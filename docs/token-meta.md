# Token de Meta (Facebook) — guía exacta

Sirve para que la vigilancia lea los posts + foto ORIGINAL de cada página de bar.
Sin esto, Facebook se omite y se sigue con webs abiertas + reportes.

## Una sola vez (tu cuenta)

1. Entra a developers.facebook.com → **Mis apps** → **Crear app** → tipo **Negocios**.
2. En la app: **Agregar producto** → **Facebook Login**.
3. Abre **Graph API Explorer** (herramientas), elige tu app arriba a la derecha.
4. **Permisos** → agrega `pages_show_list`, `pages_read_engagement` → **Generar token** (acepta con tu Facebook).
5. Alárgalo a 60 días en tu navegador:
   `https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=TOKEN_CORTO`
6. Guárdalo en el repo (nunca en código):
   `gh secret set META_TOKEN --repo josueluz89/cazando-chivos` y pega el token.

## Por cada bar (un clic cada uno)

1. El admin de la página del bar abre tu link de Facebook Login y autoriza.
2. Consigue su Page ID (la URL de la página o Graph: `/{nombre-pagina}?fields=id`).
3. Agrégalo a `vigilancia/meta_pages.json`:
   `{"Bar Legendario": {"page_id": "123456"}}`
4. Commit + push. Desde la próxima corrida (9am/6pm) sus posts entran solos.

## Permanente (opcional, recomendado)

Configuración del negocio → **Usuarios del sistema** → crea uno con acceso a las
páginas → genera su token → `gh secret set META_TOKEN` con ese. No vence.

## Revocar

App → Configuración → elimina la app, o quita el permiso desde tu Facebook
(Configuración → Apps y sitios web). El workflow sigue funcionando sin token.
