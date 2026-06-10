# EMIS Auto Filer PoC (Human-in-the-Loop)

This PoC keeps clinicians/operators in control while speeding up blood result filing through:

- a local shadow cycle that fetches + evaluates unfiled results
- a review queue with quick actions
- prefilled coded comments that operators can edit
- optional manual note append
- full local SQLite audit trail

## Run locally

```bash
pip install -r requirements.txt
uvicorn poc_app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Workflow

1. Click **Run Shadow Cycle** to ingest simulated EMIS results.
2. Review each result card and use a quick action:
   - `File as Normal`
   - `Route to Clinician`
   - or choose another action from dropdown.
3. Edit the prefilled comment if needed.
4. Add an optional manual note.
5. Submit decision (logged in audit table + SQLite).

## Safety defaults

- Any ambiguity routes to human.
- Unsupported/deferred tests route to human.
- Engine gate failures route to human.
- Shadow cycle endpoint performs no EMIS writes.
- All data remains local in `shadow_audit_log.db`.

