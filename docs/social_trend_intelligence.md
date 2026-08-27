# Social Trend Intelligence

## Production Decision

CineForge should decide what premium video to create only after normalized trend
signals pass evidence, quality, rights, policy and human-approval gates.

## Required Information Layers

| Layer | Purpose | Production Gate |
| --- | --- | --- |
| `platform_api_connector` | Connect official platform APIs or approved analytics exports. | Connector health verified |
| `trend_signal_ingestion` | Collect views, likes, comments, shares, saves, reposts and topic metadata. | At least two evidence signals for production briefs |
| `metric_normalization` | Convert platform-specific metrics into comparable engagement quality. | No raw-only scoring |
| `velocity_and_freshness_scoring` | Detect whether a trend is still moving. | Observation timestamp present |
| `cross_platform_fit_scoring` | Prefer ideas that can be adapted across Facebook, YouTube, TikTok and X. | Platform-specific format requirements present |
| `audience_and_category_mapping` | Match topic to audience, language, region and category. | Audience declared |
| `rights_and_originality_review` | Prevent copied clips, watermark reuse and unclear asset rights. | Required before brief approval |
| `policy_and_safety_review` | Block unsafe, misleading, impersonation, spam or prohibited automation. | Required before brief approval |
| `premium_video_quality_spec` | Enforce hook, clarity, safe zones, audio, subtitles and technical QC. | Required before publishing |
| `creative_brief_generation` | Produce the script premise, hook and production instructions. | Only from approved trend candidates |
| `human_approval_gate` | Require user approval before public posting. | Always required |
| `evidence_and_lineage_ledger` | Preserve sources, timestamps and scoring evidence. | Required for audit |
| `post_publish_metrics_feedback` | Feed real performance into future decisions. | Required for optimization |

## Platform Evidence Sources

| Platform | Primary Sources | Notes |
| --- | --- | --- |
| Facebook / Meta | Meta Video/Reels APIs, Page insights, manual exports where API access is limited. | Use vertical 9:16 MP4/H.264-style production profile for Reels-oriented content. |
| YouTube | YouTube Data API `videos.list` with `chart=mostPopular`, channel analytics and region/category filters. | Quota must be tracked before automated trend scans. |
| TikTok | Content Posting API, Research API where the use case is eligible, Creative Center or account analytics. | Do not rely on scraping. Commercial access to research data can be restricted. |
| X | X API post/media endpoints, search/topic monitoring where plan permits, account analytics. | Video publishing requires media upload handling before post creation. |

## Scoring Model

The production score is bounded from 0 to 1:

```text
opportunity = 0.35 engagement_quality
            + 0.30 velocity
            + 0.20 freshness
            + 0.15 cross_platform_fit

final_score = opportunity * (1 - risk_penalty)
```

Risk penalty combines originality and policy risk. A candidate is blocked when:

- Rights are not verified.
- Originality risk is greater than `0.35`.
- Policy risk is greater than `0.25`.
- Fewer than two evidence signals exist.
- Premium opportunity score is below `0.45`.

## CLI

List required layers:

```bash
python -m meta_facebook_mcp_publisher.trend_cli --list-layers
```

Evaluate candidates:

```bash
python -m meta_facebook_mcp_publisher.trend_cli --candidates trend-candidates.jsonl
```

The CLI exits with:

- `0`: at least one approved premium brief exists.
- `2`: no candidate file was provided.
- `3`: candidates exist, but none passed production gates.
