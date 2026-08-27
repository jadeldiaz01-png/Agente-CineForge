from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable
from urllib import request as urlrequest


class AIProvider(StrEnum):
    NVIDIA_NIM = "nvidia_nim"
    HUGGINGFACE = "huggingface"
    GEMINI = "gemini"
    GROQ = "groq"


@dataclass(frozen=True)
class AIProviderConfig:
    provider: AIProvider
    base_url: str
    api_key: str
    model: str
    enabled: bool = False
    free_tier: bool = False
    priority: int = 100


@dataclass(frozen=True)
class AIRequest:
    task: str
    prompt: str
    system: str = "You are a precise production assistant."
    max_tokens: int = 800
    temperature: float = 0.2


@dataclass(frozen=True)
class AIResponse:
    ok: bool
    provider: str
    model: str
    text: str = ""
    status: str = "UNKNOWN"
    error: str | None = None
    raw_response: dict | None = None


JsonTransport = Callable[[str, str, dict, dict[str, str]], dict]


def _default_transport(method: str, url: str, payload: dict, headers: dict[str, str]) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(url, data=data, method=method, headers=headers)
    with urlrequest.urlopen(req, timeout=90) as response:
        return json.loads(response.read().decode("utf-8"))


def load_provider_configs_from_env() -> list[AIProviderConfig]:
    return [
        AIProviderConfig(
            provider=AIProvider.NVIDIA_NIM,
            base_url=os.getenv("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1"),
            api_key=os.getenv("NVIDIA_NIM_API_KEY", ""),
            model=os.getenv("NVIDIA_NIM_MODEL", "nvidia/nemotron-3-ultra-550b-a55b"),
            enabled=_env_bool("NVIDIA_NIM_ENABLED"),
            priority=int(os.getenv("NVIDIA_NIM_PRIORITY", "10")),
        ),
        AIProviderConfig(
            provider=AIProvider.GROQ,
            base_url=os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            api_key=os.getenv("GROQ_API_KEY", ""),
            model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
            enabled=_env_bool("GROQ_ENABLED"),
            free_tier=True,
            priority=int(os.getenv("GROQ_PRIORITY", "20")),
        ),
        AIProviderConfig(
            provider=AIProvider.HUGGINGFACE,
            base_url=os.getenv("HF_INFERENCE_BASE_URL", "https://router.huggingface.co/v1"),
            api_key=os.getenv("HF_TOKEN", ""),
            model=os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct"),
            enabled=_env_bool("HF_INFERENCE_ENABLED"),
            free_tier=True,
            priority=int(os.getenv("HF_PRIORITY", "30")),
        ),
        AIProviderConfig(
            provider=AIProvider.GEMINI,
            base_url=os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai"),
            api_key=os.getenv("GEMINI_API_KEY", ""),
            model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
            enabled=_env_bool("GEMINI_ENABLED"),
            free_tier=True,
            priority=int(os.getenv("GEMINI_PRIORITY", "40")),
        ),
    ]


class AIProviderGateway:
    def __init__(self, configs: list[AIProviderConfig], transport: JsonTransport | None = None) -> None:
        self.configs = sorted(configs, key=lambda config: config.priority)
        self.transport = transport or _default_transport

    def available_providers(self) -> list[AIProviderConfig]:
        return [config for config in self.configs if config.enabled and bool(config.api_key)]

    def complete(self, request: AIRequest) -> AIResponse:
        providers = self.available_providers()
        if not providers:
            return AIResponse(False, "-", "-", status="DEGRADED_NO_AI_PROVIDER", error="NO_ENABLED_PROVIDER_WITH_KEY")

        errors: list[str] = []
        for config in providers:
            response = self._complete_with_provider(config, request)
            if response.ok:
                return response
            errors.append(f"{config.provider.value}:{response.error or response.status}")

        return AIResponse(False, providers[0].provider.value, providers[0].model, status="ALL_PROVIDERS_FAILED", error=";".join(errors))

    def _complete_with_provider(self, config: AIProviderConfig, request: AIRequest) -> AIResponse:
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        headers = {"Authorization": f"Bearer {config.api_key}", "Content-Type": "application/json"}
        try:
            raw = self.transport("POST", f"{config.base_url.rstrip('/')}/chat/completions", payload, headers)
        except Exception as exc:
            return AIResponse(False, config.provider.value, config.model, status="UNKNOWN", error=str(exc))

        text = _extract_openai_compatible_text(raw)
        return AIResponse(bool(text), config.provider.value, config.model, text=text, status="CONFIRMED" if text else "EMPTY_RESPONSE", raw_response=raw)


def _extract_openai_compatible_text(raw: dict) -> str:
    choices = raw.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}

