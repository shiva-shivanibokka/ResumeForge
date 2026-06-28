"""Google Gemini adapter (google-genai SDK)."""

from __future__ import annotations

from app.llm.base import LLMError, LLMResponse


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, default_model: str):
        from google import genai

        self._genai = genai
        self._client = genai.Client(api_key=api_key)
        self._default_model = default_model

    def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.2,
        model: str | None = None,
    ) -> LLMResponse:
        from google.genai import types

        mdl = model or self._default_model
        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            system_instruction=system or None,
        )
        try:
            resp = self._client.models.generate_content(
                model=mdl, contents=prompt, config=config
            )
        except self._genai.errors.APIError as e:
            code = getattr(e, "code", 0) or 0
            if code in (401, 403):
                kind = "auth"
            elif code == 429:
                kind = "rate_limit"
            elif code == 400:
                kind = "bad_request"
            elif code >= 500:
                kind = "server"
            else:
                kind = "unknown"
            raise LLMError(str(e), provider=self.name, kind=kind) from e
        except Exception as e:  # noqa: BLE001
            raise LLMError(str(e), provider=self.name, kind="unknown") from e

        text = (getattr(resp, "text", None) or "").strip()
        usage = None
        meta = getattr(resp, "usage_metadata", None)
        if meta:
            usage = {
                "input_tokens": getattr(meta, "prompt_token_count", None),
                "output_tokens": getattr(meta, "candidates_token_count", None),
            }
        return LLMResponse(text=text, model=mdl, provider=self.name, usage=usage)
