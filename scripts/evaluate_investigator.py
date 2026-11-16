
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from app.detection.incident_manager import IncidentManager
from app.investigation.context_builder import (
    InvestigationContextBuilder,
)
from app.investigation.evidence_verifier import EvidenceVerifier
from app.investigation.llm_client import (
    LLMInvestigator,
    LLMInvestigationError,
)
from app.storage.incident_repository import IncidentRepository


SCENARIOS = [
    {
        "name": "database_failure",
        "metrics": {
            "error_rate": 0.15,
            "average_latency_ms": 200.0,
        },
        "incident_type": "high_error_rate",
        "logs": [
            ("ERROR", "Database connection unavailable"),
            ("ERROR", "HTTP 500 during /jobs database operation"),
        ],
        "expected": "possible_cause",
    },
    {
        "name": "high_latency",
        "metrics": {
            "error_rate": 0.0,
            "average_latency_ms": 1800.0,
        },
        "incident_type": "high_latency",
        "logs": [
            ("WARNING", "GET /jobs completed in 1800 ms"),
            ("WARNING", "Request duration exceeded threshold"),
        ],
        "expected": "cautious",
    },
    {
        "name": "unrelated_warnings",
        "metrics": {
            "error_rate": 0.15,
            "average_latency_ms": 200.0,
        },
        "incident_type": "high_error_rate",
        "logs": [
            ("WARNING", "Invalid login credentials"),
            ("WARNING", "Authentication token expired"),
        ],
        "expected": "abstain",
    },
    {
        "name": "no_evidence",
        "metrics": {
            "error_rate": 0.15,
            "average_latency_ms": 200.0,
        },
        "incident_type": "high_error_rate",
        "logs": [],
        "expected": "abstain",
    },
]


def create_context(scenario, directory):
    db_path = Path(directory) / "evaluation.db"

    repository = IncidentRepository(db_path)
    manager = IncidentManager()

    events = manager.process_metrics(scenario["metrics"])

    incident = next(
        event["incident"]
        for event in events
        if event["incident"]["incident_type"]
        == scenario["incident_type"]
    )

    timestamp = datetime.now(timezone.utc).isoformat()

    evidence = [
        {
            "timestamp": timestamp,
            "level": level,
            "message": message,
            "seconds_from_incident": 0.0,
        }
        for level, message in scenario["logs"]
    ]

    repository.save(incident, evidence)

    return InvestigationContextBuilder(
        repository
    ).build(incident["id"])


def assess_report(result, context, expected):
    """
    Deterministic checks only.
    Semantic grounding still requires human review.
    """
    report = result.report

    allowed_ids = {
        item["evidence_id"]
        for item in context["evidence"]
    }

    checks = {
        "valid_citations": (
            set(report.evidence_ids).issubset(allowed_ids)
        ),
        "confidence_safeguard": (
            report.confidence != "high"
        ),
        "has_next_steps": bool(report.next_steps),
        "abstention_consistent": (
            not report.insufficient_evidence
            or (
                report.confidence == "low"
                and report.possible_cause is None
            )
        ),
    }

    if expected == "abstain":
        checks["expected_abstention"] = (
            report.insufficient_evidence
            and report.possible_cause is None
        )

    return checks


def main():
    investigator = LLMInvestigator()
    verifier = EvidenceVerifier()

    all_results = []

    for scenario in SCENARIOS:
        print(f"\n=== {scenario['name']} ===")

        with TemporaryDirectory() as directory:
            context = create_context(scenario, directory)

            try:
                raw_report = investigator.investigate(context)
                verified = verifier.verify(raw_report, context)

            except (LLMInvestigationError, ValueError) as exc:
                print("Evaluation error:", type(exc).__name__)
                all_results.append({
                    "scenario": scenario["name"],
                    "status": "error",
                    "error_type": type(exc).__name__,
                })
                continue

            checks = assess_report(
                verified,
                context,
                scenario["expected"],
            )

            result = {
                "scenario": scenario["name"],
                "status": (
                    "pass"
                    if all(checks.values())
                    else "needs_review"
                ),
                "expected_behavior": scenario["expected"],
                "checks": checks,
                "report": verified.report.model_dump(),
                "verification_warnings": verified.warnings,
                "human_review_required": True,
            }

            all_results.append(result)

            print(json.dumps(result, indent=2))

    print("\n=== EVALUATION SUMMARY ===")

    for result in all_results:
        print(
            f"{result['scenario']}: {result['status']}"
        )

    print(
        "\nNote: Automatic PASS does not establish "
        "semantic correctness or causality."
    )


if __name__ == "__main__":
    main()
