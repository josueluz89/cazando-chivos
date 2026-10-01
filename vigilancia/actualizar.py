#!/usr/bin/env python3
"""Actualizador de cartelera de Cazando Chivos.

Fusiona eventos nuevos en data/eventos.json:
  - ignora eventos sin banda/bar/fecha
  - deduplica por (bar, fecha, banda)
  - elimina eventos con más de 45 días de pasados (fecha < hoy-45 en America/Costa_Rica)
  - ordena por fecha, hora, bar
  - agrega a data/locales.json los bares nuevos (con direccion del evento)
  - genera data/app.json: paquete liviano para la app Android (próximos 60 días,
    hora normalizada a "Por confirmar" si falta)

Uso: actualizar.py [nuevos.json]
donde nuevos.json es una lista de objetos evento con los mismos campos
que data/eventos.json (banda, bar, fecha AAAA-MM-DD, hora, cover, flyer, ...).
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
EVENTOS = ROOT / "data" / "eventos.json"
LOCALES = ROOT / "data" / "locales.json"
LOGOS_JSON = ROOT / "data" / "logos.json"
LOGOS_DIR = ROOT / "logos-bares"


def slug(s: str) -> str:
    out = []
    for ch in s.lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    return "".join(out).strip("-")


def hoy_cr() -> str:
    return datetime.now(ZoneInfo("America/Costa_Rica")).strftime("%Y-%m-%d")


def clave(e: dict) -> tuple:
    return (
        str(e.get("bar", "")).strip().lower(),
        str(e.get("fecha", "")),
        str(e.get("banda", "")).strip().lower(),
    )


def main() -> None:
    nuevos = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")) if len(sys.argv) > 1 else []
    eventos = json.loads(EVENTOS.read_text(encoding="utf-8"))

    vistos = {clave(e) for e in eventos}
    agregados = 0
    for e in nuevos:
        if not e.get("banda") or not e.get("bar") or not e.get("fecha"):
            continue
        k = clave(e)
        if k in vistos:
            continue
        vistos.add(k)
        eventos.append(e)
        agregados += 1

    hoy = hoy_cr()
    limite_pasado = (datetime.now(ZoneInfo("America/Costa_Rica")) - timedelta(days=45)).strftime("%Y-%m-%d")
    vigentes = [e for e in eventos if str(e.get("fecha", "")) >= limite_pasado]
    vencidos = len(eventos) - len(vigentes)
    vigentes.sort(key=lambda e: (e.get("fecha", ""), e.get("hora") or "23:59", e.get("bar", "")))
    EVENTOS.write_text(json.dumps(vigentes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    locales = json.loads(LOCALES.read_text(encoding="utf-8"))
    nombres = {loc["nombre"] for loc in locales}
    for e in vigentes:
        if e["bar"] not in nombres:
            nombres.add(e["bar"])
            locales.append({
                "nombre": e["bar"],
                "direccion": e.get("direccion_display") or "Dirección sin confirmar",
                "estilo": "",
                "historial": [],
            })
    LOCALES.write_text(json.dumps(locales, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    logos = {}
    if LOGOS_DIR.is_dir():
        for f in sorted(LOGOS_DIR.iterdir()):
            if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
                continue
            stem = slug(f.stem)
            for loc in locales:
                if slug(loc["nombre"]) == stem:
                    logos[loc["nombre"]] = f"logos-bares/{f.name}"
                    break
    LOGOS_JSON.write_text(json.dumps(logos, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # data/app.json: paquete liviano para la app Android (solo próximos 60 días,
    # hora normalizada). La app NO lee eventos.json ni locales.json directo.
    lim_futuro = (datetime.now(ZoneInfo("America/Costa_Rica")) + timedelta(days=60)).strftime("%Y-%m-%d")
    proximos = []
    for e in vigentes:
        f = str(e.get("fecha", ""))
        if hoy <= f <= lim_futuro:
            ev = dict(e)
            ev["hora"] = e.get("hora") or "Por confirmar"
            proximos.append(ev)
    zonas = sorted({e.get("region", "") for e in proximos if e.get("region")})
    app_data = {
        "actualizado": datetime.now(ZoneInfo("America/Costa_Rica")).isoformat(timespec="seconds"),
        "ventana_dias": 60,
        "zonas": zonas,
        "eventos": proximos,
        "locales": locales,
    }
    (ROOT / "data" / "app.json").write_text(json.dumps(app_data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(json.dumps({
        "agregados": agregados,
        "vencidos_eliminados": vencidos,
        "total": len(vigentes),
    }))


if __name__ == "__main__":
    main()
