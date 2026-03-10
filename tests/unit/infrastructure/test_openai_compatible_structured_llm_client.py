import json

import requests

from strategic_alpha_engine.application.contracts import HypothesisPlannerPromptOutput
from strategic_alpha_engine.config import LLMSettings
from strategic_alpha_engine.infrastructure.llm import OpenAICompatibleStructuredLLMClient
from strategic_alpha_engine.prompts import load_prompt_asset


class _StubResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class _StubSession(requests.Session):
    def __init__(self, responses: list[_StubResponse]):
        super().__init__()
        self.responses = responses
        self.calls = 0
        self.requests: list[dict] = []

    def post(self, url, json=None, timeout=None):  # noqa: A002
        del url, timeout
        self.requests.append(json or {})
        response = self.responses[self.calls]
        self.calls += 1
        return response


def test_structured_llm_client_retries_schema_failures():
    prompt = load_prompt_asset("planner")
    session = _StubSession(
        [
            _StubResponse(
                200,
                {"choices": [{"message": {"content": '{"hypothesis": {"bad": "payload"}}'}}]},
            ),
            _StubResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "hypothesis": {
                                            "hypothesis_id": "hyp.test.001",
                                            "agenda_id": "agenda.test.001",
                                            "family": "momentum",
                                            "thesis_name": "Test momentum thesis",
                                            "economic_rationale": "A valid rationale long enough to satisfy the contract.",
                                            "expected_direction": "higher_signal_outperforms",
                                            "horizon": "medium",
                                            "target_region": "USA",
                                            "target_universe": "TOP3000",
                                            "market_context": "Cross-sectional equity momentum context.",
                                            "field_classes": ["price"],
                                            "preferred_update_cadences": ["daily"],
                                            "risk_notes": ["Use conservative normalization"],
                                            "evidence_requirements": ["Positive Sharpe"],
                                            "forbidden_patterns": ["missing_outer_rank"],
                                            "confidence": 0.6,
                                            "author": "stub_llm"
                                        },
                                        "planner_notes": ["Recovered after retry"]
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
        ]
    )
    client = OpenAICompatibleStructuredLLMClient(
        LLMSettings(base_url="http://127.0.0.1:8000/v1", model="test-model"),
        session=session,
    )

    result = client.generate_structured(
        asset=prompt,
        input_payload={"agenda": {"agenda_id": "agenda.test.001"}},
        output_model=HypothesisPlannerPromptOutput,
    )

    assert result.hypothesis.hypothesis_id == "hyp.test.001"
    assert session.calls == 2
    assert session.requests[0]["response_format"]["type"] == "json_schema"
    assert session.requests[0]["response_format"]["json_schema"]["name"] == "HypothesisPlannerPromptOutput"


def test_structured_llm_client_retries_empty_response_once():
    prompt = load_prompt_asset("planner")
    session = _StubSession(
        [
            _StubResponse(200, {"choices": [{"message": {"content": ""}}]}),
            _StubResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "hypothesis": {
                                            "hypothesis_id": "hyp.test.002",
                                            "agenda_id": "agenda.test.002",
                                            "family": "momentum",
                                            "thesis_name": "Second test thesis",
                                            "economic_rationale": "A valid rationale long enough to satisfy the contract.",
                                            "expected_direction": "higher_signal_outperforms",
                                            "horizon": "medium",
                                            "target_region": "USA",
                                            "target_universe": "TOP3000",
                                            "market_context": "Cross-sectional equity momentum context.",
                                            "field_classes": ["price"],
                                            "preferred_update_cadences": ["daily"],
                                            "risk_notes": ["Use conservative normalization"],
                                            "evidence_requirements": ["Positive Sharpe"],
                                            "forbidden_patterns": ["missing_outer_rank"],
                                            "confidence": 0.6,
                                            "author": "stub_llm"
                                        },
                                        "planner_notes": []
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
        ]
    )
    client = OpenAICompatibleStructuredLLMClient(
        LLMSettings(base_url="http://127.0.0.1:8000/v1", model="test-model"),
        session=session,
    )

    result = client.generate_structured(
        asset=prompt,
        input_payload={"agenda": {"agenda_id": "agenda.test.002"}},
        output_model=HypothesisPlannerPromptOutput,
    )

    assert result.hypothesis.agenda_id == "agenda.test.002"
    assert session.calls == 2
    assert session.requests[0]["response_format"]["type"] == "json_schema"


def test_structured_llm_client_falls_back_to_json_object_when_provider_rejects_json_schema():
    prompt = load_prompt_asset("planner")
    session = _StubSession(
        [
            _StubResponse(
                400,
                {"error": {"message": "response_format json_schema is not supported"}},
            ),
            _StubResponse(
                200,
                {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(
                                    {
                                        "hypothesis": {
                                            "hypothesis_id": "hyp.test.003",
                                            "agenda_id": "agenda.test.003",
                                            "family": "momentum",
                                            "thesis_name": "Third test thesis",
                                            "economic_rationale": "A valid rationale long enough to satisfy the contract.",
                                            "expected_direction": "higher_signal_outperforms",
                                            "horizon": "medium",
                                            "target_region": "USA",
                                            "target_universe": "TOP3000",
                                            "market_context": "Cross-sectional equity momentum context.",
                                            "field_classes": ["price"],
                                            "preferred_update_cadences": ["daily"],
                                            "risk_notes": ["Use conservative normalization"],
                                            "evidence_requirements": ["Positive Sharpe"],
                                            "forbidden_patterns": ["missing_outer_rank"],
                                            "confidence": 0.6,
                                            "author": "stub_llm"
                                        },
                                        "planner_notes": []
                                    }
                                )
                            }
                        }
                    ]
                },
            ),
        ]
    )
    client = OpenAICompatibleStructuredLLMClient(
        LLMSettings(base_url="http://127.0.0.1:8000/v1", model="test-model"),
        session=session,
    )

    result = client.generate_structured(
        asset=prompt,
        input_payload={"agenda": {"agenda_id": "agenda.test.003"}},
        output_model=HypothesisPlannerPromptOutput,
    )

    assert result.hypothesis.agenda_id == "agenda.test.003"
    assert session.calls == 2
    assert session.requests[0]["response_format"]["type"] == "json_schema"
    assert session.requests[1]["response_format"]["type"] == "json_object"
