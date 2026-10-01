#!/usr/bin/env python3
"""Vigilancia Cazador de Chivos: detector de cambios 2x/dia, solo stdlib.

- Recorre sources.json (solo URLs http/https; FB/IG vacios se reportan pendiente).
- Por fuente: hash del HTML. Si cambio vs state.json -> novedad.
- En novedades: guarda imagen ORIGINAL (og:image + <img>, magic bytes jpg/png/webp,
  max 3MB, max 10 por corrida) en candidatos/<stamp>/, nunca screenshot.
- Logo del bar: og:image de su web a logos-bares/<slug>.* (solo si no existe).
- Escribe novedades.json + issue_body.md. NO publica a eventos.json (lo aprueba Mike).
- Uso: check.py --run | --dry-run. Base: directorio vigilancia/.
"""
import hashlib
import html.parser
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CazadorChivos-vigilancia/1.0"}
TIMEOUT = 20
MAX_IMG = 3 * 1024 * 1024
MIN_IMG = 5 * 1024
MAX_IMGS_RUN = 10
SKIP_RE = re.compile(r"logo|icon|sprite|pixel|tracking|favicon|blank|placeholder", re.I)


def slug(s):
    s = s.lower()
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-") or "bar"


def sniff(data):
    if data[:2] == b"\xff\xd8":
        return ".jpg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:4] in (b"GIF8",):
        return ".gif"
    return None


def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        ctype = r.headers.get("Content-Type", "")
        data = r.read(8 * 1024 * 1024)
    return ctype, data


class Meta(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.og_image = None
        self.og_title = None
        self.imgs = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta":
            prop = (a.get("property") or a.get("name") or "").lower()
            if prop == "og:image" and not self.og_image:
                self.og_image = a.get("content")
            if prop == "og:title" and not self.og_title:
                self.og_title = a.get("content")
        elif tag == "img":
            src = a.get("src")
            if src:
                self.imgs.append(src)


def abs_url(base, src):
    if not src or src.startswith("data:"):
        return None
    return urllib.parse.urljoin(base, src)


MESES = ("enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|"
         "octubre|noviembre|diciembre|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec")
DATE_RE = re.compile(rf"20\d{{2}}[-/]\d{{1,2}}[-/]\d{{1,2}}|\d{{1,2}}\s+de\s+(?:{MESES})|"
                     rf"(?:{MESES})\s+\d{{1,2}}", re.I)
STRIP_RE = re.compile(r"<!--.*?-->|<script\b.*?</script>|<style\b.*?</style>"
                      r"|\s+data-[a-z-]+=\"[^\"]*\"|csrf|nonce|timestamp", re.I | re.S)


class Text(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, d):
        d = d.strip()
        if d:
            self.parts.append(d)


def signal_of(html, base):
    """Huella solo de senales de evento: fechas + titulo + imagenes (sin scripts/ads)."""
    clean = STRIP_RE.sub(" ", html[:500000])
    p = Meta()
    try:
        p.feed(clean)
    except Exception:
        pass
    t = Text()
    try:
        t.feed(clean)
    except Exception:
        pass
    text = re.sub(r"\s+", " ", " ".join(t.parts).lower())
    fechas = sorted(set(DATE_RE.findall(text)))
    imgs = []
    for cand in ([p.og_image] if p.og_image else []) + p.imgs:
        u = abs_url(base, cand)
        if u and u.startswith("http") and not SKIP_RE.search(u) and u not in imgs:
            imgs.append(re.sub(r"\?.*$", "", u))
    blob = "\n".join([(p.og_title or "").strip()] + fechas + sorted(imgs))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest(), p


def main():
    dry = "--dry-run" in sys.argv
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    with open(os.path.join(BASE, "sources.json"), encoding="utf-8") as f:
        sources = json.load(f)
    state_p = os.path.join(BASE, "state.json")
    state = json.load(open(state_p, encoding="utf-8")) if os.path.exists(state_p) else {}
    known_p = os.path.join(BASE, "known_events.json")
    known = set(json.load(open(known_p, encoding="utf-8"))) if os.path.exists(known_p) else set()

    novedades = []
    pendientes = []
    saved = 0
    cand_dir = os.path.join(BASE, "candidatos", stamp)

    for entry in sources["bares"]:
        bar = entry["bar"]
        url = entry.get("web")
        if not url:
            if entry.get("facebook") or entry.get("instagram"):
                pendientes.append(f"{bar}: FB/IG configurado pero requiere token o revision manual")
            else:
                pendientes.append(f"{bar}: sin fuente web, revision manual o WhatsApp")
            continue
        try:
            ctype, data = fetch(url)
        except Exception as e:
            novedades.append({"bar": bar, "fuente": url, "tipo": "fuente_caida",
                              "detalle": f"{type(e).__name__}: {e}"[:200]})
            continue
        if "html" not in ctype:
            continue
        try:
            html = data.decode("utf-8", "replace")
        except Exception:
            html = ""
        sig, p = signal_of(html, url)
        key = f"sig:{bar}"
        if state.get(key) == sig:
            continue  # sin cambios en senales de evento
        state[key] = sig
        # limpia hashes viejos de pagina completa para no arrastrar ruido
        state.pop(f"hash:{bar}", None)
        item = {"bar": bar, "fuente": url, "tipo": "cambio_detectado",
                "titulo": (p.og_title or "")[:150], "imagenes": []}
        urls = []
        for cand in ([p.og_image] if p.og_image else []) + p.imgs:
            u = abs_url(url, cand)
            if u and u.startswith("http") and not SKIP_RE.search(u) and u not in urls:
                urls.append(u)
        for u in urls[:12]:
            if saved >= MAX_IMGS_RUN:
                break
            try:
                _, img = fetch(u)
            except Exception:
                continue
            if len(img) > MAX_IMG:
                continue
            ext = sniff(img[:16])
            if not ext or len(img) < MIN_IMG:
                continue
            if not dry:
                os.makedirs(cand_dir, exist_ok=True)
                name = f"{slug(bar)}-{hashlib.sha256(img).hexdigest()[:8]}{ext}"
                with open(os.path.join(cand_dir, name), "wb") as f:
                    f.write(img)
                item["imagenes"].append(f"candidatos/{stamp}/{name}")
            else:
                item["imagenes"].append(u + " (dry-run, no descargada)")
            saved += 1
        # logo del bar: og:image de su web, solo si aun no hay uno
        if p.og_image and not dry:
            logo_dir = os.path.join(BASE, "..", "logos-bares")
            if not any(f.startswith(slug(bar)) for f in (os.listdir(logo_dir) if os.path.isdir(logo_dir) else [])):
                try:
                    _, limg = fetch(abs_url(url, p.og_image))
                    ext = sniff(limg[:16])
                    if ext and len(limg) <= MAX_IMG:
                        os.makedirs(logo_dir, exist_ok=True)
                        with open(os.path.join(logo_dir, slug(bar) + ext), "wb") as f:
                            f.write(limg)
                        item["logo_bar"] = True
                except Exception:
                    pass
        novedades.append(item)

    out = {"stamp": stamp, "novedades": novedades, "pendientes": pendientes,
           "eventos_conocidos": len(known)}
    if not dry:
        with open(state_p, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=1, ensure_ascii=False)
        with open(os.path.join(BASE, "novedades.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, ensure_ascii=False)
        lines = [f"# Vigilancia {stamp} (2x/dia)", "",
                 f"Novedades: {len(novedades)} | Fuentes pendientes: {len(pendientes)}",
                 "**Nada se publica solo: Mike aprueba antes de tocar eventos.json.**", ""]
        for n in novedades:
            lines.append(f"## {n['bar']}")
            lines.append(f"- Fuente: {n['fuente']} | Tipo: {n['tipo']}")
            if n.get("titulo"):
                lines.append(f"- Titulo: {n['titulo']}")
            if n.get("detalle"):
                lines.append(f"- Detalle: {n['detalle']}")
            for im in n.get("imagenes", []):
                lines.append(f"  - Imagen original: {im}")
            if n.get("logo_bar"):
                lines.append("  - Logo del bar guardado en logos-bares/")
            lines.append("")
        if pendientes:
            lines.append("## Pendientes (revision manual/WhatsApp)")
            lines += [f"- {x}" for x in pendientes]
        with open(os.path.join(BASE, "issue_body.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
    print(json.dumps({"novedades": len(novedades), "pendientes": len(pendientes),
                      "imagenes": saved, "dry": dry}, ensure_ascii=False))


if __name__ == "__main__":
    main()
