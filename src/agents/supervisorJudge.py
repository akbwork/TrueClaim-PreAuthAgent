from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from src.config.llmClients import get_OpenAIClient


class FinalDecision(BaseModel):
    recommendation: str                  # approve | reject | manual_review
    approved_amount: float | None       # keep None only for hard rejects
    recommended_amount: float | None    # always populate from cost_check
    conditions: list[str]                # e.g. "Room rent capped at ₹5000/night"
    rejection_reasons: list[str]         # empty if approved
    manual_review_reasons: list[str]     # empty if approved/rejected cleanly
    ocr_summary: str
    policy_summary: str
    waiting_period_summary: str
    cost_summary: str
    sop_summary: str
    overall_summary: str                 # 3-4 lines for claim processor


SYSTEM_PROMPT = """You are a senior medical insurance pre-authorization supervisor.

You will receive the results of five validation checks run on a pre-authorization request:
1. OCR Validation — document authenticity and consistency
2. Policy Eligibility — policy active, premium paid, sum insured, member coverage
3. Waiting Period & Exclusions — treatment not excluded, waiting periods cleared
4. Cost Estimation — CGHS-based admissible amount
5. SOP Compliance — treatment and billing aligned with standard protocols

Your job is to make a final recommendation:
- "approve" — all checks passed, cost is within limits, no red flags
- "reject" — one or more hard failures (exclusion hit, policy lapsed, waiting period active)
- "manual_review" — mixed signals, low confidence, or borderline cases needing human judgment

Rules:
- If policy_check or waiting_period_check has hard_fail=true → recommend reject
- If ocr_validation has critical mismatches → recommend manual_review at minimum  
- If sop_check has billing non-compliance → flag in conditions, do not auto-approve
- approved_amount should come from cost_check.recommended_approved_amount
- Be concise but complete in overall_summary — this is what the claim processor reads first
"""

USER_PROMPT = """
## Pre-Authorization Details
Preauth ID: {preauth_id}
Proposed Treatment: {proposed_treatment}
Estimated Cost Submitted: ₹{estimated_cost}
Policy Number: {policy_number}

## OCR Validation Result
{ocr_validation}

## Policy Eligibility Result
{policy_check}

## Waiting Period & Exclusion Result
{waiting_period_check}

## Cost Estimation Result
{cost_check}

## SOP Compliance Result
{sop_check}

Based on all the above, make your final recommendation.
"""

llm = get_OpenAIClient()
supervisor_chain = (
    ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("human", USER_PROMPT),
    ])
    | llm.with_structured_output(FinalDecision)
)
