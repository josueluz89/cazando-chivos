#!/usr/bin/env python3
"""Flyers automáticos para Cazando Chivos.

Cada evento nuevo entra con imagen, sin que nadie lo pida:
  SOLO el póster oficial del evento: og:image / twitter:image de la página
  de la fuente (ticketeras, sitio del bar, eventos.cr, etc.).
La imagen se descarga a flyers/ y el evento queda con flyer local.
Si no hay póster oficial, el evento queda sin flyer: NUNCA se inventa
una URL, ni se usa foto de disco, foto de otro artista o imagen genérica.

Uso:
  buscar_flyers.py [--dry-run]   # backfill: llena los flyers vacíos de data/eventos.json
  resolver_flyer(evento)         # lo usa actualizar.py para cada evento nuevo
"""
import html.parser
import json
import re
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTOS = ROOT / "data" / "eventos.json"
FLYERS_DIR = ROOT / "flyers"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CazadorChivos/1.0"}
TIMEOUT = 25
MAX_IMG = 5 * 1024 * 1024
MIN_IMG = 5 * 1024
IMG_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


def slug(s: str) -> str:
    out = []
    for ch in (s or "").lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


def sniff(data: bytes):
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:4] == b"GIF8":
        return ".gif"
    return None


def fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read(MAX_IMG + 1)


class MetaParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.image = None

    def handle_starttag(self, tag, attrs):
        if tag != "meta" or self.image:
            return
        a = dict(attrs)
        prop = (a.get("property") or a.get("name") or "").lower()
        if prop in ("og:image", "twitter:image"):
            self.image = a.get("content")


def og_image(page_url: str):
    """Póster oficial de la página de la fuente. None si no hay o si es FB/IG."""
    if not page_url:
        return None
    if "facebook.com" in page_url or "instagram.com" in page_url:
        return None  # muro de login, nunca trae og:image útil
    try:
        html = fetch_bytes(page_url).decode("utf-8", "replace")
    except Exception:
        return None
    p = MetaParser()
    try:
        p.feed(html)
    except Exception:
        pass
    if p.image:
        return urllib.parse.urljoin(page_url, p.image)
    return None


def descargar(url: str, destino_base: str):
    """Descarga y verifica que sea imagen real. Retorna 'flyers/...' o None."""
    try:
        data = fetch_bytes(url)
    except Exception:
        return None
    if len(data) < MIN_IMG or len(data) > MAX_IMG:
        return None
    ext = sniff(data)
    if not ext:
        return None
    FLYERS_DIR.mkdir(exist_ok=True)
    dest = FLYERS_DIR / (destino_base + ext)
    dest.write_bytes(data)
    return f"flyers/{dest.name}"


def resolver_flyer(evento: dict) -> str:
    """Imagen para un evento. '' si no se encontró nada real."""
    banda = evento.get("banda", "")
    fecha = evento.get("fecha", "")
    base = slug(f"{banda}-{fecha}") or "flyer"
    if FLYERS_DIR.is_dir():
        for f in FLYERS_DIR.glob(base + ".*"):
            if f.suffix.lower() in IMG_EXTS:
                return f"flyers/{f.name}"
    img = og_image(evento.get("fuente", ""))
    if img:
        out = descargar(img, base)
        if out:
            return out
    return ""


def main() -> None:
    dry = "--dry-run" in sys.argv
    eventos = json.loads(EVENTOS.read_text(encoding="utf-8"))
    hechos = 0
    faltan = []
    for e in eventos:
        if e.get("flyer"):
            continue
        if dry:
            faltan.append(f"{e.get('fecha')} {e.get('banda')} @ {e.get('bar')}")
            continue
        flyer = resolver_flyer(e)
        if flyer:
            e["flyer"] = flyer
            hechos += 1
            print(f"OK  {e.get('fecha')} {e.get('banda')[:50]} -> {flyer}")
        else:
            faltan.append(f"{e.get('fecha')} {e.get('banda')} @ {e.get('bar')}")
    if dry:
        print(f"\nEventos sin flyer: {len(faltan)} (dry-run, no se modificó nada)")
        for f in faltan:
            print(f"  - {f}")
        return
    EVENTOS.write_text(json.dumps(eventos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    # Regenerar data/app.json con actualizar.py (lista vacía = solo regenera)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        tf.write("[]")
        empty = tf.name
    subprocess.run(
        [sys.executable, str(ROOT / "vigilancia" / "actualizar.py"), empty],
        check=True, capture_output=True, text=True,
    )
    print(f"\nFlyers resueltos: {hechos} | Sin imagen: {len(faltan)}")
    for f in faltan:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
