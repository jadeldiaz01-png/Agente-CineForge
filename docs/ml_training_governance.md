# ML/DL/LLM Training Governance

## Objective

Add machine learning, deep learning and LLM improvement loops to Agente
CineForge without uncontrolled scraping, copyright leakage, private data
collection or autonomous deployment of unreviewed model behavior.

## Architecture

```text
Approved source
  -> source policy review
  -> dataset registry
  -> offline feature extraction
  -> ML/DL/LLM evaluation
  -> model card + dataset card
  -> human approval
  -> production rollout gate
```

## Layers

| Layer | Purpose |
| --- | --- |
| Data governance | Source URL, license, terms, robots and personal-data review |
| Dataset registry | Dataset ID, lineage hash, splits and policy decision |
| ML | Ranking trends, captions, hooks and platform-fit predictions |
| Deep learning | Vision/audio embeddings and multimodal quality scoring |
| LLM | RAG over approved data, prompt templates and pairwise evaluations |
| Autonomous programming | Propose code changes, never deploy without review |
| Evidence | Registry, eval reports, model cards and approval artifacts |

## Training Gates

| Gate | Requirement |
| --- | --- |
| `SOURCE_URL_VALID` | Valid HTTP/HTTPS source |
| `LICENSE_PRESENT` | License declared |
| `LICENSE_ALLOWED_OR_REVIEWED` | Open license or explicit review |
| `TERMS_REVIEWED` | Human reviewed source terms |
| `ROBOTS_REVIEWED` | Collection rules reviewed |
| `NO_UNREVIEWED_PERSONAL_DATA` | Personal data requires separate approval |
| `EVALS_PASSED` | Offline evals pass before production |
| `MODEL_CARD_READY` | Intended use, limits and evals documented |

## Production Rule

The agent may collect metadata and register sources, but it must not train or
fine-tune on arbitrary internet data. Production training is allowed only when
every dataset record is `ALLOWED`.

## Evidence References

- NIST AI RMF: governance and risk management for AI systems.
- Model Cards: standardized reporting for trained models.
- Hugging Face Dataset Cards: dataset contents, context, bias and responsible use.
- OpenAI Evals guidance: prefer structured scoring and comparisons.

