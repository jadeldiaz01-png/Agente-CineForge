from __future__ import annotations

from collections.abc import Iterable

from .models import Platform, PlatformCapability, PlatformPublishRequest, PublishResult


class MultiPlatformPublisher:
    def __init__(self, clients: dict[Platform, object], capabilities: dict[Platform, PlatformCapability]) -> None:
        self.clients = clients
        self.capabilities = capabilities

    def publish_many(self, requests: Iterable[PlatformPublishRequest]) -> list[PublishResult]:
        results: list[PublishResult] = []
        for request in requests:
            capability = self.capabilities.get(request.platform)
            client = self.clients.get(request.platform)

            if capability is None or not capability.connected:
                results.append(PublishResult(False, request.platform.value, status="DEGRADED_NOT_CONNECTED", error="CONNECTOR_NOT_CONNECTED"))
                continue
            if not capability.production_ready:
                results.append(PublishResult(False, request.platform.value, status="DEGRADED_NOT_PRODUCTION_READY", error=capability.reason))
                continue
            if client is None:
                results.append(PublishResult(False, request.platform.value, status="DEGRADED_NOT_CONNECTED", error="CLIENT_NOT_REGISTERED"))
                continue

            results.append(client.publish_video(request))

        return results

