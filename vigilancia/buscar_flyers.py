#!/usr/bin/env python3
"""Buscador automático de flyers para Cazando Chivos.

Recorre data/eventos.json, detecta eventos sin flyer (o con URL externa),
busca una imagen del flyer, la descarga a flyers/ y actualiza el evento.

Uso: buscar_flyers.py [--dry-run]
  --dry-run: solo muestra qué haría, no modifica nada
"""
import json
import sys
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTOS = ROOT / "data" / "eventos.json"
FLYERS_DIR = ROOT / "flyers"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def slug(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


def buscar_imagen(banda: str, bar: str) -> str | None:
    """Busca el flyer del evento. Retorna URL o None.
    
    Estrategia:
    1. Si el evento ya tiene flyer local, no hacer nada (retorna None)
    2. Buscar en la web el flyer oficial
    """
    # Por ahora, retorna None - la búsqueda real se hace manual
    # o se integra con el image_search en el futuro
    return None


def descargar(url: str, destino: Path) -> bool:
    """Descarga una imagen. Retorna True si tuvo éxito."""
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read(5 * 1024 * 1024)  # max 5MB
        # Verificar que sea imagen
        if data[:2] == b"\xff\xd8":
            ext = ".jpg"
        elif data[:8] == b"\x89PNG\r\n\x1a\n":
            ext = ".png"
        elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            ext = ".webp"
        else:
            return False
        destino.with_suffix(ext).write_bytes(data)
        return True
    except Exception:
        return False


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    eventos = json.loads(EVENTOS.read_text(encoding="utf-8"))
    
    sin_flyer = []
    for e in eventos:
        flyer = e.get("flyer", "")
        # Sin flyer, o con URL externa (no local)
        if not flyer or flyer.startswith("http"):
            sin_flyer.append(e)
    
    print(f"Eventos sin flyer local: {len(sin_flyer)}")
    for e in sin_flyer:
        banda = e.get("banda", "?")[:50]
        print(f"  - {banda} ({e.get('fecha')})")
        if not dry_run:
            # Aquí iría la lógica de búsqueda y descarga
            # Por ahora solo reporta
            pass
    
    if dry_run:
        print("\n(dry-run: no se modificó nada)")


if __name__ == "__main__":
    main()
