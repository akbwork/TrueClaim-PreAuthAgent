from typing import Optional, Any, Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class PreAuthState(TypedDict):
    # Input
    preauth_id: str

    # Raw data fetched from DB at the start
    pre_auth: dict          # pre_authorizations row
    policy: dict            # policies row
    policy_member: list[dict]    # policy_members row
    ocr_data: list[dict]          # merged OCR fields from pre_auth_documents

    # Agent results  (each agent writes its own key)
    cost_check: dict        # CostCheckAgent result
    diagnosis_check: dict   # DiagnosisCheckAgent result
    waiting_period_check: dict  # WaitingPeriodCheckAgent result
    ocr_validation: dict    # OCRValidationAgent result
    policy_check: dict 
    sop_check: dict

    # Final decision assembled by the supervisor
    final_decision: dict

    # Free-form messages from agents (for LLM reasoning traces)
    messages: Annotated[list[Any], add_messages]