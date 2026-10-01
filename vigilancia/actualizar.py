#!/usr/bin/env python3
"""Actualizador de cartelera de Cazando Chivos.

Fusiona eventos nuevos en data/eventos.json:
  - ignora eventos sin banda/bar/fecha
  - deduplica por (bar, fecha, banda)
  - elimina eventos vencidos (fecha < hoy en America/Costa_Rica)
  - ordena por fecha, hora, bar
  - agrega a data/locales.json los bares nuevos (con direccion del evento)

Uso: actualizar.py [nuevos.json]
donde nuevos.json es una lista de objetos evento con los mismos campos
que data/eventos.json (banda, bar, fecha AAAA-MM-DD, hora, cover, flyer, ...).
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
EVENTOS = ROOT / "data" / "eventos.json"
LOCALES = ROOT / "data" / "locales.json"


def hoy_cr() -> str:
    return datetime.now(ZoneInfo("America/Costa_Rica")).strftime("%Y-%m-%d")


def clave(e: dict) -> tuple:
    return (
        str(e.get("bar", "")).strip().lower(),
        str(e.get("fecha", "")),
        str(e.get("banda", "")).strip().lower(),
    )


def main() -> None:
    nuevos = json.loads(Path(sys.argv[1]).read_text()) if len(sys.argv) > 1 else []
    eventos = json.loads(EVENTOS.read_text())

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
    vigentes = [e for e in eventos if str(e.get("fecha", "")) >= hoy]
    vencidos = len(eventos) - len(vigentes)
    vigentes.sort(key=lambda e: (e.get("fecha", ""), e.get("hora") or "23:59", e.get("bar", "")))
    EVENTOS.write_text(json.dumps(vigentes, ensure_ascii=False, indent=1) + "\n")

    locales = json.loads(LOCALES.read_text())
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
    LOCALES.write_text(json.dumps(locales, ensure_ascii=False, indent=1) + "\n")

    print(json.dumps({
        "agregados": agregados,
        "vencidos_eliminados": vencidos,
        "total": len(vigentes),
    }))


if __name__ == "__main__":
    main()
