from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol


class GenerationError(RuntimeError):
    pass


class TextGenerator(Protocol):
    def generate(self, system: str, user: str, *, temperature: float = 0.7) -> str: ...


@dataclass
class CompatibleChatProvider:
    """Minimal OpenAI-compatible HTTP provider without a runtime SDK dependency."""

    api_key: str
    model: str
    endpoint: str = "https://api.openai.com/v1/chat/completions"
    timeout: int = 180

    def generate(self, system: str, user: str, *, temperature: float = 0.7) -> str:
        if not self.api_key.strip():
            raise GenerationError("AI API 키가 설정되지 않았습니다.")
        payload = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature,
        }, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint, data=payload, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise GenerationError(f"AI 서버 오류 HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise GenerationError(f"AI 서버에 연결할 수 없습니다: {exc}") from exc
        try:
            return body["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise GenerationError("AI 서버 응답 형식을 해석할 수 없습니다.") from exc


def parse_json_response(value: str) -> dict:
    value = value.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", value, re.DOTALL | re.IGNORECASE)
    if fenced:
        value = fenced.group(1)
    try:
        result = json.loads(value)
    except json.JSONDecodeError as exc:
        start, end = value.find("{"), value.rfind("}")
        if start >= 0 and end > start:
            try:
                result = json.loads(value[start:end + 1])
            except json.JSONDecodeError:
                raise GenerationError("AI가 유효한 JSON 계획을 반환하지 않았습니다.") from exc
        else:
            raise GenerationError("AI가 유효한 JSON 계획을 반환하지 않았습니다.") from exc
    if not isinstance(result, dict):
        raise GenerationError("AI 계획 응답은 JSON 객체여야 합니다.")
    return result

