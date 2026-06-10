from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from core.engine import ClinicalDecisionEngine
from poc_app.database import (
    complete_review_item,
    fetch_pending_reviews,
    fetch_recent_audit_entries,
    get_review_item,
    log_engine_decision,
    log_operator_decision,
    upsert_review_item,
)
from poc_app.emis_adapter_stub import fetch_new_results, file_result

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Pathology Auto-Filer PoC")
engine = ClinicalDecisionEngine()

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

QUICK_ACTIONS = {
    "file_normal": {
        "label": "File as Normal",
        "final_status": "Filed",
        "default_comment": "Normal, no action.",
        "send_to_emis": True,
    },
    "file_reviewed": {
        "label": "File as Reviewed",
        "final_status": "Filed",
        "default_comment": "Reviewed by operator and filed.",
        "send_to_emis": True,
    },
    "route_clinician": {
        "label": "Route to Clinician",
        "final_status": "Route to Human",
        "default_comment": "Routed to clinician for manual review.",
        "send_to_emis": False,
    },
    "hold_followup": {
        "label": "Hold for Follow-up",
        "final_status": "Hold",
        "default_comment": "Held pending follow-up/repeat bloods.",
        "send_to_emis": False,
    },
}


class OperatorDecisionRequest(BaseModel):
    result_id: str
    action_key: str = Field(description="Quick action key from /api/quick-actions")
    comment_override: str | None = None
    manual_note: str | None = None
    operator_id: str = "Operator"


def _recommended_action_for_decision(decision: str) -> str:
    if decision.startswith("Auto-file"):
        return "file_normal"
    return "route_clinician"


def _compose_comment(base_comment: str, manual_note: str | None) -> str:
    note = (manual_note or "").strip()
    if not note:
        return base_comment
    return f"{base_comment}\nManual note: {note}"


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.post("/api/run-shadow-cycle")
async def run_shadow_cycle() -> dict:
    """
    Shadow mode processing:
      - fetch new results
      - evaluate rules
      - save review queue suggestions
      - log all engine decisions
    No writes are sent to EMIS from this endpoint.
    """
    new_results = fetch_new_results()
    queue_items = []

    for result in new_results:
        decision, reasons = engine.evaluate(result)
        suggested_action_key = _recommended_action_for_decision(decision)
        suggested_comment = QUICK_ACTIONS[suggested_action_key]["default_comment"]

        upsert_review_item(
            result=result,
            engine_decision=decision,
            reasons=reasons,
            suggested_action_key=suggested_action_key,
            suggested_comment=suggested_comment,
        )
        log_engine_decision(result, decision, reasons)

        queue_items.append(
            {
                "result_id": result["id"],
                "patient_id": result["patient_id"],
                "test_type": result["test_type"],
                "value": result["value"],
                "units": result["units"],
                "engine_decision": decision,
                "reasoning": reasons,
                "suggested_action_key": suggested_action_key,
                "suggested_comment": suggested_comment,
            }
        )

    pending_count = len(fetch_pending_reviews())
    return {
        "status": "ok",
        "processed_this_cycle": len(queue_items),
        "pending_queue_count": pending_count,
        "items": queue_items,
    }


@app.get("/api/review-queue")
async def get_review_queue() -> dict:
    items = fetch_pending_reviews()
    return {"status": "ok", "count": len(items), "items": items}


@app.get("/api/quick-actions")
async def get_quick_actions() -> dict:
    return {"status": "ok", "actions": QUICK_ACTIONS}


@app.post("/api/submit-decision")
async def submit_operator_decision(payload: OperatorDecisionRequest) -> dict:
    if payload.action_key not in QUICK_ACTIONS:
        raise HTTPException(status_code=400, detail="Unknown action key")

    item = get_review_item(payload.result_id)
    if not item:
        raise HTTPException(status_code=404, detail="Result not found in review queue")
    if item["status"] != "pending":
        raise HTTPException(status_code=409, detail="Result already processed")

    action = QUICK_ACTIONS[payload.action_key]
    base_comment = (payload.comment_override or "").strip() or action["default_comment"]
    final_comment = _compose_comment(base_comment, payload.manual_note)

    if action["send_to_emis"]:
        file_result(
            result_id=payload.result_id,
            status=action["final_status"],
            comment=final_comment,
        )

    complete_review_item(
        result_id=payload.result_id,
        operator_action=payload.action_key,
        final_status=action["final_status"],
        final_comment=final_comment,
        manual_note=(payload.manual_note or "").strip(),
        operator_id=payload.operator_id,
    )
    log_operator_decision(
        item=item,
        operator_action=payload.action_key,
        final_status=action["final_status"],
        final_comment=final_comment,
        operator_id=payload.operator_id,
    )

    return {
        "status": "ok",
        "result_id": payload.result_id,
        "final_status": action["final_status"],
        "operator_action": payload.action_key,
        "final_comment": final_comment,
    }


@app.get("/api/audit-log")
async def get_audit_log(limit: int = 50) -> dict:
    safe_limit = max(1, min(limit, 500))
    rows = fetch_recent_audit_entries(safe_limit)
    return {"status": "ok", "count": len(rows), "items": rows}