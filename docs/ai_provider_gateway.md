# AI Provider Gateway

## Objective

Add a provider-agnostic AI gateway for Agente CineForge so the system can use
Nemotron 3 Ultra through NVIDIA NIM and fail over to free-tier or low-cost
providers when configured.

## Provider Priority

| Priority | Provider | Default Model | Reason |
| --- | --- | --- | --- |
| 10 | NVIDIA NIM | `nvidia/nemotron-3-ultra-550b-a55b` | High-capacity reasoning and agent planning |
| 20 | Groq | `llama-3.3-70b-versatile` | Fast OpenAI-compatible fallback |
| 30 | Hugging Face | `meta-llama/Llama-3.1-8B-Instruct` | Open model ecosystem and serverless inference |
| 40 | Gemini | `gemini-2.5-flash` | Low-cost/free-tier long-context fallback |

## Gates

| Gate | Rule |
| --- | --- |
| `PROVIDER_ENABLED` | Provider must be explicitly enabled |
| `API_KEY_PRESENT` | Key must be present in GitHub Secrets/environment |
| `NO_SECRET_IN_REPO` | Keys are never committed |
| `FAILOVER_READY` | Gateway tries the next provider if one fails |
| `TASK_BOUNDARY` | Gateway is inference only; training uses training governance |

## GitHub Secrets

```text
NVIDIA_NIM_API_KEY
GROQ_API_KEY
HF_TOKEN
GEMINI_API_KEY
```

## GitHub Variables

```text
NVIDIA_NIM_ENABLED=false
NVIDIA_NIM_MODEL=nvidia/nemotron-3-ultra-550b-a55b
NVIDIA_NIM_BASE_URL=https://integrate.api.nvidia.com/v1
GROQ_ENABLED=false
HF_INFERENCE_ENABLED=false
GEMINI_ENABLED=false
```

## Run

```bash
python -m meta_facebook_mcp_publisher.ai_cli \
  --prompt "Create a production-safe video plan" \
  --dry-run
```

## Evidence Notes

NVIDIA NIM exposes OpenAI-compatible LLM inference APIs. Hugging Face Inference
Providers provide serverless access to many models. Free-tier availability and
limits can change, so production should treat each provider as quota-limited and
fail closed when credentials or provider access are missing.

