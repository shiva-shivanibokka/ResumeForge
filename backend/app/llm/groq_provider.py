"""Groq adapter (OpenAI-compatible chat completions)."""

from __future__ import annotations

from app.config import get_settings
from app.llm.base import LLMError, LLMResponse


class GroqProvider:
    name = "groq"

    def __init__(self, api_key: str, default_model: str):
        import groq

        self._sdk = groq
        settings = get_settings()
        self._client = groq.Groq(
            api_key=api_key,
            timeout=float(settings.request_timeout_s),
            max_retries=settings.llm_max_retries,
        )
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
        mdl = model or self._default_model
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            resp = self._client.chat.completions.create(
                model=mdl,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=messages,
            )
        except self._sdk.AuthenticationError as e:
            raise LLMError(str(e), provider=self.name, kind="auth") from e
        except self._sdk.RateLimitError as e:
            raise LLMError(str(e), provider=self.name, kind="rate_limit") from e
        except self._sdk.APITimeoutError as e:
            raise LLMError(str(e), provider=self.name, kind="timeout") from e
        except self._sdk.BadRequestError as e:
            raise LLMError(str(e), provider=self.name, kind="bad_request") from e
        except self._sdk.APIStatusError as e:
            kind = "server" if getattr(e, "status_code", 500) >= 500 else "unknown"
            raise LLMError(str(e), provider=self.name, kind=kind) from e
        except Exception as e:  # noqa: BLE001
            raise LLMError(str(e), provider=self.name, kind="unknown") from e

        text = (resp.choices[0].message.content or "").strip()
        usage = None
        if getattr(resp, "usage", None):
            usage = {
                "input_tokens": resp.usage.prompt_tokens,
                "output_tokens": resp.usage.completion_tokens,
            }
        return LLMResponse(text=text, model=mdl, provider=self.name, usage=usage)
