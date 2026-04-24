"""
Provider-agnostic OpenAI-compatible client.

Switch providers via .env:
  AI_PROVIDER=openai       AI_MODEL=gpt-5-mini          (uses OPENAI_API_KEY)
  AI_PROVIDER=groq         AI_MODEL=llama-3.3-70b-versatile   (uses GROQ_API_KEY)
  AI_PROVIDER=openrouter   AI_MODEL=anthropic/claude-haiku-4.5 (uses OPENROUTER_API_KEY)

All three providers expose an OpenAI-compatible /chat/completions endpoint,
so the same SDK works — only base_url + api_key + model differ.
"""
from openai import AsyncOpenAI
from config import settings

_PROVIDER_CONFIG = {
    "openai": {
        "base_url": None,  # SDK default
        "key_attr": "OPENAI_API_KEY",
    },
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "key_attr": "GROQ_API_KEY",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "key_attr": "OPENROUTER_API_KEY",
    },
}


def _build_client() -> AsyncOpenAI:
    provider = (settings.AI_PROVIDER or "openai").lower().strip()
    conf = _PROVIDER_CONFIG.get(provider, _PROVIDER_CONFIG["openai"])
    api_key = getattr(settings, conf["key_attr"], "") or settings.OPENAI_API_KEY
    kwargs = {"api_key": api_key}
    if conf["base_url"]:
        kwargs["base_url"] = conf["base_url"]
    return AsyncOpenAI(**kwargs)


client = _build_client()
MODEL = settings.AI_MODEL or "gpt-5-mini"


def _is_reasoning_model(model: str) -> bool:
    """OpenAI reasoning models (gpt-5, o-series) need max_completion_tokens + reasoning_effort.
    Everything else (gpt-4o, Groq Llama, Claude via OpenRouter, Gemini) uses max_tokens + temperature."""
    m = model.lower()
    return m.startswith(("gpt-5", "o1", "o3", "o4"))


def build_completion_params(
    *,
    max_tokens: int,
    temperature: float = 0.3,
    json_mode: bool = False,
) -> dict:
    """Returns kwargs compatible with the current model's param requirements."""
    params: dict = {"model": MODEL}
    if _is_reasoning_model(MODEL):
        params["max_completion_tokens"] = max_tokens
        params["reasoning_effort"] = "minimal"
        # gpt-5 series ignores/rejects temperature — don't send it
    else:
        params["max_tokens"] = max_tokens
        params["temperature"] = temperature
    if json_mode:
        params["response_format"] = {"type": "json_object"}
    return params
