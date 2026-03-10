from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from src.graph.workflow import app
from src.worker.worker import _write_decision, _mark_failed
import json

api = FastAPI()

api.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@api.get("/preauth/{preauth_id}/stream")
async def stream_preauth(preauth_id: str):

    def event_stream():
        full_state = {}

        for event in app.stream(
            {"preauth_id": preauth_id},
            stream_mode="updates"
        ):
            for node_name, state_update in event.items():
                # Accumulate state updates
                full_state.update(state_update)

                payload = {
                    "node"   : node_name,
                    "status" : _node_label(node_name),
                    "passed" : _extract_passed(node_name, state_update),
                }
                yield f"data: {json.dumps(payload)}\n\n"

        # Persist full result to DB
        if full_state.get("final_decision"):
            try:
                _write_decision(preauth_id, full_state)
            except Exception as e:
                _mark_failed(preauth_id, reason=str(e))

        yield "data: {\"node\": \"done\"}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _node_label(node_name: str) -> str:
    labels = {
        "data_loader_node"                  : "Loading pre-authorization data...",
        "ocr_validation_node"               : "Validating documents (OCR)...",
        "policy_eligibility_node"           : "Checking policy eligibility...",
        "waiting_period_and_exclusion_node" : "Checking exclusions & waiting periods...",
        "cost_check_node"                   : "Estimating admissible cost (CGHS)...",
        "sop_compliance_node"               : "Checking SOP compliance...",
        "supervisor_node"                   : "Assembling final decision...",
    }
    return labels.get(node_name, node_name)


def _extract_passed(node_name: str, update: dict) -> bool | None:
    if "policy_check" in update:
        return update["policy_check"].get("passed")
    if "waiting_period_check" in update:
        return not update["waiting_period_check"].get("hard_fail", False)
    if "ocr_validation" in update:
        return update["ocr_validation"].get("passed")
    if "final_decision" in update:
        rec = update["final_decision"].get("recommendation")
        return rec == "approve"
    return None


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.stream:api", host="0.0.0.0", port=8081, reload=True)