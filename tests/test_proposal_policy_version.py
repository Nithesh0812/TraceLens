
import json

from app.storage.incident_repository import (
    FIX_PROPOSAL_POLICY_VERSION,
    IncidentRepository,
)


def test_old_proposal_is_not_returned(tmp_path):
    repository = IncidentRepository(tmp_path / "version.db")

    with repository.connect() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("""
            INSERT INTO fix_proposals
            (incident_id, proposal_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (
            "incident-old",
            json.dumps({
                "incident_id": "incident-old",
                "status": "proposed",
                "proposal": {"title": "Outdated fix"},
                "requires_human_review": True,
            }),
            "2026-11-16",
            "2026-11-16",
        ))

    assert repository.get_fix_proposal("incident-old") is None


def test_current_version_is_returned(tmp_path):
    repository = IncidentRepository(tmp_path / "version.db")

    result = {
        "incident_id": "incident-new",
        "status": "proposed",
        "proposal": {"title": "Review database metrics"},
        "requires_human_review": True,
    }

    with repository.connect() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("""
            INSERT INTO fix_proposals
            (incident_id, proposal_json, created_at, updated_at)
            VALUES (?, ?, ?, ?)
        """, (
            "incident-new",
            json.dumps({
                "policy_version": FIX_PROPOSAL_POLICY_VERSION,
                "result": result,
            }),
            "2026-11-16",
            "2026-11-16",
        ))

    assert repository.get_fix_proposal("incident-new") == result
