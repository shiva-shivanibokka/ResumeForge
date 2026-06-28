"""Anthropic adapter.

Note: temperature is intentionally NOT sent. The current default model
(claude-opus-4-8) rejects sampling parameters with a 400, so we steer via the
prompt instead — consistent across all listed Claude models.
"""

from __future__ import annotations

from app.config import get_settings
from app.llm.base import LLMError, LLMResponse


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, default_model: str):
        import anthropic

        self._sdk = anthropic
        settings = get_settings()
        self._client = anthropic.Anthropic(
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
        try:
            kwargs: dict = {
                "model": mdl,
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            }
            if system:
                kwargs["system"] = system
            resp = self._client.messages.create(**kwargs)
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
        except Exception as e:  # noqa: BLE001 - normalize anything unexpected
            raise LLMError(str(e), provider=self.name, kind="unknown") from e

        text = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text = block.text
                break
        usage = None
        if getattr(resp, "usage", None):
            usage = {
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            }
        return LLMResponse(text=text.strip(), model=mdl, provider=self.name, usage=usage)
