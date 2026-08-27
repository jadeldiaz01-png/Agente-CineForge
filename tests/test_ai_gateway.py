from meta_facebook_mcp_publisher.ai_gateway import AIProvider, AIProviderConfig, AIProviderGateway, AIRequest


def test_gateway_degrades_when_no_provider_has_key() -> None:
    gateway = AIProviderGateway(
        [
            AIProviderConfig(
                provider=AIProvider.NVIDIA_NIM,
                base_url="https://example.com/v1",
                api_key="",
                model="nvidia/nemotron-3-ultra-550b-a55b",
                enabled=True,
            )
        ]
    )

    result = gateway.complete(AIRequest(task="test", prompt="hello"))

    assert not result.ok
    assert result.status == "DEGRADED_NO_AI_PROVIDER"


def test_gateway_uses_first_available_provider() -> None:
    calls = []

    def transport(method: str, url: str, payload: dict, headers: dict[str, str]) -> dict:
        calls.append((method, url, payload, headers))
        return {"choices": [{"message": {"content": "ok"}}]}

    gateway = AIProviderGateway(
        [
            AIProviderConfig(AIProvider.HUGGINGFACE, "https://hf.example/v1", "", "hf-model", enabled=True, priority=5),
            AIProviderConfig(AIProvider.NVIDIA_NIM, "https://nim.example/v1", "key", "nemotron", enabled=True, priority=10),
        ],
        transport=transport,
    )

    result = gateway.complete(AIRequest(task="test", prompt="hello"))

    assert result.ok
    assert result.provider == "nvidia_nim"
    assert calls[0][1] == "https://nim.example/v1/chat/completions"

