#!/usr/bin/env python3
"""Fuente Meta (Facebook) para la vigilancia. Solo stdlib.

Usa Graph API con token largo (60 dias) o de usuario del sistema.
Sin token configurado no hace nada (la vigilancia sigue con webs abiertas).

Env:
  META_TOKEN   token de app/usuario con pages_read_engagement
Config (vigilancia/meta_pages.json):
  {"Bar Legendario": {"page_id": "123..."}, ...}

Devuelve por bar: posts recientes con mensaje + foto ORIGINAL (full_picture)
y foto de perfil (logo). Nunca screenshots.
"""
import json
import os
import urllib.parse
import urllib.request

API = "https://graph.facebook.com/v21.0"
TIMEOUT = 20


def gget(path, token, params=None):
    q = dict(params or {})
    q["access_token"] = token
    url = f"{API}/{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, headers={"User-Agent": "CazadorChivos/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def page_posts(page_id, token, limit=10):
    return gget(f"{page_id}/posts",
                token,
                {"fields": "message,created_time,full_picture,permalink_url",
                 "limit": limit}).get("data", [])


def page_logo_url(page_id):
    return f"{API}/{page_id}/picture?type=large&redirect=false"


def load_map(base):
    p = os.path.join(base, "meta_pages.json")
    if os.path.exists(p):
        return json.load(open(p, encoding="utf-8"))
    return {}


def token():
    return os.environ.get("META_TOKEN", "").strip()
