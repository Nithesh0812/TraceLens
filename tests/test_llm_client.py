
import json

import httpx
import pytest

from app.investigation.llm_client import (
    LLMInvestigator,
    LLMInvestigationError,
)


def sample_context():
    return {
        "incident": {
            "id": "incident-123",
            "incident_type": "high_error_rate",
            "severity": "critical",
            "metric_value": 0.12,
        },
        "evidence": [
            {
                "evidence_id": 7,
                "level": "ERROR",
                "message": "Database connection failed",
            }
        ],
    }


def mock_client(report):
    def handler(request):
        assert request.url.path.endswith(
            "/chat/completions"
        )

        body = json.loads(request.content)

        assert body["model"] == "test-model"
        
        response_format = body["response_format"]

        assert response_format["type"] == "json_schema"
        assert response_format["json_schema"]["strict"] is True

        schema = response_format["json_schema"]["schema"]

        assert schema["properties"]["confidence"]["enum"] == [
            "low", "medium", "high"
        ]

        assert schema["properties"]["next_steps"]["type"] == "array"
        assert schema["additionalProperties"] is False

        return httpx.Response(
            200,
            json={
                "choices": [{
                    "message": {
                        "content": json.dumps(report)
                    }
                }]
            },
        )

    return httpx.Client(
        transport=httpx.MockTransport(handler)
    )


def test_successful_llm_investigation():
    response = {
        "summary": "Elevated HTTP errors were detected.",
        "possible_cause": "Database connectivity issue",
        "confidence": "medium",
        "evidence_ids": [7],
        "next_steps": [
            "Inspect PostgreSQL connection metrics"
        ],
        "insufficient_evidence": False,
    }

    with mock_client(response) as client:
        investigator = LLMInvestigator(
            api_key="test-key",
            model="test-model",
            client=client,
        )

        result = investigator.investigate(
            sample_context()
        )

    assert result.confidence == "medium"
    assert result.evidence_ids == [7]
    assert result.insufficient_evidence is False


def test_missing_evidence_abstains():
    investigator = LLMInvestigator()

    context = sample_context()
    context["evidence"] = []

    result = investigator.investigate(context)

    assert result.insufficient_evidence is True
    assert result.confidence == "low"
    assert result.evidence_ids == []
    assert result.possible_cause is None


def test_invalid_evidence_id_rejected():
    response = {
        "summary": "HTTP failures detected",
        "possible_cause": "Unknown",
        "confidence": "medium",
        "evidence_ids": [999],
        "next_steps": ["Inspect logs"],
        "insufficient_evidence": False,
    }

    with mock_client(response) as client:
        investigator = LLMInvestigator(
            api_key="test-key",
            model="test-model",
            client=client,
        )

        with pytest.raises(LLMInvestigationError):
            investigator.investigate(sample_context())


def test_invalid_json_rejected():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "choices": [{
                    "message": {"content": "not valid json"}
                }]
            },
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        investigator = LLMInvestigator(
            api_key="test-key",
            model="test-model",
            client=client,
        )

        with pytest.raises(LLMInvestigationError):
            investigator.investigate(sample_context())


def test_provider_failure():
    def handler(request):
        return httpx.Response(
            503,
            json={"error": "provider unavailable"},
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler)
    ) as client:
        investigator = LLMInvestigator(
            api_key="test-key",
            model="test-model",
            client=client,
        )

        with pytest.raises(LLMInvestigationError):
            investigator.investigate(sample_context())


def test_missing_configuration(monkeypatch):
    monkeypatch.delenv(
        "TRACELENS_LLM_API_KEY", raising=False
    )
    monkeypatch.delenv(
        "TRACELENS_LLM_MODEL", raising=False
    )

    investigator = LLMInvestigator()

    with pytest.raises(LLMInvestigationError):
        investigator.investigate(sample_context())
