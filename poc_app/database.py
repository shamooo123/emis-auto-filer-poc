import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_FILE = Path(__file__).resolve().parent.parent / "shadow_audit_log.db"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create audit + review queue tables if missing."""
    with _connect() as conn:
        cursor = conn.cursor()
        _create_review_queue_table(cursor)
        _create_audit_log_table(cursor)
        _migrate_legacy_review_queue_if_needed(cursor)
        _migrate_legacy_audit_log_if_needed(cursor)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_review_queue_status ON review_queue(status)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_audit_log_result_id ON audit_log(result_id)"
        )
        conn.commit()


def _create_review_queue_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS review_queue (
            result_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            patient_id TEXT NOT NULL,
            test_type TEXT NOT NULL,
            value REAL NOT NULL,
            units TEXT NOT NULL,
            engine_decision TEXT NOT NULL,
            reasoning_json TEXT NOT NULL,
            suggested_action_key TEXT NOT NULL,
            suggested_comment TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            processed_at TEXT,
            operator_action TEXT,
            final_status TEXT,
            final_comment TEXT,
            manual_note TEXT,
            operator_id TEXT,
            raw_data_json TEXT NOT NULL
        )
        """
    )


def _create_audit_log_table(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            result_id TEXT NOT NULL,
            test_type TEXT,
            stage TEXT NOT NULL,
            engine_decision TEXT,
            reasoning TEXT,
            operator_action TEXT,
            final_status TEXT,
            comment TEXT,
            operator_id TEXT,
            raw_data_json TEXT
        )
        """
    )


def _migrate_legacy_review_queue_if_needed(cursor: sqlite3.Cursor) -> None:
    required_columns = {
        "result_id",
        "created_at",
        "patient_id",
        "test_type",
        "value",
        "units",
        "engine_decision",
        "reasoning_json",
        "suggested_action_key",
        "suggested_comment",
        "status",
        "processed_at",
        "operator_action",
        "final_status",
        "final_comment",
        "manual_note",
        "operator_id",
        "raw_data_json",
    }
    current_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(review_queue)").fetchall()
    }
    if required_columns.issubset(current_columns):
        return

    cursor.execute("ALTER TABLE review_queue RENAME TO review_queue_legacy")
    _create_review_queue_table(cursor)
    cursor.execute("DROP TABLE review_queue_legacy")


def _migrate_legacy_audit_log_if_needed(cursor: sqlite3.Cursor) -> None:
    required_columns = {
        "id",
        "timestamp",
        "result_id",
        "test_type",
        "stage",
        "engine_decision",
        "reasoning",
        "operator_action",
        "final_status",
        "comment",
        "operator_id",
        "raw_data_json",
    }
    current_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(audit_log)").fetchall()
    }
    if required_columns.issubset(current_columns):
        return

    cursor.execute("ALTER TABLE audit_log RENAME TO audit_log_legacy")
    _create_audit_log_table(cursor)

    legacy_columns = {
        row["name"] for row in cursor.execute("PRAGMA table_info(audit_log_legacy)").fetchall()
    }
    can_migrate_old_rows = {"timestamp", "result_id", "test_type", "decision", "reasoning", "raw_data"}.issubset(legacy_columns)
    if can_migrate_old_rows:
        cursor.execute(
            """
            INSERT INTO audit_log (
                timestamp, result_id, test_type, stage, engine_decision, reasoning, raw_data_json
            )
            SELECT timestamp, result_id, test_type, 'engine_evaluation', decision, reasoning, raw_data
            FROM audit_log_legacy
            """
        )

    cursor.execute("DROP TABLE audit_log_legacy")


def upsert_review_item(
    result: dict[str, Any],
    engine_decision: str,
    reasons: list[str],
    suggested_action_key: str,
    suggested_comment: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO review_queue (
                result_id, created_at, patient_id, test_type, value, units, engine_decision,
                reasoning_json, suggested_action_key, suggested_comment, status, raw_data_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            ON CONFLICT(result_id) DO UPDATE SET
                created_at = excluded.created_at,
                patient_id = excluded.patient_id,
                test_type = excluded.test_type,
                value = excluded.value,
                units = excluded.units,
                engine_decision = excluded.engine_decision,
                reasoning_json = excluded.reasoning_json,
                suggested_action_key = excluded.suggested_action_key,
                suggested_comment = excluded.suggested_comment,
                status = 'pending',
                processed_at = NULL,
                operator_action = NULL,
                final_status = NULL,
                final_comment = NULL,
                manual_note = NULL,
                operator_id = NULL,
                raw_data_json = excluded.raw_data_json
            """,
            (
                result["id"],
                _utc_now(),
                result["patient_id"],
                result["test_type"],
                float(result["value"]),
                result["units"],
                engine_decision,
                json.dumps(reasons),
                suggested_action_key,
                suggested_comment,
                json.dumps(result),
            ),
        )
        conn.commit()


def log_engine_decision(result: dict[str, Any], decision: str, reasons: list[str]) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (
                timestamp, result_id, test_type, stage, engine_decision, reasoning, raw_data_json
            ) VALUES (?, ?, ?, 'engine_evaluation', ?, ?, ?)
            """,
            (
                _utc_now(),
                result["id"],
                result.get("test_type"),
                decision,
                " | ".join(reasons) if reasons else "No reason logged",
                json.dumps(result),
            ),
        )
        conn.commit()


def fetch_pending_reviews(limit: int = 200) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM review_queue
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_deserialize_review_row(row) for row in rows]


def get_review_item(result_id: str) -> dict[str, Any] | None:
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM review_queue WHERE result_id = ?",
            (result_id,),
        ).fetchone()
    return _deserialize_review_row(row) if row else None


def complete_review_item(
    result_id: str,
    operator_action: str,
    final_status: str,
    final_comment: str,
    manual_note: str,
    operator_id: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE review_queue
            SET status = 'processed',
                processed_at = ?,
                operator_action = ?,
                final_status = ?,
                final_comment = ?,
                manual_note = ?,
                operator_id = ?
            WHERE result_id = ?
            """,
            (
                _utc_now(),
                operator_action,
                final_status,
                final_comment,
                manual_note,
                operator_id,
                result_id,
            ),
        )
        conn.commit()


def log_operator_decision(
    item: dict[str, Any],
    operator_action: str,
    final_status: str,
    final_comment: str,
    operator_id: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_log (
                timestamp, result_id, test_type, stage, engine_decision, reasoning,
                operator_action, final_status, comment, operator_id, raw_data_json
            ) VALUES (?, ?, ?, 'operator_decision', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _utc_now(),
                item["result_id"],
                item["test_type"],
                item["engine_decision"],
                " | ".join(item.get("reasoning", [])),
                operator_action,
                final_status,
                final_comment,
                operator_id,
                json.dumps(item.get("raw_data", {})),
            ),
        )
        conn.commit()


def fetch_recent_audit_entries(limit: int = 100) -> list[dict[str, Any]]:
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT timestamp, result_id, test_type, stage, engine_decision,
                   reasoning, operator_action, final_status, comment, operator_id
            FROM audit_log
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def _deserialize_review_row(row: sqlite3.Row) -> dict[str, Any]:
    raw_data = row["raw_data_json"] if row["raw_data_json"] else "{}"
    reasoning_json = row["reasoning_json"] if row["reasoning_json"] else "[]"
    return {
        "result_id": row["result_id"],
        "created_at": row["created_at"],
        "patient_id": row["patient_id"],
        "test_type": row["test_type"],
        "value": row["value"],
        "units": row["units"],
        "engine_decision": row["engine_decision"],
        "reasoning": json.loads(reasoning_json),
        "suggested_action_key": row["suggested_action_key"],
        "suggested_comment": row["suggested_comment"],
        "status": row["status"],
        "processed_at": row["processed_at"],
        "operator_action": row["operator_action"],
        "final_status": row["final_status"],
        "final_comment": row["final_comment"],
        "manual_note": row["manual_note"],
        "operator_id": row["operator_id"],
        "raw_data": json.loads(raw_data),
    }


init_db()