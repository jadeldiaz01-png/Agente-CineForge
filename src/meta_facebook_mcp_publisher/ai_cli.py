from __future__ import annotations

import argparse
import json

from .ai_gateway import AIProviderGateway, AIRequest, load_provider_configs_from_env


def run() -> int:
    parser = argparse.ArgumentParser(description="Run the AI provider gateway with failover.")
    parser.add_argument("--task", default="general")
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--system", default="You are a precise production assistant.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configs = load_provider_configs_from_env()
    if args.dry_run:
        providers = [
            {
                "provider": config.provider.value,
                "model": config.model,
                "enabled": config.enabled,
                "has_key": bool(config.api_key),
                "free_tier": config.free_tier,
                "priority": config.priority,
            }
            for config in configs
        ]
        print(json.dumps({"status": "DRY_RUN_CONFIRMED", "providers": providers}, indent=2, sort_keys=True))
        return 0

    gateway = AIProviderGateway(configs)
    result = gateway.complete(AIRequest(task=args.task, prompt=args.prompt, system=args.system))
    print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(run())

