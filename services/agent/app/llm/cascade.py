"""
Multi-provider LLM cascade with automatic failover.
Ported from huquqai/lib/ai/chat-provider.ts
"""

import logging
import httpx

from app.llm.providers import ProviderConfig, get_providers
from app.config import settings

logger = logging.getLogger(__name__)


class AllProvidersFailed(Exception):
    pass


class LLMCascade:
    def __init__(self):
        self.providers = get_providers(
            cerebras_key=settings.cerebras_api_key,
            groq_key=settings.groq_api_key,
            mistral_key=settings.mistral_api_key,
        )
        if not self.providers:
            logger.warning("No LLM providers configured!")
        else:
            names = [p.name for p in self.providers]
            logger.info(f"LLM cascade initialized: {' → '.join(names)}")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """
        Send a chat request, trying each provider in order.
        Returns dict with: content, tool_calls, provider, model, tokens_in, tokens_out
        """
        if not self.providers:
            raise AllProvidersFailed("No providers configured")

        temp = temperature if temperature is not None else settings.default_temperature
        tokens = max_tokens if max_tokens is not None else settings.default_max_tokens
        last_error = None

        for provider in self.providers:
            try:
                result = await self._call_provider(provider, messages, tools, temp, tokens)
                logger.info(
                    f"[{provider.name}] Success — "
                    f"tokens: {result['tokens_in']}+{result['tokens_out']}"
                )
                return result
            except Exception as e:
                last_error = e
                logger.warning(f"[{provider.name}] Failed: {e}, trying next...")
                continue

        raise AllProvidersFailed(f"All providers failed. Last error: {last_error}")

    async def _call_provider(
        self,
        provider: ProviderConfig,
        messages: list[dict],
        tools: list[dict] | None,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Call a single OpenAI-compatible provider."""
        payload: dict = {
            "model": provider.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                provider.endpoint,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {provider.api_key}",
                },
                json=payload,
                timeout=30,
            )

        if response.status_code == 429:
            raise Exception(f"Rate limited (429)")
        if response.status_code in (401, 403):
            raise Exception(f"Auth error ({response.status_code})")
        if response.status_code != 200:
            raise Exception(f"API error {response.status_code}: {response.text[:200]}")

        data = response.json()
        choice = data["choices"][0]
        usage = data.get("usage", {})

        return {
            "content": choice["message"].get("content", ""),
            "tool_calls": choice["message"].get("tool_calls"),
            "finish_reason": choice.get("finish_reason"),
            "provider": provider.name,
            "model": provider.model,
            "tokens_in": usage.get("prompt_tokens", 0),
            "tokens_out": usage.get("completion_tokens", 0),
        }

    def get_available_providers(self) -> list[str]:
        return [p.name for p in self.providers]


# Singleton
_cascade: LLMCascade | None = None


def get_cascade() -> LLMCascade:
    global _cascade
    if _cascade is None:
        _cascade = LLMCascade()
    return _cascade
