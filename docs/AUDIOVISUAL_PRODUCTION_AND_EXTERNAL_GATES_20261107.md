# CineForge: producción audiovisual local y gates externos — 2026-11-07

Dictamen: PREPARE_ONLY. Sin publicación LIVE, compras, activación de OAuth o despliegues.

## Cadena de trabajo

1. Se analiza un video local mediante clip_cli, con medición visual + audio
   y selección de intervalos atados al SHA-256 de la fuente.
2. Se ejecuta clip_render_cli con --video, --analysis, --output y
   --candidate-index. El archivo de salida debe ser MP4 nuevo.
3. FFmpeg produce preview H.264 / AAC, 1080x1920, 30 fps, pix_fmt yuv420p,
   sin recorte forzado: usa escalado y padding, registrando este hecho.
   Retiene audio de entrada o añade silencio si el video no tiene audio.
4. ffprobe comprueba codec, dimensiones, FPS, pista AAC y duración;
   el sidecar .mp4.render.json contiene hash de fuente, selección, hash
   de resultado y banderas de protección en FALSE.
5. El resultado es preview editorial local, NO generación texto-a-video ni
   una predicción estadística de viralidad, rentabilidad o elegibilidad.
   La subida de videos de terceros a la conversación no certifica derechos
   de redistribución o monetización.

Ejemplo:
    python -m meta_facebook_mcp_publisher.clip_cli --video fuente.mp4 --output candidatos.json --clip-seconds 20
    python -m meta_facebook_mcp_publisher.clip_render_cli --video fuente.mp4 --analysis candidatos.json --output preview.mp4

## Gobierno GitHub — PARCIAL

Lectura de GitHub 2026-11-07: main SHA fb703aa013042ba6e8a0807068c27b9d9a5fabe4.
Ruleset 26164666, cineforge-protected-main-p0, activo, aplica a
default branch, bloquea borrado y non-fast-forward, exige pull request
y status production-readiness con strict policy. Sin bypass actors.
ATENCIÓN: required_approving_review_count=0. El job `ffmpeg-real-video` del workflow específico está sujeto a filtros de rutas; NO debe añadirse como required global mientras sea condicional. En este PR, la prueba FFmpeg ahora también es obligatoria dentro de `production-readiness` (que sí es un check requerido). La prueba separada sirve como evidencia adicional.
PR #5 y PR #6 siguen DRAFT / SIN MERGE.

Política del propietario: solo reconocer revisión automática de **Codex** como revisión de código. Activar `Automatic review` en la configuración Codex del repositorio y elegir `Review trigger` para cada push; ya se solicitaron revisiones con `@codex review` sobre los dos PR. No dar por recibida aprobación formal `APPROVED` cuando Codex solo publica `COMMENTED` o reacciona. El job requerido `production-readiness` ya exige pruebas FFmpeg en este PR. Los gates externos de producción y la aprobación del contenido antes de publicar son controles distintos.

## Conectores de redes — BLOQUEADO

No se verificaron tokens, cuentas, propietarios, permisos OAuth, scope grants,
auditorías de aplicación, ni recibos de post públicos. No modificar flags de
publicación ni declarar estas condiciones satisfechas.

YouTube: cambio oficial 2026-11-02: deja de aplicar la antigua restricción
general que forzaba uploads de proyectos no verificados a privados. Eso NO
concede OAuth ni autorización humana. Ahora videos.insert puede usar PUBLIC
por defecto si privacyStatus se omite; forzar explicitamente PRIVATE en
pruebas autorizadas. En PR #5 la privacidad por defecto ya es PRIVATE.
Fuente: https://developers.google.com/youtube/data/revision_history

TikTok: exige video.publish aprobado y consentido por creador; cliente sin
auditoría no habilita publicación pública. Validar creator-info y estado
remoto antes de considerar visible el post.
Fuente: https://developers.tiktok.com/docs/en/content-posting-api-get-started

Meta: verificar Page role, modo de app, scopes efectivamente concedidos,
consentimiento y prueba de contrato actual desde sesión autorizada.
Fuente: https://developers.facebook.com/documentation/video-api/guides/publishing

X: no existe certificación de INIT/APPEND/FINALIZE/status en PR #5;
conector de video debe permanecer bloqueado.
Fuente: https://docs.x.com/x-api/media/introduction

## Infraestructura y generación — BLOQUEADO

VPS: verificar lectura de preflight en PR #5, volumen persistente del ledger,
backup, restore tras reboot, semántica multi-host, identidades de servicio,
permisos y reconciliación remota. GitHub runner efímero no certifica esto.
GPU: verificar hardware, VRAM, digest/licencia del modelo, coste externo
cero y benchmark real de inferencia. Este renderer es compositor, NO motor
generativo certificado. Mantener generation_model_quality_benchmark_certified
en FALSE.

Publicación LIVE: requiere SHA-256 final + derechos + revisión editorial
+ aprobación humana vinculada a caption/thumbnail/plataforma + permiso
de cuenta + ledger persistente y reconciliación remota antes de habilitarse.

## Evidencia CI

Exigir el job protegido `production-readiness` sobre HEAD exacto (incluye FFmpeg E2E). Ejecutar el workflow separado `clip-intelligence-av-e2e` como evidencia adicional; está filtrado por rutas y no debe configurarse globalmente como required.
Prueba especializada instala ffmpeg/ffprobe, genera media audiovisual real,
verifica codificación, SHA-256 y denegaciones adversariales. Estas pruebas
no certifican fuente real propia, contenido generado por un modelo ni
permiso de ninguna plataforma.

En esta implementación no se alteran PayPal, Cloudflare, VPS, permisos de
publicación, credenciales, modelos de inferencia o pagos.
