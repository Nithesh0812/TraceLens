import sqlite3
import json
from datetime import datetime, timezone
from app.detection.incident_manager import ManagedIncident
from app.detection.rules import Severity


# Increment whenever remediation verification rules change.
FIX_PROPOSAL_POLICY_VERSION = 2

class IncidentRepository:
    def __init__(self, db_path="tracelens.db"):
        self.db_path = str(db_path)
        self.initialize()

    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self):
        with self.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id TEXT PRIMARY KEY,
                    incident_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    status TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolved_at TEXT,
                    occurrences INTEGER NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_incidents_status
                ON incidents(status)
            """)

            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS
                idx_one_active_incident_per_type
                ON incidents(incident_type)
                WHERE status = 'active'
            """)

            # New table for correlated log evidence
            conn.execute("""
                CREATE TABLE IF NOT EXISTS incident_evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    seconds_from_incident REAL NOT NULL,

                    FOREIGN KEY (incident_id)
                        REFERENCES incidents(id),

                    UNIQUE (
                        incident_id,
                        timestamp,
                        level,
                        message
                    )
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS
                idx_evidence_incident
                ON incident_evidence(incident_id)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS investigations (
                incident_id TEXT PRIMARY KEY,
                report_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,

                FOREIGN KEY (incident_id)
                    REFERENCES incidents(id)
                    ON DELETE CASCADE
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS fix_proposals (
                    incident_id TEXT PRIMARY KEY,
                    proposal_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    FOREIGN KEY (incident_id)
                        REFERENCES incidents(id)
                        ON DELETE CASCADE
                )
            """)


    def save(self, incident: dict, evidence=None):
        """
        Upsert an incident and save its log evidence
        in one SQLite transaction.
        """
        if evidence is None:
            evidence = []

        with self.connect() as conn:
            conn.execute("""
                INSERT INTO incidents (
                    id, incident_type, severity, status,
                    message, metric_value, created_at,
                    updated_at, resolved_at, occurrences
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)

                ON CONFLICT(id) DO UPDATE SET
                    severity = excluded.severity,
                    status = excluded.status,
                    message = excluded.message,
                    metric_value = excluded.metric_value,
                    updated_at = excluded.updated_at,
                    resolved_at = excluded.resolved_at,
                    occurrences = excluded.occurrences
            """, (
                incident["id"],
                incident["incident_type"],
                incident["severity"],
                incident["status"],
                incident["message"],
                incident["metric_value"],
                incident["created_at"],
                incident["updated_at"],
                incident["resolved_at"],
                incident["occurrences"],
            ))

            for log in evidence:
                cursor = conn.execute("""
                    INSERT OR IGNORE INTO incident_evidence (
                        incident_id,
                        timestamp,
                        level,
                        message,
                        seconds_from_incident
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    incident["id"],
                    log["timestamp"],
                    log["level"],
                    log["message"],
                    log["seconds_from_incident"],
                ))

                # Invalidate old proposals if new
                # evidence was actually inserted.
                if cursor.rowcount > 0:
                    conn.execute("""
                        DELETE FROM fix_proposals
                        WHERE incident_id = ?
                    """, (incident["id"],))


    def list_all(self):
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM incidents
                ORDER BY created_at DESC
            """).fetchall()

            return [dict(row) for row in rows]

    def list_active(self):
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT * FROM incidents
                WHERE status = 'active'
                ORDER BY created_at DESC
            """).fetchall()

            return [dict(row) for row in rows]

    def get_by_id(self, incident_id: str):
        with self.connect() as conn:
            row = conn.execute(
                "SELECT * FROM incidents WHERE id = ?",
                (incident_id,),
            ).fetchone()

            return dict(row) if row else None

    def list_evidence(self, incident_id: str):
        """Retrieve permanently stored incident evidence."""
        with self.connect() as conn:
            rows = conn.execute("""
                SELECT
                    id,
                    incident_id,
                    timestamp,
                    level,
                    message,
                    seconds_from_incident
                FROM incident_evidence
                WHERE incident_id = ?
                ORDER BY timestamp DESC, id DESC
            """, (incident_id,)).fetchall()

            return [dict(row) for row in rows]

    def load_manager_state(self, manager):
        """Restore active incidents after a restart."""
        manager.incidents.clear()

        for row in self.list_active():
            manager.incidents[row["incident_type"]] = (
                ManagedIncident(
                    id=row["id"],
                    incident_type=row["incident_type"],
                    severity=Severity(row["severity"]),
                    status=row["status"],
                    message=row["message"],
                    metric_value=row["metric_value"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    resolved_at=row["resolved_at"],
                    occurrences=row["occurrences"],
                )
            )
    def save_investigation(self,incident_id: str,report: dict,):
        """Save or update a verified investigation."""

        if self.get_by_id(incident_id) is None:
            raise ValueError("Incident not found")

        timestamp = datetime.now(timezone.utc).isoformat()
        report_json = json.dumps(report)

        with self.connect() as conn:
            conn.execute("""
                INSERT INTO investigations (
                    incident_id,
                    report_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?)

                ON CONFLICT(incident_id) DO UPDATE SET
                    report_json = excluded.report_json,
                    updated_at = excluded.updated_at
            """, (
                incident_id,
                report_json,
                timestamp,
                timestamp,
            ))

            # Any newly saved investigation invalidates
            # the previously proposed remediation.
            conn.execute("""
                DELETE FROM fix_proposals
                WHERE incident_id = ?
            """, (incident_id,))



    def get_investigation(self, incident_id: str):
        """Retrieve the saved investigation for an incident."""

        with self.connect() as conn:
            row = conn.execute("""
                SELECT report_json
                FROM investigations
                WHERE incident_id = ?
            """, (incident_id,)).fetchone()

            if row is None:
                return None

            return json.loads(row["report_json"])

    def save_fix_proposal(
        self,
        incident_id: str,
        proposal: dict,
        *,
        expected_investigation: dict,
        expected_evidence_ids: list[int],
    ):
        """Save only if the investigation and evidence are unchanged."""

        if (
            proposal.get("incident_id") != incident_id
            or proposal.get("status") != "proposed"
            or proposal.get("proposal") is None
            or proposal.get("requires_human_review") is not True
        ):
            raise ValueError("Invalid fix proposal")

        timestamp = datetime.now(timezone.utc).isoformat()

        with self.connect() as conn:
            # Serialize writes while checking the current snapshot.
            conn.execute("BEGIN IMMEDIATE")

            investigation = conn.execute("""
                SELECT report_json
                FROM investigations
                WHERE incident_id = ?
            """, (incident_id,)).fetchone()

            if (
                investigation is None
                or json.loads(investigation["report_json"])
                != expected_investigation
            ):
                raise ValueError(
                    "Investigation changed during proposal generation"
                )

            rows = conn.execute("""
                SELECT id FROM incident_evidence
                WHERE incident_id = ?
                ORDER BY timestamp DESC, id DESC
                LIMIT 20
            """, (incident_id,)).fetchall()

            current_evidence_ids = [
                row["id"] for row in rows
            ]

            if current_evidence_ids != expected_evidence_ids:
                raise ValueError(
                    "Incident evidence changed during generation"
                )

            conn.execute("""
                INSERT INTO fix_proposals (
                    incident_id,
                    proposal_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    proposal_json = excluded.proposal_json,
                    updated_at = excluded.updated_at
            """, (
                incident_id,
                json.dumps({ "policy_version": FIX_PROPOSAL_POLICY_VERSION,
    "result": proposal,}),
                timestamp,
                timestamp,
            ))

    
    def get_fix_proposal(self, incident_id: str):
        """Retrieve a proposal generated under the current policy."""

        with self.connect() as conn:
            row = conn.execute("""
                SELECT proposal_json
                FROM fix_proposals
                WHERE incident_id = ?
            """, (incident_id,)).fetchone()

            if row is None:
                return None

            try:
                stored = json.loads(row["proposal_json"])
            except (TypeError, ValueError):
                return None

            if not isinstance(stored, dict):
                return None

            if stored.get("policy_version") != (
                FIX_PROPOSAL_POLICY_VERSION
            ):
                return None

            result = stored.get("result")

            if not isinstance(result, dict):
                return None

            if (
                result.get("incident_id") != incident_id
                or result.get("status") != "proposed"
                or result.get("requires_human_review") is not True
            ):
                return None

            return result


    def delete_fix_proposal(self, incident_id: str):
        """Invalidate a saved fix proposal."""

        with self.connect() as conn:
            conn.execute("""
                DELETE FROM fix_proposals
                WHERE incident_id = ?
            """, (incident_id,))