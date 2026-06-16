from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fusa_ai_studio.database.connection import connect, rows_to_dicts


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class Repository:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        return connect(self.db_path)

    def get_setting(self, key: str, default: str = "") -> str:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, value, now_iso()),
            )
            conn.commit()

    def list_projects(self) -> list[dict]:
        with self._connect() as conn:
            return rows_to_dicts(conn.execute("SELECT * FROM projects ORDER BY updated_at DESC"))

    def get_project(self, project_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return dict(row) if row else None

    def upsert_project(self, project_id: str, name: str, description: str, standard: str) -> None:
        ts = now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO projects(id, name, description, standard, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    description = excluded.description,
                    standard = excluded.standard,
                    updated_at = excluded.updated_at
                """,
                (project_id, name, description, standard, ts, ts),
            )
            conn.commit()

    def list_table(self, table: str, project_id: str | None = None) -> list[dict]:
        allowed = {
            "items",
            "hazards",
            "safety_goals",
            "fsc_requirements",
            "tsc_requirements",
            "trace_links",
            "knowledge_documents",
            "knowledge_chunks",
            "project_memory",
            "ai_interactions",
            "workflow_tasks",
            "doc_templates",
            "documents",
            "vector_collections",
        }
        if table not in allowed:
            raise ValueError(f"Unsupported table: {table}")
        with self._connect() as conn:
            if project_id and table != "doc_templates":
                return rows_to_dicts(conn.execute(f"SELECT * FROM {table} WHERE project_id = ? ORDER BY id DESC", (project_id,)))
            return rows_to_dicts(conn.execute(f"SELECT * FROM {table} ORDER BY id DESC"))

    def insert(self, table: str, values: dict[str, Any]) -> int:
        ts = now_iso()
        columns = dict(values)
        if "created_at" not in columns:
            columns["created_at"] = ts
        if table in {
            "items",
            "hazards",
            "safety_goals",
            "fsc_requirements",
            "tsc_requirements",
            "knowledge_documents",
            "workflow_tasks",
        } and "updated_at" not in columns:
            columns["updated_at"] = ts
        keys = list(columns.keys())
        placeholders = ", ".join("?" for _ in keys)
        sql = f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({placeholders})"
        with self._connect() as conn:
            cursor = conn.execute(sql, tuple(columns[k] for k in keys))
            conn.commit()
            return int(cursor.lastrowid)

    def update(self, table: str, row_id: int, values: dict[str, Any]) -> None:
        columns = dict(values)
        columns["updated_at"] = now_iso()
        assignments = ", ".join(f"{key} = ?" for key in columns)
        with self._connect() as conn:
            conn.execute(f"UPDATE {table} SET {assignments} WHERE id = ?", (*columns.values(), row_id))
            conn.commit()

    def delete(self, table: str, row_id: int) -> None:
        with self._connect() as conn:
            conn.execute(f"DELETE FROM {table} WHERE id = ?", (row_id,))
            conn.commit()

    def add_trace(self, project_id: str, source_type: str, source_id: str, target_type: str, target_id: str, link_type: str, rationale: str) -> None:
        existing = self.find_trace(project_id, source_type, source_id, target_type, target_id, link_type)
        if existing:
            return
        self.insert(
            "trace_links",
            {
                "project_id": project_id,
                "source_type": source_type,
                "source_id": str(source_id),
                "target_type": target_type,
                "target_id": str(target_id),
                "link_type": link_type,
                "rationale": rationale,
            },
        )

    def find_trace(self, project_id: str, source_type: str, source_id: str, target_type: str, target_id: str, link_type: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM trace_links
                WHERE project_id = ? AND source_type = ? AND source_id = ?
                  AND target_type = ? AND target_id = ? AND link_type = ?
                """,
                (project_id, source_type, str(source_id), target_type, str(target_id), link_type),
            ).fetchone()
        return dict(row) if row else None

    def add_memory(self, project_id: str, memory_type: str, content: str, importance: int = 3) -> int:
        return self.insert(
            "project_memory",
            {
                "project_id": project_id,
                "memory_type": memory_type,
                "content": content,
                "importance": importance,
            },
        )

    def recent_memory(self, project_id: str, limit: int = 8) -> list[dict]:
        with self._connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    "SELECT * FROM project_memory WHERE project_id = ? ORDER BY importance DESC, id DESC LIMIT ?",
                    (project_id, limit),
                )
            )

    def store_ai_interaction(self, project_id: str, feature: str, provider: str, model: str, question: str, retrieved_context: list[dict], response: str, metadata: dict | None = None) -> int:
        # Write a sidecar metadata file for auditing into the project's Error folder
        try:
            from fusa_ai_studio import logging_config

            ai_dir = logging_config.ERROR_DIR / "ai_interactions"
            ai_dir.mkdir(parents=True, exist_ok=True)
            safe_name = f"ai_{project_id}_{int(datetime.utcnow().timestamp())}.json"
            payload = {
                "project_id": project_id,
                "feature": feature,
                "provider": provider,
                "model": model,
                "question": question,
                "retrieved_context": retrieved_context,
                "response": response,
                "metadata": metadata or {},
            }
            (ai_dir / safe_name).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except Exception:
            # avoid raising on logging failure
            pass

        return self.insert(
            "ai_interactions",
            {
                "project_id": project_id,
                "feature": feature,
                "provider": provider,
                "model": model,
                "question": question,
                "retrieved_context": json.dumps(retrieved_context, indent=2),
                "response": response,
            },
        )

    def metrics(self, project_id: str) -> dict[str, int]:
        tables = ["items", "hazards", "safety_goals", "fsc_requirements", "tsc_requirements", "trace_links", "knowledge_documents", "workflow_tasks"]
        with self._connect() as conn:
            return {
                table: int(conn.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE project_id = ?", (project_id,)).fetchone()["c"])
                for table in tables
            }

    def due_tasks(self, project_id: str) -> list[dict]:
        today = date.today().isoformat()
        with self._connect() as conn:
            return rows_to_dicts(
                conn.execute(
                    """
                    SELECT * FROM workflow_tasks
                    WHERE project_id = ? AND status != 'Done' AND due_date <= ?
                    ORDER BY due_date ASC
                    """,
                    (project_id, today),
                )
            )
