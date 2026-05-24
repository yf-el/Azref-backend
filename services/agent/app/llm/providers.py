"""
LLM provider configurations.
"""

from dataclasses import dataclass


@dataclass
class ProviderConfig:
    name: str
    model: str
    api_key: str
    endpoint: str
    priority: int


def get_providers(
    cerebras_key: str = "",
    groq_key: str = "",
    mistral_key: str = "",
) -> list[ProviderConfig]:
    """Return enabled providers sorted by priority."""
    all_providers = [
        ProviderConfig(
            name="groq",
            model="meta-llama/llama-4-scout-17b-16e-instruct",
            api_key=groq_key,
            endpoint="https://api.groq.com/openai/v1/chat/completions",
            priority=1,
        ),
        ProviderConfig(
            name="cerebras",
            model="qwen-3-235b-a22b-instruct-2507",
            api_key=cerebras_key,
            endpoint="https://api.cerebras.ai/v1/chat/completions",
            priority=2,
        ),
        ProviderConfig(
            name="mistral",
            model="mistral-small-latest",
            api_key=mistral_key,
            endpoint="https://api.mistral.ai/v1/chat/completions",
            priority=3,
        ),
    ]

    enabled = [p for p in all_providers if p.api_key]
    enabled.sort(key=lambda p: p.priority)
    return enabled
