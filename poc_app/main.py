from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from poc_app.emis_adapter_stub import fetch_new_results
from poc_app.database import log_decision
from core.engine import ClinicalDecisionEngine

app = FastAPI(title="Pathology Auto-Filer PoC")
engine = ClinicalDecisionEngine()

app.mount("/static", StaticFiles(directory="poc_app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    with open("poc_app/static/index.html") as f:
        return f.read()

@app.post("/api/run-shadow-cycle")
async def run_shadow_cycle():
    """
    Executes a shadow-mode processing sweep[cite: 1]. Reads data, evaluates rules,
    logs outcomes, and ensures absolute safety with zero EMIS writes.
    """
    new_results = fetch_new_results()
    audit_log = []
    
    for result in new_results:
        # Run the engine
        decision, reasons = engine.evaluate(result)
        
        # Shadow Run Rule: Log decisions safely to SQLite; do not push changes to EMIS[cite: 1, 2]
        log_decision(result, decision, reasons)
        
        audit_log.append({
            "patient": result["patient_id"],
            "test_type": result["test_type"],
            "value": f"{result['value']} {result['units']}",
            "decision": decision,
            "reasoning": " | ".join(reasons)
        })
        
    return {"status": "success", "processed": len(new_results), "log": audit_log}