from src.graph.states import PreAuthState
from src.agents.costAgent import cost_agent, CostCheckResult
from src.config.dbClient import run_query
from src.agents.ocrJudge import ocr_validation_chain, OCRValidationResult
from src.agents.w_periodJudge import waiting_period_exclusion_chain, WaitingPeriodExclusionResult
from src.agents.sopAgent import sop_agent
from src.agents.supervisorJudge import supervisor_chain, FinalDecision
from src.utils.helper import _parse_dt

import json
from datetime import datetime, timezone

# Document Loader Node
def data_loader_node(state: PreAuthState) -> PreAuthState:
    preauth_id = state["preauth_id"]

     # Initialise all check keys so downstream nodes never hit KeyError
    state["ocr_validation"]     = {}
    state["policy_check"]       = {}
    state["waiting_period_check"] = {}
    state["cost_check"]         = {}
    state["sop_check"]          = {}
    state["final_decision"]     = {}

    # 1. Load pre_auth row
    rows = run_query("SELECT * FROM pre_authorizations WHERE id = :id", {"id": preauth_id})
    if not rows:
        return {**state, "final_decision": {"status": "error", "reason": f"PreAuth {preauth_id} not found"}}
    state["pre_auth"] = rows[0]

    # 2. Load policy
    policy_id = state["pre_auth"].get("policy_id")
    if policy_id:
        rows = run_query("SELECT * FROM policies WHERE id = :id", {"id": policy_id})
        state["policy"] = rows[0] if rows else {}

    # 3. Load ALL policy members for this policy (patient_id may be null in DB)
    if policy_id:
        state["policy_member"] = run_query(
            "SELECT * FROM policy_members WHERE policy_id = :policy_id",
            {"policy_id": policy_id}
        )

    # 4. Load OCR documents
    state["ocr_data"] = run_query(
        "SELECT * FROM pre_auth_documents WHERE pre_auth_id = :id",
        {"id": preauth_id}
    )

    return state


# Document Verifier Node 
def ocr_validation_node(state: PreAuthState) -> PreAuthState:
    result: OCRValidationResult = ocr_validation_chain.invoke({
        "pre_auth": json.dumps(state["pre_auth"], indent=2, default=str),
        "policy": json.dumps(state["policy"], indent=2, default=str),
        "ocr_docs": json.dumps(state["ocr_data"], indent=2, default=str),
    })

    state["ocr_validation"] = result.model_dump()
    return state


# Policy Eligibility Node 
def policy_eligibility_node(state: PreAuthState) -> PreAuthState:
    policy = state["policy"]
    members = state["policy_member"]
    pre_auth = state["pre_auth"]

    findings = []
    flags = []
    hard_fail = False

    now = datetime.now(timezone.utc)

    # Check Policy Status (Active or Not)
    if policy.get("status") != "active":
        flags.append(f"POLICY_NOT_ACTIVE: status={policy.get('status')}")
        hard_fail = True
    else:
        findings.append("Policy status is active")

    # Check if Premimum Paid
    if not policy.get("premium_paid"):
        flags.append("PREMIUM_NOT_PAID")
        hard_fail = True
    else:
        findings.append("Premium paid")

    # Check if Polciy validity dates
    start = _parse_dt(policy.get("policy_start_date"))
    end = _parse_dt(policy.get("policy_end_date"))

    if start and now < start:
        flags.append(f"POLICY_NOT_YET_ACTIVE: starts {start.date()}")
        hard_fail = True
    elif end and now > end:
        flags.append(f"POLICY_EXPIRED: expired {end.date()}")
        hard_fail = True
    else:
        findings.append(f"Policy valid until {end.date() if end else 'N/A'}")

    # Check if there is any wait period
    waiting_days = policy.get("initial_waiting_period_days") or 30
    if start:
        days_since_start = (now - start).days
        if days_since_start < waiting_days:
            days_remaining = waiting_days - days_since_start
            flags.append(
                f"INITIAL_WAITING_PERIOD_ACTIVE: {days_remaining} days remaining "
                f"(policy started {start.date()}, waiting period {waiting_days} days)"
            )
            hard_fail = True
        else:
            findings.append(f"Initial waiting period of {waiting_days} days elapsed")

    # Check if there is enough Sum Insured
    sum_insured = float(policy.get("sum_insured") or 0)
    utilized = float(policy.get("utilized_sum_insured") or 0)
    estimated_cost = float(pre_auth.get("estimated_treatment_cost") or 0)
    remaining = sum_insured - utilized

    if remaining <= 0:
        flags.append(f"SUM_INSURED_EXHAUSTED: utilized ₹{utilized} of ₹{sum_insured}")
        hard_fail = True
    elif estimated_cost > remaining:
        flags.append(
            f"INSUFFICIENT_SUM_INSURED: estimated cost ₹{estimated_cost} "
            f"exceeds remaining ₹{remaining} (utilized ₹{utilized} of ₹{sum_insured})"
        )
        # Soft flag — not a hard fail, cost estimator may approve partial
        findings.append(
            f"Remaining sum insured: ₹{remaining} | Estimated cost: ₹{estimated_cost} — partial approval possible"
        )
    else:
        findings.append(
            f"Sum insured sufficient: ₹{remaining} remaining, "
            f"estimated cost ₹{estimated_cost}"
        )

    # Check if the Member is eligible #TODO - Rewrite this logic again
    patient_id = pre_auth.get("patient_id")
    matched_member = None

    for member in members:
        # Match by patient_id if populated, else leave for OCR name match
        if patient_id and member.get("patient_id") == patient_id:
            matched_member = member
            break

    # Fallback: if patient_id is null in policy_members (as in your current data),
    # just check that at least one active (non-terminated) member exists
    if not matched_member:
        active_members = [
            m for m in members
            if not m.get("termination_date") or
            _parse_dt(m.get("termination_date")) > now
        ]
        if not active_members:
            flags.append("NO_ACTIVE_MEMBER_FOUND_ON_POLICY")
            hard_fail = True
        else:
            matched_member = active_members[0]
            findings.append(
                f"Active member found on policy "
                f"(relationship: {matched_member.get('relationship')}) ✓ "
                f"[patient_id not linked in DB — verify via OCR name match]"
            )
    else:
        # Check member termination date
        termination = _parse_dt(matched_member.get("termination_date"))
        if termination and now > termination:
            flags.append(
                f"MEMBER_TERMINATED: termination date was {termination.date()}"
            )
            hard_fail = True
        else:
            findings.append(
                f"Member active on policy "
                f"(relationship: {matched_member.get('relationship')}) ✓"
            )

    # Check for Co-pay and deductible
    co_pay = float(policy.get("co_pay_percentage") or 0)
    deductible = float(policy.get("deductible_amount") or 0)
    if co_pay > 0:
        findings.append(f"Co-pay applicable: {co_pay}% — cost estimator should factor this in")
    if deductible > 0:
        findings.append(f"Deductible applicable: ₹{deductible} — cost estimator should factor this in")

    state["policy_check"] = {
        "passed": not hard_fail,
        "hard_fail": hard_fail,
        "findings": findings,
        "flags": flags,
        "remaining_sum_insured": remaining,
        "matched_member": matched_member,
        "co_pay_percentage": co_pay,
        "deductible_amount": deductible,
    }
    return state


# Waiting Period Checker Node 
def waiting_period_and_exclusion_node(state: PreAuthState) -> PreAuthState:
    pre_auth  = state["pre_auth"]
    policy    = state["policy"]
    members   = state["policy_member"]   # list[dict]

    # Fetch reference data from DB
    exclusions = run_query(
        "SELECT exclusion_name, exclusion_category, icd_10_codes, "
        "procedure_keywords, description, is_permanent "
        "FROM policy_exclusions"
    )

    disease_waiting_periods = run_query(
        "SELECT disease_name, icd_10_code, waiting_period_days, "
        "period_type, description "
        "FROM disease_waiting_periods WHERE is_active = true"
    )

    procedure_coverage_rules = run_query(
        "SELECT procedure_name, icd_codes, specialty_required, is_covered, "
        "waiting_period_days, requires_pre_auth, age_restriction, "
        "exclusion_conditions, max_allowed_per_year "
        "FROM procedure_coverage_rules"
    )

    # Compute elapsed days (plain arithmetic)
    now = datetime.now(timezone.utc)

    policy_start = _parse_dt(policy.get("policy_start_date"))
    days_since_policy_start = (now - policy_start).days if policy_start else 0

    # Use earliest enrollment date across all members as the reference
    enrollment_dates = [
        _parse_dt(m.get("enrollment_date"))
        for m in members
        if m.get("enrollment_date")
    ]
    earliest_enrollment = min(enrollment_dates) if enrollment_dates else policy_start
    days_since_enrollment = (now - earliest_enrollment).days if earliest_enrollment else 0

    # Collect all PEDs across all members
    all_peds = []
    for member in members:
        ped_data = member.get("pre_existing_diseases")
        if ped_data:
            if isinstance(ped_data, str):
                try:
                    ped_data = json.loads(ped_data)
                except json.JSONDecodeError:
                    pass
            summary = ped_data.get("summary", "") if isinstance(ped_data, dict) else str(ped_data)
            if summary:
                all_peds.append(f"[{member.get('relationship', 'member')}] {summary}")

    # LLM Sematic Mathcing Call
    result: WaitingPeriodExclusionResult = waiting_period_exclusion_chain.invoke({
        "proposed_treatment"        : pre_auth.get("proposed_treatment", ""),
        "peds"                      : "\n".join(all_peds) if all_peds else "None recorded",
        "days_since_policy_start"   : days_since_policy_start,
        "policy_start_date"         : policy_start.date() if policy_start else "N/A",
        "days_since_enrollment"     : days_since_enrollment,
        "enrollment_date"           : earliest_enrollment.date() if earliest_enrollment else "N/A",
        "ped_waiting_period_days"   : policy.get("ped_waiting_period_days", 730),
        "initial_waiting_period_days": policy.get("initial_waiting_period_days", 30),
        "exclusions"                : json.dumps(exclusions, indent=2, default=str),
        "disease_waiting_periods"   : json.dumps(disease_waiting_periods, indent=2, default=str),
        "procedure_coverage_rules"  : json.dumps(procedure_coverage_rules, indent=2, default=str),
    })

    state["waiting_period_check"] = result.model_dump()
    return state


# Cost Checker Node 
def cost_check_node(state: PreAuthState) -> PreAuthState:
    policy_check = state["policy_check"]
    pre_auth = state["pre_auth"]

    ward_entitlement = (
    state.get("ocr_validation", {})
    .get("policy_card_check", {})
    .get("observations", ["Semi-Private"])[0]  # fallback to Semi-Private
        )

    result = cost_agent.invoke({
                "messages": [{
                    "role": "user",
                    "content": f"""
        Estimate admissible cost for the following pre-authorization:

        Proposed Treatment: {pre_auth['proposed_treatment']}
        Estimated Cost Submitted: ₹{pre_auth['estimated_treatment_cost']}
        Expected Duration: {pre_auth['expected_duration_days']} days
        Remaining Sum Insured: ₹{policy_check['remaining_sum_insured']}
        Co-pay: {policy_check['co_pay_percentage']}%
        Deductible: ₹{policy_check['deductible_amount']}
        Room Rent Limit: ₹{state['policy'].get('room_rent_limit')} ({state['policy'].get('room_rent_limit_type')})
        Ward Entitlement from ECHS Card: {ward_entitlement}

        Look up CGHS rates and service_rate_master for each component.
        Return structured JSON.
        """
        }]
    })

    raw = result["messages"][-1].content
    try:
        # Strip markdown code fences if LLM wraps in ```json
        clean = raw.strip().removeprefix("```json").removesuffix("```").strip()
        state["cost_check"] = json.loads(clean)
    except json.JSONDecodeError:
        state["cost_check"] = {"raw": raw, "parse_error": True}
    return state

    

# SOP Compliance Node #TODO - Rework the SOP NODE
def sop_compliance_node(state: PreAuthState) -> PreAuthState:
    pre_auth     = state["pre_auth"]
    cost_check   = state["cost_check"]
    policy_check = state["policy_check"]
    waiting_check = state["waiting_period_check"]

    result = sop_agent.invoke({
        "messages": [{
            "role": "user",
            "content": f"""
        Check SOP compliance for this pre-authorization:

        Proposed Treatment: {pre_auth['proposed_treatment']}
        Expected Duration: {pre_auth['expected_duration_days']} days
        Estimated Cost Submitted: ₹{pre_auth['estimated_treatment_cost']}
        Recommended Approved Amount (from cost check): {cost_check.get('recommended_approved_amount', 'N/A')}

        Prior Findings:
        - Policy Check: {policy_check.get('findings')}
        - Waiting Period / Exclusion Check: {waiting_check.get('summary')}
        - Cost Check Notes: {cost_check.get('notes')}

        OCR Validation Summary: {state['ocr_validation'].get('summary')}

        Check treatment SOP, billing SOP, and documentation adequacy.
        Return structured JSON.
        """
        }]
    })

    raw = result["messages"][-1].content
    try:
        clean = raw.strip().removeprefix("```json").removesuffix("```").strip()
        state["sop_check"] = json.loads(clean)
    except json.JSONDecodeError:
        state["sop_check"] = {"raw": raw, "parse_error": True, "passed": False}

    return state


# Supervisor Node
def supervisor_node(state: PreAuthState) -> PreAuthState:
    pre_auth = state["pre_auth"]

    # Handle early-exit error case from data_loader_node
    if state.get("final_decision", {}).get("status") == "error":
        return state

    result: FinalDecision = supervisor_chain.invoke({
        "preauth_id"          : state["preauth_id"],
        "proposed_treatment"  : pre_auth.get("proposed_treatment", ""),
        "estimated_cost"      : pre_auth.get("estimated_treatment_cost", 0),
        "policy_number"       : pre_auth.get("policy_number", ""),
        "ocr_validation"      : json.dumps(state.get("ocr_validation", {}), indent=2, default=str),
        "policy_check"        : json.dumps(state.get("policy_check", {}), indent=2, default=str),
        "waiting_period_check": json.dumps(state.get("waiting_period_check", {}), indent=2, default=str),
        "cost_check"          : json.dumps(state.get("cost_check", {}), indent=2, default=str),
        "sop_check"           : json.dumps(state.get("sop_check", {}), indent=2, default=str),
    })

    state["final_decision"] = result.model_dump()
    return state
