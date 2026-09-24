"""
SQLite storage for use cases, saved assessment packages and monthly value actuals
"""

from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import os
import sqlite3

from src.sample_data import new_use_case


def data_dir() -> Path:
    """App folder by default; NAVIGATOR_DATA_DIR overrides it (used by tests)"""
    return Path(os.environ.get("NAVIGATOR_DATA_DIR", Path(__file__).resolve().parent.parent))


class Database:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or data_dir() / "navigator.db")
        self._init_schema()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self):
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS use_cases (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS assessments (
                    use_case_id INTEGER PRIMARY KEY REFERENCES use_cases(id) ON DELETE CASCADE,
                    package TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS value_actuals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    use_case_id INTEGER NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
                    month TEXT NOT NULL,
                    hours_saved REAL NOT NULL DEFAULT 0,
                    adoption_pct REAL NOT NULL DEFAULT 0,
                    actual_cost REAL NOT NULL DEFAULT 0,
                    notes TEXT DEFAULT '',
                    UNIQUE (use_case_id, month)
                );
                CREATE TABLE IF NOT EXISTS control_evidence (
                    use_case_id INTEGER NOT NULL REFERENCES use_cases(id) ON DELETE CASCADE,
                    control TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Not started',
                    owner TEXT DEFAULT '',
                    due_date TEXT DEFAULT '',
                    evidence TEXT DEFAULT '',
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (use_case_id, control)
                );
            """)

    # ------------------------------------------------------------ use cases
    def save_use_case(self, uc: Dict[str, Any], use_case_id: Optional[int] = None) -> int:
        now = datetime.now().isoformat(timespec="seconds")
        data = json.dumps(uc)
        with self._connect() as conn:
            if use_case_id:
                conn.execute("UPDATE use_cases SET name=?, data=?, updated_at=? WHERE id=?",
                             (uc["name"], data, now, use_case_id))
                return use_case_id
            cur = conn.execute("INSERT INTO use_cases (name, data, created_at, updated_at) VALUES (?, ?, ?, ?)",
                               (uc["name"], data, now, now))
            return cur.lastrowid

    def get_use_case(self, use_case_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT data FROM use_cases WHERE id=?", (use_case_id,)).fetchone()
        # Merge onto defaults so older records pick up new fields
        return new_use_case(**json.loads(row["data"])) if row else None

    def list_use_cases(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, data FROM use_cases ORDER BY id").fetchall()
        return [{"id": r["id"], **new_use_case(**json.loads(r["data"]))} for r in rows]

    def delete_use_case(self, use_case_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM use_cases WHERE id=?", (use_case_id,))

    # ---------------------------------------------------------- assessments
    def save_assessment(self, use_case_id: int, package: Dict[str, Any]):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO assessments (use_case_id, package, mode, created_at) VALUES (?, ?, ?, ?)",
                (use_case_id, json.dumps(package, default=str), package.get("mode", ""),
                 datetime.now().isoformat(timespec="seconds")),
            )

    def get_assessment(self, use_case_id: int) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute("SELECT package, created_at FROM assessments WHERE use_case_id=?",
                               (use_case_id,)).fetchone()
        if not row:
            return None
        package = json.loads(row["package"])
        package["saved_at"] = row["created_at"]
        return package

    def delete_assessment(self, use_case_id: int):
        with self._connect() as conn:
            conn.execute("DELETE FROM assessments WHERE use_case_id=?", (use_case_id,))

    # --------------------------------------------------------- value actuals
    def upsert_actual(self, use_case_id: int, month: str, hours_saved: float, adoption_pct: float,
                      actual_cost: float, notes: str = ""):
        with self._connect() as conn:
            conn.execute("""
                INSERT INTO value_actuals (use_case_id, month, hours_saved, adoption_pct, actual_cost, notes)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (use_case_id, month) DO UPDATE SET
                    hours_saved=excluded.hours_saved, adoption_pct=excluded.adoption_pct,
                    actual_cost=excluded.actual_cost, notes=excluded.notes
            """, (use_case_id, month, hours_saved, adoption_pct, actual_cost, notes))

    def get_actuals(self, use_case_id: int) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT month, hours_saved, adoption_pct, actual_cost, notes FROM value_actuals "
                "WHERE use_case_id=? ORDER BY month", (use_case_id,)).fetchall()
        return [dict(r) for r in rows]

    def delete_actual(self, use_case_id: int, month: str):
        with self._connect() as conn:
            conn.execute("DELETE FROM value_actuals WHERE use_case_id=? AND month=?", (use_case_id, month))

    # ------------------------------------------------------ control evidence
    def save_evidence(self, use_case_id: int, rows: List[Dict[str, Any]]):
        """Upsert evidence records keyed by control text"""
        now = datetime.now().isoformat(timespec="seconds")
        with self._connect() as conn:
            for r in rows:
                due = r.get("due_date")
                conn.execute("""
                    INSERT INTO control_evidence (use_case_id, control, status, owner, due_date, evidence, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT (use_case_id, control) DO UPDATE SET
                        status=excluded.status, owner=excluded.owner, due_date=excluded.due_date,
                        evidence=excluded.evidence, updated_at=excluded.updated_at
                """, (use_case_id, r["control"], r.get("status") or "Not started", r.get("owner") or "",
                      due.isoformat() if hasattr(due, "isoformat") else (due or ""), r.get("evidence") or "", now))

    def get_evidence(self, use_case_id: int) -> Dict[str, Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT control, status, owner, due_date, evidence, updated_at FROM control_evidence "
                "WHERE use_case_id=?", (use_case_id,)).fetchall()
        return {r["control"]: dict(r) for r in rows}

    # ------------------------------------------------------------ samples
    def load_samples(self, use_cases: List[Dict[str, Any]], actuals: Dict[str, List[Dict[str, Any]]],
                     evidence: Optional[Dict[str, List[Dict[str, Any]]]] = None) -> int:
        """Insert sample use cases that are not already present (matched by name)"""
        existing = {uc["name"]: uc["id"] for uc in self.list_use_cases()}
        evidence = evidence or {}
        added = 0
        for uc in use_cases:
            if uc["name"] in existing:
                # Samples loaded by an older version: add evidence only where none was recorded yet
                if not self.get_evidence(existing[uc["name"]]):
                    self.save_evidence(existing[uc["name"]], evidence.get(uc["name"], []))
                continue
            uc_id = self.save_use_case(uc)
            for row in actuals.get(uc["name"], []):
                self.upsert_actual(uc_id, **row)
            self.save_evidence(uc_id, evidence.get(uc["name"], []))
            added += 1
        return added
