# CineForge: cinco compuertas externas de producción (2026-10-26)

Decision: NO-GO / PREPARE_ONLY. Sin gastos, publicación externa, OAuth operativo ni entrenamiento externo.

## Gate 1: GitHub main
Lectura real: el repositorio es público; main está desprotegido y no tiene rulesets activos. El conector GitHub usado aquí permite lectura pero no administra reglas.
Configuración manual: https://github.com/jadeldiaz01-png/Agente-CineForge/settings/rules
Settings > Rules > Rulesets > New branch ruleset. Nombre: cineforge-protected-main-P0. Enforced: Active. Target: default branch/main.
Require a pull request before merging; require status checks: production-readiness (nombre exacto del job que existe); strict/up-to-date; resolve conversations; no force pushes; no deletions; restrict bypass. Si hay un revisor independiente autorizado, requerir su aprobación; no inventar un revisor.
Confirmar rama protected=true y ruleset efectivo tras guardar. No fusionar PR #5 por el éxito del check sin las otras condiciones.
Docs: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/creating-rulesets-for-a-repository

## Gate 2: ledger persistente
Desde el VPS y una copia del repo ejecutar: python3 scripts/cineforge_host_preflight_readonly.py
El preflight NO escribe datos ni abre secretos; solo observa existencia y permisos de la carpeta, ffmpeg/ffprobe y GPU NVIDIA. Por definición siempre devuelve production_ready=false.
NO considerar certificada una carpeta por existir. Pendiente: servicio de mínimo privilegio, volumen persistente, copias y restauración, concurrencia/múltiples nodos, persistencia después de reinicio y vínculo remoto-intento.
Nunca activar CINEFORGE_DURABLE_LEDGER_CERTIFIED por el inventario de solo lectura. Los runners de GitHub son efímeros.

## Gate 3: identidad y permisos de cada red
Meta: comprobar App ID y modo, revisión y permisos precisos de Page, rol del propietario, validez de conexión en consola sin exponer tokens.
YouTube: comprobar proyecto, OAuth, API habilitada y scope youtube.upload; se debe elegir privacidad y confirmar canal. Verificar auditoría/consentimiento aplicable.
TikTok: comprobar video.publish aprobado, Content Posting API, app audit para visibilidad pública, consentimiento explícito del creador e interfaz creator-info. Apps sin auditar quedan limitadas a privado.
X: confirmar entitlement, acceso del plan, permisos vigentes de medios y publicación; permanecer bloqueado hasta completar el protocolo.
En GitHub solo almacenar evidencia de alcance y permisos sin valores de tokens, secretos, OAuth codes ni IDs personales.
Docs: https://developers.google.com/youtube/data/reference/rest/v3/videos/insert
Docs: https://developers.tiktok.com/docs/en/content-posting-api-reference-direct-post
Docs: https://developers.tiktok.com/docs/en/content-posting-api-reference-get-video-status
Docs: https://developers.facebook.com/documentation/video-api/guides/publishing
Docs: https://docs.x.com/x-api/media/introduction

## Gate 4: pruebas contractuales
Primero pruebas negativas offline: vídeo inválido, aprobación falsificada, hash/caption distinto, token ausente, permisos insuficientes, doble intento, rate limit, caída/timeout, identidad de cuenta incorrecta.
Después, solo si la cuenta y el entorno de prueba están expresamente autorizados: 1 vídeo privado de prueba por plataforma permitida, hash del archivo aprobado, receipt de API, reconciliación del ID exacto y reintento sin duplicados.
No equiparar upload completado con publicación visible. Si no existe sandbox real, no prometer pruebas LIVE públicas como test.

## Gate 5: calidad de vídeo generativo
El render local anterior es composición/motion graphics, no texto a vídeo generativo. Verificar licencia de modelo y assets, checksum de checkpoint, GPU/VRAM, runtime y coste cero.
Wan2.2 TI2V-5B de referencia: 720p/24fps y aproximadamente 24 GB de VRAM (requisito de ejemplo oficial). No alegar 1080p nativo si hay upscale.
Benchmark propuesto: 20 briefs iguales por plataforma y tres evaluadores independientes a ciegas, calidad visual y movimiento, fidelidad, audio, identidad, tasa de error, p50/p95 y coste real.
Docs: https://github.com/Wan-Video/Wan2.2

## Evidencia y auditoría
El estado probado por GitHub Actions hasta esta preparación es solo CI. La firma de artefactos CI no certifica una publicación externa ni licencia de modelos.
El PR #5 permanece en borrador, sin merge ni publicación; el manifiesto declara BLOCKED. Todos los cinco gates requieren prueba reproducible sobre SHA exacto antes de LIVE.
