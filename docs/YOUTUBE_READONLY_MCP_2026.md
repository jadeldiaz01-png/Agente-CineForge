# CineForge y YouTube: MCP propio de solo lectura

**Estado: PREPARE_ONLY. No hay autenticación OAuth real, conexión ChatGPT, despliegue en VPS ni publicación.**

No se necesita contratar Windsor.ai. Este proyecto es independiente y reutiliza CineForge sin otro agente.

## Componentes preparados

- Cliente HTTPS GET-only: consultas de identidad de canal, lista de vídeos y analíticas no monetarias.
- MCP Python SDK v2: cuatro herramientas de solo lectura: estado, canal, vídeos y métricas.
- Contrato OAuth 2.0/PKCE S256: genera solicitud con scopes fijos, state aleatorio, desafío y verifica el estado del callback. **No implementa un servidor de callback ni intercambia o almacena tokens.**
- Pruebas offline y CI: rechazo de acceso sin token, fijación del ID de canal, lista limitada de herramientas, OAuth y ausencia de publicación.

## Acciones del titular desde Android

1. Abrir https://console.cloud.google.com/ con la misma cuenta que administra el canal. Seleccionar o crear un proyecto de Google Cloud. No habilitar facturación o gastos que no estén aprobados.
2. En https://console.cloud.google.com/apis/library habilitar **YouTube Data API v3** y **YouTube Analytics API**; consultar la cuota disponible.
3. En https://console.cloud.google.com/auth/overview configurar la pantalla de consentimiento, audiencia y usuarios de prueba según corresponda.
4. Permisos requeridos: https://www.googleapis.com/auth/youtube.readonly y https://www.googleapis.com/auth/yt-analytics.readonly. No solicitar permisos de subida ni de gestión de cuenta.
5. La credencial de tipo **Web application** necesita una URL de redirección HTTPS registrada que coincida con el broker. **Aún no existe ese callback público auditado.** No utilizar una URL de ejemplo como si estuviera operativa.
6. Cuando el broker seguro esté preparado, el propietario inicia sesión en Google, selecciona el canal correcto y autoriza la lectura. Nunca compartir secretos, códigos de autorización ni tokens por chat.

## Puertas pendientes para la conexión real

- Implementar un broker OAuth HTTPS con redirección exacta, estado y PKCE de un solo uso, canje privado de código, cifrado de tokens en un gestor de secretos, verificación de scopes, expiración y revocación.
- Confirmar consentimiento de Google y lectura real del canal mediante channels.list(mine=true).
- Guardar el ID real aprobado en la configuración segura YOUTUBE_EXPECTED_CHANNEL_ID. Las consultas de vídeos y Analytics se bloquean si falta este ID o no coincide con el canal autorizado.
- Ejecutar pruebas autenticadas, acuses de lectura y revisión de seguridad en el VPS Ubuntu.
- Para ChatGPT remoto se necesita **MCP Streamable HTTP autenticado**, HTTPS y controles de audiencia, permisos y acceso. El servidor local stdio **no** crea por sí solo una conexión remota.
- No instalar ni exponer servicios públicos hasta validar seguridad y el flujo OAuth.

## Estado de seguridad

El comando local, tras instalar el paquete opcional y configurar la credencial mediante un almacén privado, es: python -m meta_facebook_mcp_publisher.youtube_readonly_mcp

El estado del MCP informa BLOCKED_NO_OAUTH, BLOCKED_CHANNEL_NOT_PINNED, BLOCKED_AUTH_OR_API, BLOCKED_CHANNEL_MISMATCH o CONNECTED_READONLY, sin mostrar tokens. La disponibilidad del canal y el acceso a Analytics deben comprobarse por separado.

La aprobación para publicar, monetizar, gastar, realizar operaciones o modificar cuentas **no** está incluida. Los controles existentes de CineForge continúan bloqueando la publicación.

## Referencias oficiales

- https://developers.google.com/youtube/data/guides/authentication
- https://developers.google.com/youtube/analytics/reference/reports/query
- https://developers.google.com/youtube/reporting/guides/authorization/server-side-web-apps
- https://py.sdk.modelcontextprotocol.io/run/
