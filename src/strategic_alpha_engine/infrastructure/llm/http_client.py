from __future__ import annotations

import json
from typing import Any
from urllib.parse import urljoin

import requests
from pydantic import ValidationError

from strategic_alpha_engine.config import LLMSettings
from strategic_alpha_engine.prompts import PromptAsset


class OpenAICompatibleStructuredLLMClient:
    def __init__(
        self,
        settings: LLMSettings,
        *,
        session: requests.Session | None = None,
    ):
        self.settings = settings
        self._session = session or requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def generate_structured(
        self,
        *,
        asset: PromptAsset,
        input_payload: dict,
        output_model: type,
    ):
        schema_retries = 0
        empty_retries = 0
        last_error: Exception | None = None

        while True:
            response = self._session.post(
                self._build_url("/chat/completions"),
                json=self._build_request_payload(
                    asset=asset,
                    input_payload=input_payload,
                    retry_error=last_error,
                ),
                timeout=self.settings.timeout_seconds,
            )
            if response.status_code >= 400:
                raise RuntimeError(
                    f"Structured LLM request failed with status {response.status_code}: {response.text[:240]}"
                )

            payload = self._decode_json(response)
            content = self._extract_content(payload)
            if not content.strip():
                if empty_retries >= 1:
                    raise RuntimeError("Structured LLM returned empty content twice")
                empty_retries += 1
                last_error = RuntimeError("empty_content")
                continue

            try:
                structured_payload = self._parse_json_object(content)
                return output_model.model_validate(structured_payload)
            except (json.JSONDecodeError, ValidationError) as exc:
                if schema_retries >= 2:
                    raise RuntimeError(f"Structured LLM output failed schema validation: {exc}") from exc
                schema_retries += 1
                last_error = exc

    def _build_request_payload(
        self,
        *,
        asset: PromptAsset,
        input_payload: dict,
        retry_error: Exception | None,
    ) -> dict[str, Any]:
        retry_note = (
            f"\nPrevious attempt failed: {type(retry_error).__name__}: {retry_error}"
            if retry_error is not None
            else ""
        )
        user_payload = {
            "prompt_id": asset.prompt_id,
            "role": str(asset.role),
            "purpose": asset.purpose,
            "input_contract": asset.input_contract,
            "output_contract": asset.output_contract,
            "return_rules": [
                "Return JSON only.",
                "Do not wrap the JSON in markdown fences.",
                "Ensure the JSON validates against the output contract exactly.",
            ],
            "input_payload": input_payload,
            "retry_context": retry_note.strip() or None,
        }
        return {
            "model": self.settings.model,
            "temperature": asset.temperature,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": asset.system_instructions,
                },
                {
                    "role": "user",
                    "content": json.dumps(user_payload, indent=2),
                },
            ],
        }

    def _build_url(self, path_or_url: str) -> str:
        if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
            return path_or_url
        return urljoin(self.settings.base_url.rstrip("/") + "/", path_or_url.lstrip("/"))

    @staticmethod
    def _decode_json(response: requests.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("Structured LLM response was not valid JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Structured LLM response JSON must be an object")
        return payload

    @staticmethod
    def _extract_content(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Structured LLM response did not include any choices")
        message = choices[0].get("message", {})
        if not isinstance(message, dict):
            raise RuntimeError("Structured LLM response choice message was malformed")
        content = message.get("content", "")
        if isinstance(content, list):
            chunks: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    chunks.append(str(item.get("text", "")))
            return "\n".join(chunks)
        return str(content)

    @staticmethod
    def _parse_json_object(content: str) -> dict[str, Any]:
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            if len(lines) >= 3:
                stripped = "\n".join(lines[1:-1]).strip()

        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            start_candidates = [idx for idx in (stripped.find("{"), stripped.find("[")) if idx != -1]
            if not start_candidates:
                raise
            start = min(start_candidates)
            end = max(stripped.rfind("}"), stripped.rfind("]"))
            if end == -1 or end <= start:
                raise
            payload = json.loads(stripped[start : end + 1])

        if not isinstance(payload, dict):
            raise json.JSONDecodeError("top-level JSON must be an object", stripped, 0)
        return payload
