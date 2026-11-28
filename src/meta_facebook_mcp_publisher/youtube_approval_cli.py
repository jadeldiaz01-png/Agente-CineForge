"""Issue a one-time upload approval from the VPS operator shell.

Run as the service account with the same YOUTUBE_ENV_FILE and ledger settings.
The token is printed once; pass it directly as the MCP tool argument and never
store it in the repository or logs.
"""
from __future__ import annotations

import os

from .youtube_mcp_server import _configured_client, _ledger_path, _video_path
from .youtube_approval import issue_upload_approval, upload_approval_digest


def _yes(prompt: str) -> bool:
    return input(prompt + " [y/N]: ").strip().lower() == "y"


def main() -> None:
    video = _video_path(input("Ruta del MP4 dentro del directorio permitido: ").strip())
    title = input("Título exacto: ").strip()
    description = input("Descripción exacta: ")
    privacy = input("Privacidad (private/unlisted/public) [private]: ").strip() or "private"
    if privacy not in {"private", "unlisted", "public"}:
        raise SystemExit("Privacidad inválida.")
    if privacy == "public" and os.getenv("YOUTUBE_PUBLIC_POSTING_AUDITED", "").lower() not in {"1", "true", "yes", "on"}:
        raise SystemExit("Publicación pública no auditada; no se emitió aprobación.")
    tags = [item.strip() for item in input("Etiquetas separadas por coma (vacío si ninguna): ").split(",") if item.strip()]
    category = input("ID de categoría [22]: ").strip() or "22"
    made_for_kids = _yes("¿El contenido está hecho para niños?")
    if not _yes("¿Revisaste el archivo exacto y aprobaste calidad y originalidad?"):
        raise SystemExit("No se emitió aprobación.")
    if input("Escribe APPROVE para emitir autorización de un solo uso: ").strip() != "APPROVE":
        raise SystemExit("No se emitió aprobación.")
    if not 1 <= len(title) <= 100 or len(description) > 5000:
        raise SystemExit("Título o descripción fuera de los límites permitidos.")
    _, channel_id, _ = _configured_client()
    digest = upload_approval_digest(video, channel_id, title, description, made_for_kids, privacy, tags, category)
    token = issue_upload_approval(_ledger_path(), digest)
    print("\nAutorización de un solo uso (vence en 10 minutos):")
    print(token)
    print("Pásala solo a la llamada MCP correspondiente; no la publiques ni la guardes.")


if __name__ == "__main__":
    main()
