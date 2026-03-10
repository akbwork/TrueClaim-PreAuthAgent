import time
import json
import logging
from datetime import datetime, timezone

from src.graph.workflow import app
from src.config.dbClient import run_query
from src.utils.helper import _parse_dt

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# def fetch_pending_preauths() -> list[dict]:
#     """Fetch all pre-auths that are pending and have no agent findings yet."""
#     return run_query(
#         """
#         SELECT id, policy_number, proposed_treatment, requested_at
#         FROM pre_authorizations
#         WHERE status = 'pending'
#           AND agent_findings IS NULL
#         ORDER BY requested_at ASC
#         """
#     )

def fetch_pending_preauths() -> list[dict]:
    """Fetch pre-auths that are pending AND all documents have completed OCR."""
    return run_query(
        """
        SELECT pa.id, pa.policy_number, pa.proposed_treatment, pa.requested_at
        FROM pre_authorizations pa
        WHERE pa.status = 'pending'
          AND pa.agent_findings IS NULL
          AND EXISTS (
              SELECT 1 FROM pre_auth_documents pad
              WHERE pad.pre_auth_id = pa.id
          )
          AND NOT EXISTS (
              SELECT 1 FROM pre_auth_documents pad
              WHERE pad.pre_auth_id = pa.id
                AND pad.ocr_agent_status != 'completed'
          )
        ORDER BY pa.requested_at ASC
        """
    )


def process_preauth(preauth_id: str) -> None:
    log.info(f"Processing preauth_id={preauth_id}")

    # Mark as underreview immediately so another worker doesn't pick it up
    run_query(
        "UPDATE pre_authorizations SET status = 'under_review', updated_at = :now WHERE id = :id",
        {"id": preauth_id, "now": datetime.now(timezone.utc).isoformat()}
    )

    try:
        result = app.invoke({"preauth_id": preauth_id})
        decision = result.get("final_decision", {})

        if not decision or decision.get("status") == "error":
            log.error(f"Graph returned error for {preauth_id}: {decision}")
            _mark_failed(preauth_id, reason=decision.get("reason", "Unknown error"))
            return

        _write_decision(preauth_id, result)
        log.info(f"Done: {preauth_id} → {decision.get('recommendation')}")

    except Exception as e:
        log.exception(f"Unhandled error for {preauth_id}: {e}")
        _mark_failed(preauth_id, reason=str(e))


def _write_decision(preauth_id: str, result: dict) -> None:
    decision   = result.get("final_decision", {})
    pre_auth   = result.get("pre_auth", {})

    status_map = {
        "approve"       : "approved",
        "reject"        : "rejected",
        "manual_review" : "under_review",
    }
    status = status_map.get(decision.get("recommendation"), "underreview")

    requested_at  = _parse_dt(pre_auth.get("requested_at"))
    now           = datetime.now(timezone.utc)
    response_time = int((now - requested_at).total_seconds() / 60) if requested_at else None

    agent_findings = {
        "ocr_summary"           : decision.get("ocr_summary"),
        "policy_summary"        : decision.get("policy_summary"),
        "waiting_period_summary": decision.get("waiting_period_summary"),
        "cost_summary"          : decision.get("cost_summary"),
        "sop_summary"           : decision.get("sop_summary"),
        "manual_review_reasons" : decision.get("manual_review_reasons", []),
        "conditions"            : decision.get("conditions", []),
        "rejection_reasons"     : decision.get("rejection_reasons", []),
        "overall_summary"       : decision.get("overall_summary"),
        "recommended_amount"    : decision.get("recommended_amount"),
        # Intermediate check results for audit
        "ocr_validation"        : result.get("ocr_validation", {}),
        "policy_check"          : result.get("policy_check", {}),
        "waiting_period_check"  : result.get("waiting_period_check", {}),
        "cost_check"            : result.get("cost_check", {}),
        "sop_check"             : result.get("sop_check", {}),
    }

    run_query(
        """
        UPDATE pre_authorizations SET
            status                = :status,
            approved_amount       = :approved_amount,
            conditions            = :conditions,
            rejection_reason      = :rejection_reason,
            responded_at          = :responded_at,
            response_time_minutes = :response_time_minutes,
            agent_findings        = :agent_findings,
            updated_at            = :updated_at
        WHERE id = :id
        """,
        {
            "id"                   : preauth_id,
            "status"               : status,
            "approved_amount"      : decision.get("approved_amount"),
            "conditions"           : "; ".join(decision.get("conditions", [])) or None,
            "rejection_reason"     : "; ".join(decision.get("rejection_reasons", [])) or None,
            "responded_at"         : now.isoformat(),
            "response_time_minutes": response_time,
            "agent_findings"       : json.dumps(agent_findings, default=str),
            "updated_at"           : now.isoformat(),
        }
    )


def _mark_failed(preauth_id: str, reason: str) -> None:
    """Reset to pending so it can be retried, log the error."""
    run_query(
        """
        UPDATE pre_authorizations SET
            status        = 'pending',
            agent_findings = :findings,
            updated_at    = :now
        WHERE id = :id
        """,
        {
            "id"      : preauth_id,
            "findings": json.dumps({"error": reason, "failed_at": datetime.now(timezone.utc).isoformat()}),
            "now"     : datetime.now(timezone.utc).isoformat(),
        }
    )


def run_worker(poll_interval_seconds: int = 30) -> None:
    log.info(f"Worker started. Polling every {poll_interval_seconds}s for pending pre-auths.")
    while True:
        try:
            pending = fetch_pending_preauths()
            if pending:
                log.info(f"Found {len(pending)} pending pre-auth(s)")
                for row in pending:
                    process_preauth(row["id"])
            else:
                log.info("No pending pre-auths. Sleeping...")
        except Exception as e:
            log.exception(f"Worker poll error: {e}")

        time.sleep(poll_interval_seconds)

# RUN python main.py --mode worker --interval 30