# 🔎 webscope

**Español** | [English](README.md)

[![CI](https://github.com/AlvaroAramayoChain/webscope/actions/workflows/ci.yml/badge.svg)](https://github.com/AlvaroAramayoChain/webscope/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.0-informational)](CHANGELOG.md)

**webscope** es una herramienta de **reconocimiento pasivo** para la línea de comandos. Le
das una URL y en unos segundos te devuelve un primer plano del objetivo, pensado para
analistas de ciberseguridad, auditores y desarrolladores:

- **De qué trata** el sitio, en concreto: categoría (e-commerce, SaaS, blog…), descripción,
  nombre, idioma, país y tecnologías con versión.
- **Infraestructura**: IPs, reverse DNS, red (ASN), CDN/WAF/hosting, nameservers, correo y
  redirecciones.
- **TLS**: emisor, dominios cubiertos, días para vencer, protocolo y validez de la cadena.
- **Seguridad visible**: security headers con nota A–F, cookies, SPF/DMARC/DKIM,
  `security.txt`, contenido de terceros, formularios y superficie expuesta.
- **Hallazgos priorizados** por severidad, con evidencia y una recomendación corta.

Todo **sin enviar un solo payload**: solo lee lo que el sitio ya publica. La interfaz es
bilingüe (español / inglés) y la salida puede ser texto, **JSON** estable o **Markdown**
para pegar en un informe.

```
$ webscope alvaroaramayochain.github.io
🔎 alvaroaramayochain.github.io  ·  https://alvaroaramayochain.github.io/
═══════════════════════════════════════════════════════════════════════════════
 GENERAL
 De qué trata    Portfolio personal — Full stack developer based in Argentina.
                 Websites and web applications with WhatsApp and email
                 integrations, built end to end.
 Tipo            Sitio web (confianza: alta)
 Sitio           Alvaro Aramayo Chain · idioma en
 Páginas         1 (vía rastreo de links)
 Tecnologías     HTML, CSS, JavaScript · GitHub Pages · Fastly
 Palabras clave  end, work, website, alvaro, aramayo, chain, full, stack

 INFRAESTRUCTURA
 IPs             185.199.108.153 (IPv4) · 185.199.110.153 (IPv4) ·
                 2606:50c0:8001::153 (IPv6) · 2606:50c0:8003::153 (IPv6) (+4)
 Reverse DNS     cdn-185-199-108-153.github.com, cdn-185-199-110-153.github.com
 Red             AS54113 Fastly, Inc. · US
 CDN / WAF       Fastly, GitHub Pages
 Nameservers     dns1.p05.nsone.net, dns2.p05.nsone.net, dns3.p05.nsone.net,
                 dns4.p05.nsone.net
 Correo (MX)     sin MX

 TLS
 Certificado     Let's Encrypt (YR1) · vence en 56 días · TLS 1.3
 Dominios (SAN)  *.github.com, *.github.io, *.githubusercontent.com, github.com
                 (+2)

 SEGURIDAD VISIBLE
 Headers         Nota D (2/8) · faltan: CSP, X-Frame-Options,
                 X-Content-Type-Options, Referrer-Policy, Permissions-Policy
 Cookies         sin cookies
 Email           SPF: no · DMARC: no
 Otros           security.txt: no · HTTP→HTTPS: sí (301) · formularios: 0

 HALLAZGOS
 [MEDIO] Falta Content-Security-Policy
 [MEDIO] No se observó un registro DMARC
 [BAJO]  Sin protección contra framing (X-Frame-Options / frame-ancestors)
 [BAJO]  Falta X-Content-Type-Options: nosniff
 [BAJO]  No se observó un registro SPF
 [INFO]  Falta Referrer-Policy
 [INFO]  Falta Permissions-Policy
 [INFO]  No se observó /.well-known/security.txt

Reconocimiento pasivo. Las observaciones no confirman vulnerabilidades.
```

## Contenido

- [Alcance y ética](#alcance-y-ética)
- [Instalación](#instalación)
- [Uso](#uso)
- [Qué muestra cada bloque](#qué-muestra-cada-bloque)
- [Ejemplos de salida](#ejemplos-de-salida)
- [Catálogo de hallazgos](#catálogo-de-hallazgos)
- [Idioma de la interfaz](#idioma-de-la-interfaz)
- [Cómo funciona](#cómo-funciona)
- [Servicios de terceros](#servicios-de-terceros)
- [Limitaciones](#limitaciones)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Tests y calidad](#tests-y-calidad)
- [Roadmap](#roadmap)
- [Licencia](#licencia)

## Alcance y ética

> ⚠️ **Usá webscope solo sobre sitios propios, con autorización del dueño o dentro del
> alcance de un programa de bug bounty.** El mismo aviso aparece en `webscope --help`.

webscope está diseñado para ser **pasivo** a propósito. Eso se garantiza en el código, no
solo en esta documentación.

**Lo único que hace contra el objetivo:**

| Acción | Para qué |
|---|---|
| `GET` a la home (siguiendo redirecciones) | Contenido, headers, cookies, cadena de redirecciones |
| `GET /robots.txt` y sitemaps declarados | Contar páginas y respetar `Disallow` |
| `GET /.well-known/security.txt` | Ver si hay un canal para reportes |
| Un `GET http://` | Ver si redirige a HTTPS y con qué código |
| Crawl liviano de links internos (si no hay sitemap) | Contar páginas, hasta `--max-pages` |
| Hasta 5 `GET` a páginas internas (nosotros, productos, contacto, blog, docs) | Entender mejor de qué trata |
| Una conexión TLS estándar | Leer el certificado y lo negociado |
| Consultas DNS | Registros públicos, PTR y ASN |

**Lo que no hace nunca** (no existe código para eso): escaneo de puertos, fuerza bruta o
"descubrimiento" de rutas, fuzzing, intentos de login, envío de payloads, pruebas activas
de ciphers o protocolos débiles, ni explotación de ningún tipo. Los endpoints como `/admin`
o `/api` se listan **solo si aparecen referenciados en el HTML o JS**, y no se sondean.

**Buenas prácticas incluidas:**

- User-Agent identificable: `webscope/2.0.0 (+https://github.com/AlvaroAramayoChain/webscope)`.
- Respeta `robots.txt` para el crawl y para las páginas internas.
- Pausa de 0,3 s entre requests del crawl y timeouts cortos en todo.
- Los hallazgos son **observaciones**, no un veredicto. El lenguaje es prudente ("posible",
  "no se observó") y webscope nunca afirma que algo "es vulnerable". Cada observación es un
  punto de partida para que un humano la verifique.

## Instalación

Requiere **Python 3.10 o superior**.

```bash
git clone https://github.com/AlvaroAramayoChain/webscope.git
cd webscope
pip install .
```

Opcional: `pip install ".[fast]"` instala además `lxml`, un parser HTML más rápido. Sin él
se usa `html.parser` de la biblioteca estándar.

### Modo desarrollo

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # incluye pytest, responses, ruff y lxml
```

## Uso

```bash
webscope https://ejemplo.com                 # reporte completo (5 bloques)
webscope ejemplo.com                         # sin esquema se asume https://
webscope ejemplo.com --brief                 # solo el bloque GENERAL (rápido, sin DNS ni TLS)
webscope ejemplo.com --verbose               # señales, evidencias, recomendaciones y detalle
webscope ejemplo.com --json                  # JSON completo y estable, solo en stdout
webscope ejemplo.com --md                    # reporte en Markdown para notas o informes
webscope ejemplo.com --no-crawl              # no cuenta páginas
webscope ejemplo.com --rdap                  # suma datos de registro del dominio (opt-in)
webscope ejemplo.com --timeout 5             # timeout por request, conexión TLS y consulta DNS
webscope ejemplo.com --max-pages 100         # límite del crawl cuando no hay sitemap (50 por defecto)
webscope ejemplo.com --lang en               # interfaz en inglés solo para esta ejecución
webscope ejemplo.com --no-color              # sin colores (también respeta NO_COLOR)
webscope --change-lang                       # volver a elegir el idioma de la interfaz
python -m webscope ejemplo.com               # lo mismo sin el entry point
```

| Exit code | Significado |
|---|---|
| `0` | Éxito (aunque algún bloque haya quedado "no disponible") |
| `1` | Error de red o de URL al descargar la home (DNS, timeout, SSL, 4xx/5xx, no es HTML) |
| `2` | Error de uso (falta la URL, `--lang` inválido, `--max-pages` < 1, `--timeout` ≤ 0, `--json` con `--md`) |

Los errores siempre se muestran como un mensaje corto y traducido, nunca como un stack trace.

## Qué muestra cada bloque

### GENERAL: de qué trata

| Dato | Cómo se obtiene |
|---|---|
| **De qué trata** | `<Categoría> — <descripción>`. La descripción sale de la mejor fuente disponible: JSON-LD/schema.org, `meta description`, Open Graph o Twitter. Se limpia el boilerplate ("Bienvenido a…", "Home \|", el nombre del sitio repetido). Si no hay metadatos útiles, se arma un resumen extractivo con las frases más informativas de la home y de hasta 5 páginas internas, descartando banners de cookies, menús y pies. |
| **Categoría** | Diccionarios es/en de señales ponderadas: tipos de schema.org (`Product`, `BlogPosting`, `SoftwareApplication`, `Restaurant`…), `og:type`, TLD (`.gob`, `.edu`…), tecnologías (WooCommerce, Shopify…), rutas de los links (`/carrito`, `/pricing`, `/docs`…) y palabras clave. Si la confianza no alcanza, el resumen dice **`Indeterminada — <descripción>`** en vez de inventar una categoría. |
| **Tipo** | Sitio web o app web, con nivel de confianza. Para decir "app web" hace falta al menos una señal fuerte (contenedor SPA `#root`/`#app`/`#__next`, bundles JS, `manifest.json`, service worker, rutas `/login`, `/dashboard`, `/app` o `/api`, aviso de `<noscript>` o formulario de contraseña). Una página con poco texto y sin esas señales (como example.com) es "sitio web (confianza: baja)". |
| **Sitio** | Nombre (`og:site_name`, JSON-LD o título), idioma detectado y país como pista (ccTLD, dirección en schema.org o `lang` regional). |
| **Páginas** | Por `sitemap.xml` (vía `robots.txt`) o, si no hay, rastreando links internos. |
| **Tecnologías** | Firmas declarativas sobre HTML y headers, **con versión** cuando es visible (`WordPress 6.4.3`, `jQuery 3.7.1`, `nginx/1.25.3`…), agrupadas en lenguaje, CMS, e-commerce, frontend, librerías, backend, analítica, servicios, servidor y CDN. |
| **Palabras clave** | Frecuencia ponderada (título, encabezados y metas pesan más). |

### INFRAESTRUCTURA

IPs A/AAAA (y la IP efectivamente usada si difiere), reverse DNS (PTR), red (ASN,
organización y país vía Team Cymru), CDN/WAF/hosting inferido por headers (`cf-ray`,
`x-sucuri-id`, `x-akamai-*`, `x-amz-cf-id`, `x-served-by`, `via`…), CNAMEs (cloudfront,
azureedge, fastly, vercel, netlify, github.io…), organización del ASN y PTR. También
nameservers, MX (detecta MX nulo), y con `--verbose` TXT, CAA, CNAME de raíz y `www`, la
cadena completa de redirecciones y la evidencia de cada CDN. Con `--rdap` suma registrador,
fecha de creación, vencimiento y edad del dominio.

Si el objetivo es una IP se omiten las consultas que no aplican. Si es `localhost` o una IP
privada, el bloque DNS se marca "no disponible (host local o IP privada)", sin errores.

### TLS

Un único handshake estándar: emisor, SANs, fechas de validez, **días para vencer**, versión
de protocolo y cipher negociados, y si la cadena valida. Si la verificación falla, se
reporta como hallazgo (`TLS-CERT-INVALID` o `TLS-EXPIRED`) y el programa sigue. Para eso
se repite el handshake sin verificar, solo para leer el certificado.

### SEGURIDAD VISIBLE

| Fila | Qué evalúa |
|---|---|
| **Headers** | HSTS (`max-age`, `includeSubDomains`, `preload`), CSP (`unsafe-inline`, `unsafe-eval`, comodines), X-Frame-Options o `frame-ancestors`, X-Content-Type-Options, Referrer-Policy y Permissions-Policy. Puntaje sobre 8 y **nota A–F** ([criterio](docs/FINDINGS.md#criterio-del-puntaje-de-headers)). COOP/CORP/COEP se informan con `--verbose`. |
| **Cookies** | Cantidad y, por cookie, `Secure`, `HttpOnly`, `SameSite` y prefijos `__Host-`/`__Secure-`. |
| **Email** | SPF (y su política `-all`/`~all`/`?all`/`+all`), DMARC (`p=none/quarantine/reject`), DKIM en selectores comunes (solo DNS), MTA-STS y BIMI. Si una consulta DNS falla se muestra `?`, nunca "no". |
| **Otros** | `security.txt` (contacto y vencimiento), redirección HTTP→HTTPS y su código, formularios y formularios de login. |
| **Terceros** | Dominios externos de los que se cargan scripts, estilos, imágenes o iframes. |
| **Superficie** | Subdominios vistos en los SANs y en el HTML/JS, y endpoints como `/api`, `/graphql`, `/admin`, `/login`, `/wp-admin` o `/wp-json` **referenciados en el contenido**. |

Con `--verbose` se suman los valores de cada header, las fugas de versión (`Server`,
`X-Powered-By`, `X-AspNet-Version`, `X-Generator`, meta generator, comentarios HTML), el
detalle de cookies, las rutas sensibles de `robots.txt`, el contenido mixto y los recursos
sin SRI.

### HALLAZGOS

Lista ordenada por severidad (`CRÍTICO`, `ALTO`, `MEDIO`, `BAJO`, `INFO`), con colores
sobrios. Con `--verbose` cada hallazgo muestra su evidencia, una recomendación corta y su
id estable.

## Ejemplos de salida

### En inglés (`--lang en`)

```
$ webscope github.com --lang en
🔎 github.com  ·  https://github.com/
═══════════════════════════════════════════════════════════════════════════════
 GENERAL
 About          SaaS / software — Join the world's most widely adopted,
                AI-powered developer platform where millions of developers,
                businesses, and the largest open source community build
                software that…
 Type           Website (confidence: high)
 Site           GitHub · language en
 Pages          ~375 (via sitemap.xml)
 Technologies   HTML, CSS, JavaScript
 Keywords       github, developer, code, nov, stars, week, mercado, libre

 INFRASTRUCTURE
 IPs            4.228.31.150 (IPv4)
 Network        AS8075 Microsoft Corporation · US
 CDN / WAF      Microsoft Azure
 Nameservers    dns1.p08.nsone.net, dns2.p08.nsone.net, dns3.p08.nsone.net,
                dns4.p08.nsone.net
 Mail (MX)      github-com.mail.protection.outlook.com

 TLS
 Certificate    Sectigo Limited (Sectigo Public Server Authentication CA DV
                E36) · expires in 85 days · TLS 1.3
 Domains (SAN)  github.com, www.github.com

 VISIBLE SECURITY
 Headers        Grade A (7/8) · missing: Permissions-Policy
 Cookies        3 cookies · 1 without HttpOnly
 Email          SPF: ? · DMARC: p=quarantine · DKIM: google, selector1, k1, k2
 Other          security.txt: yes · HTTP→HTTPS: ? · forms: 2
 Third parties  3 domains: github.githubassets.com, images.ctfassets.net,
                videos.ctfassets.net
 Surface        subdomains: 9 · endpoints: /cmc_internal/api, /login

 FINDINGS
 [LOW]  1 cookie(s) without HttpOnly
 [INFO] Missing Permissions-Policy
 [INFO] robots.txt mentions 4 path(s) that sound sensitive
 [INFO] 28 external resource(s) without SRI (github.githubassets.com)
 [INFO] 2 sensitive endpoint(s) referenced in the content

Passive reconnaissance. Observations do not confirm vulnerabilities.
```

> `SPF: ?` y `HTTP→HTTPS: ?` significan que esa consulta no tuvo respuesta desde la red
> donde se corrió el ejemplo (el resolver local no devolvió el TXT grande y el puerto 80
> no respondió). webscope no lo convierte en un hallazgo falso.

### JSON (`--json`)

Las **claves siempre están en inglés** y el esquema es estable (`schema_version: "2.0"`).
Por stdout sale solo JSON válido; los textos de los hallazgos (`title`, `recommendation`)
van en el idioma de la interfaz. Extracto de `webscope example.com --json`:

```json
{
  "schema_version": "2.0",
  "webscope_version": "2.0.0",
  "scanned_at": "2026-11-03T05:29:14Z",
  "url": "https://example.com",
  "final_url": "https://example.com/",
  "domain": "example.com",
  "ui_lang": "es",
  "site_lang": "en",
  "general": {
    "summary": "Indeterminada — This domain is for use in documentation examples without needing permission. …",
    "category": { "code": "unknown", "confidence": "low", "score": 4, "signals": [{ "category": "docs", "reason": "kw:documentation", "weight": 4 }] },
    "site_name": "Example Domain",
    "technologies": [{ "name": "Cloudflare", "category": "cdn", "version": null }],
    "pages": { "count": 1, "source": "crawl", "at_least": false }
  },
  "infrastructure": {
    "ipv4": ["172.66.147.243", "104.20.23.154"],
    "asn": { "172.66.147.243": { "asn": 13335, "org": "Cloudflare, Inc.", "country": "US", "prefix": "172.66.144.0/20", "registry": "arin" } },
    "cdn": [{ "name": "Cloudflare", "kind": "cdn+waf", "evidence": "header cf-ray" }],
    "dns": { "ns": ["elliott.ns.cloudflare.com", "hera.ns.cloudflare.com"], "mx": ["0 ."], "dmarc": ["v=DMARC1;p=reject;sp=reject;adkim=s;aspf=s"] },
    "redirects": []
  },
  "tls": { "issuer": "SSL Corporation (Cloudflare TLS Issuing ECC CA 3)", "days_left": 52, "protocol": "TLSv1.3", "verified": true },
  "security": { "https": true, "headers": { "score": 0, "max_score": 8, "grade": "F" } },
  "findings": [
    {
      "id": "HTTP-NO-REDIRECT",
      "severity": "medium",
      "title": "http:// no redirige a https://",
      "evidence": "http:// -> 200 http://example.com/",
      "recommendation": "Redirigir todo el tráfico HTTP a HTTPS con 301."
    }
  ],
  "unavailable": {}
}
```

| Sección | Contenido |
|---|---|
| `schema_version`, `webscope_version`, `scanned_at` | Versión del esquema, de la herramienta y fecha UTC (ISO 8601) |
| `ui_lang`, `site_lang` | Idioma de la interfaz y de la web analizada |
| `general` | Resumen, descripción y fuente, categoría con señales, nombre, país, tipo, páginas, tecnologías con versión y palabras clave |
| `infrastructure` | IPs, IP conectada, PTR, ASN, CDN con evidencia, registros DNS, RDAP y redirecciones |
| `tls` | Sujeto, emisor, SANs, fechas, `days_left`, protocolo, cipher y verificación |
| `security` | Headers (checks, puntaje, nota), fugas, cookies, email, archivos, redirección HTTP, contenido y superficie |
| `findings` | Lista ordenada de `{id, severity, title, evidence, recommendation}` |
| `unavailable` | Bloques que no se pudieron completar y el código del motivo (p. ej. `"dns": "dns_timeout"`) |

Las claves de la v0.1 (`summary`, `site_type`, `pages`, `technologies`, `keywords`, `http`)
se mantienen en el nivel superior por compatibilidad.

### Markdown (`--md`)

Listo para pegar en un informe, un issue o Obsidian. Extracto de
`webscope example.com --md --lang es`:

```markdown
# 🔎 example.com

**URL:** https://example.com/
**Escaneado:** 2026-11-03T05:29:24Z · webscope 2.0.0

## TLS

| Dato | Valor |
|---|---|
| Certificado | SSL Corporation (Cloudflare TLS Issuing ECC CA 3) · vence en 52 días · TLS 1.3 |
| Dominios (SAN) | example.com, *.example.com |

## HALLAZGOS

| Severidad | ID | Hallazgo | Evidencia | Recomendación |
|---|---|---|---|---|
| MEDIO | `HTTP-NO-REDIRECT` | http:// no redirige a https:// | http:// -> 200 http://example.com/ | Redirigir todo el tráfico HTTP a HTTPS con 301. |
| MEDIO | `HDR-HSTS-MISSING` | Falta Strict-Transport-Security (HSTS) | Strict-Transport-Security: - | Agregar HSTS con max-age de al menos 6 meses (idealmente 1 año). |
| INFO | `DNS-NO-CAA` | No se observó un registro CAA | CAA: - | Publicar CAA para limitar qué CAs pueden emitir certificados. |

> Reconocimiento pasivo. Las observaciones no confirman vulnerabilidades.
```

## Catálogo de hallazgos

42 reglas declarativas e internacionalizadas, cada una con un **id estable**. La lista
completa, con severidad, qué observa y qué se recomienda, está en
[`docs/FINDINGS.md`](docs/FINDINGS.md). Resumen por familia:

| Familia | Ejemplos de ids | Severidades |
|---|---|---|
| TLS y HTTPS | `TLS-EXPIRED`, `TLS-CERT-INVALID`, `TLS-EXPIRING`, `TLS-OLD-PROTOCOL`, `HTTPS-MISSING`, `HTTP-NO-REDIRECT` | alta / media |
| Security headers | `HDR-HSTS-MISSING`, `HDR-CSP-MISSING`, `HDR-CSP-UNSAFE`, `HDR-XFO-MISSING`, `HDR-XCTO-MISSING`… | media / baja / info |
| Fugas de información | `LEAK-SERVER-VERSION`, `LEAK-POWERED-BY`, `LEAK-ASPNET-VERSION`, `LEAK-GENERATOR`, `LEAK-HTML-COMMENT` | baja / info |
| Cookies | `COOKIE-NO-SECURE`, `COOKIE-NO-HTTPONLY`, `COOKIE-NO-SAMESITE` | media / baja |
| Correo | `SPF-PERMISSIVE`, `SPF-MISSING`, `SPF-NEUTRAL`, `SPF-MULTIPLE`, `DMARC-MISSING`, `DMARC-NONE`, `DKIM-NOT-FOUND` | alta a info |
| Archivos | `SECTXT-MISSING`, `SECTXT-EXPIRED`, `ROBOTS-SENSITIVE` | baja / info |
| Contenido y formularios | `FORM-PASSWORD-HTTP`, `FORM-INSECURE-ACTION`, `CONTENT-MIXED`, `CONTENT-NO-SRI`, `FORM-EXTERNAL-ACTION`… | alta a info |
| Superficie e inventario | `SURFACE-ENDPOINTS`, `TECH-VERSIONS`, `DNS-NO-CAA` | info |

## Idioma de la interfaz

### Primera ejecución

La primera vez que corrés webscope en una terminal (sin `--lang` y sin preferencia
guardada) aparece este menú:

```
Select language / Elegí idioma
  1) Español
  2) English
>
```

Acepta `1`, `2`, `es` o `en`. Si la respuesta no es válida vuelve a preguntar, y después de
3 intentos usa español. La elección se guarda y las siguientes ejecuciones la usan sin
preguntar.

### Prioridad

```
--lang  >  idioma guardado  >  menú (solo en modo interactivo)  >  idioma del sistema
```

- `--lang es|en` gana siempre, saltea el menú y **no cambia** el idioma guardado.
- `webscope --change-lang` vuelve a mostrar el menú y guarda la nueva elección.
- En modo no interactivo (pipes, CI) o con `--json`/`--md` el menú **nunca** aparece.

> El idioma de la interfaz es independiente del idioma del sitio analizado: la descripción
> y las palabras clave quedan en el idioma original de la web.

| Sistema | Dónde se guarda la preferencia |
|---|---|
| Linux / macOS | `~/.config/webscope/config.json` (o `$XDG_CONFIG_HOME/webscope/config.json`) |
| Windows | `%APPDATA%\webscope\config.json` |
| Cualquiera | `$WEBSCOPE_CONFIG_DIR/config.json` si esa variable está definida |

## Cómo funciona

```
              ┌────────────── red (solo en estos módulos) ──────────────┐
URL ─► fetcher ──► home ──┬─► crawler   (robots.txt, sitemaps, BFS)      │
                          ├─► dnsinfo   (dnspython: registros, PTR, ASN) │  en paralelo
                          ├─► tlsprobe  (ssl/socket: un handshake)       │  (ThreadPoolExecutor)
                          └─► fetcher   (security.txt, http://, RDAP)    │
              └─────────────────────────────────────────────────────────┘
                                   │ datos crudos
                                   ▼
        analyzers/ (funciones puras: sin red, sin idioma)
        topic · category · tech · keywords · site_type · infra · tls · security · findings
                                   │ códigos estables + datos
                                   ▼
        report.py ─► texto (rich) · Markdown · JSON        i18n.py ─► es / en
```

Decisiones de diseño:

- **Red aislada**: solo `fetcher`, `crawler`, `dnsinfo` y `tlsprobe` tocan la red. Los
  analizadores son funciones puras que reciben headers, HTML o registros ya obtenidos, así
  que se testean sin mocks complicados.
- **Cada bloque falla por su cuenta**: si DNS, TLS, el crawl o RDAP fallan, el resto del
  reporte sale igual y ese bloque muestra `no disponible (motivo)`. Solo si no se puede
  descargar la home el programa termina con exit code 1.
- **"Falló" no es "no existe"**: una consulta DNS que no respondió se marca como `?` y no
  dispara hallazgos como `SPF-MISSING`.
- **Todo es declarativo**: firmas de tecnologías (`analyzers/tech.py`), reglas de CDN/WAF
  (`analyzers/infra.py`), diccionarios de categorías (`analyzers/category.py`) y catálogo
  de hallazgos (`analyzers/findings.py`). Ampliar cualquiera es sumar una entrada.
- **Los analizadores devuelven códigos**, nunca texto. `report.py` es el único que traduce,
  por eso texto, Markdown y JSON muestran exactamente la misma información.
- El análisis completo tarda unos 5–13 s en sitios reales (objetivo: menos de 15 s).

## Servicios de terceros

webscope usa solo los servicios estrictamente necesarios, todos sin API keys:

| Servicio | Cuándo | Qué se envía |
|---|---|---|
| **Resolver DNS del sistema** | Siempre (salvo `--brief`) | Los nombres a consultar del dominio objetivo |
| **Team Cymru** (`origin.asn.cymru.com`, `origin6.asn.cymru.com`, `asn.cymru.com`) | Siempre (salvo `--brief`) | Las IPs del objetivo, como consulta DNS TXT, para saber su ASN |
| **rdap.org** | Solo con `--rdap` (opt-in) | El dominio registrable, por HTTPS, para obtener los datos de registro |

`rdap.org` es opt-in justamente porque envía el dominio a un tercero por HTTP. Ningún otro
dato sale de tu máquina.

## Limitaciones

Lo que un reconocimiento pasivo puede y no puede saber:

- **El backend solo se detecta si deja pistas** (headers como `X-Powered-By`, cookies como
  `laravel_session`, tokens como `csrfmiddlewaretoken`). Muchos sitios las ocultan a propósito.
- **La categoría es heurística**: diccionarios de señales, no un modelo de lenguaje. Con poca
  evidencia, o con evidencia empatada, queda "indeterminada". Un sitio puede tener rasgos de
  varias categorías (un SaaS con blog, por ejemplo).
- **Un WAF/CDN puede ocultar el origen**: las IPs, el ASN y el reverse DNS suelen ser los del
  CDN (Cloudflare, Fastly, Akamai…), no los del servidor real. webscope no intenta
  descubrir el origen.
- **DKIM se busca solo en selectores comunes** (`default`, `google`, `selector1`, `k1`…). Que
  no se encuentre no significa que el dominio no firme su correo.
- **El conteo de páginas es aproximado**: con sitemap cuenta las URLs declaradas; sin sitemap,
  solo las alcanzables por links desde la home, hasta `--max-pages`.
- **No ejecuta JavaScript**: en una SPA pura el contenido real puede no estar en el HTML.
- **El dominio registrable es aproximado** (`ejemplo.com.ar`, `ejemplo.co.uk`…): no se usa la
  Public Suffix List para no sumar dependencias.
- Los resultados de DNS dependen del resolver: algunos resolvers hogareños no devuelven
  respuestas TXT grandes. En ese caso se muestra `?`.
- Los hallazgos son observaciones a verificar, no confirmaciones de vulnerabilidades.
- Los mensajes propios de `click` (`No such option`, `Usage:`) quedan en inglés.

## Estructura del proyecto

```
webscope/
├── pyproject.toml              # empaquetado (hatchling), dependencias, ruff y pytest
├── CHANGELOG.md
├── docs/FINDINGS.md            # catálogo de reglas de hallazgos
├── .github/workflows/ci.yml    # ruff + pytest en Python 3.10–3.13
├── src/webscope/
│   ├── cli.py                  # typer: flags, menú de idioma, errores, exit codes
│   ├── core.py                 # orquesta red + analizadores en paralelo
│   ├── fetcher.py              # [red] requests: home, redirecciones, recursos auxiliares
│   ├── crawler.py              # [red] robots.txt, sitemaps y rastreo BFS
│   ├── dnsinfo.py              # [red] dnspython: registros, PTR, ASN (Team Cymru)
│   ├── tlsprobe.py             # [red] ssl/socket: un handshake TLS estándar
│   ├── report.py               # texto (rich), Markdown y JSON; traduce códigos a texto
│   ├── i18n.py                 # textos es/en y t()
│   ├── models.py               # dataclasses inmutables
│   ├── config.py · parsing.py
│   └── analyzers/              # funciones puras, sin red
│       ├── topic.py · category.py · keywords.py · site_type.py · tech.py
│       ├── infra.py · tls.py · security.py · findings.py
│       └── _text.py
└── tests/
    ├── fixtures/               # WordPress, WooCommerce, React SPA, estático, mínimo,
    │                           # login, JSON-LD (SaaS, blog), headers buenos y malos
    └── test_*.py
```

## Tests y calidad

```bash
pytest            # 359 tests, sin ninguna request real
ruff check .      # lint
ruff format .     # formato
```

- **Sin red real**: `requests` se simula con [`responses`](https://github.com/getsentry/responses),
  `dnspython` con un resolver falso y `tlsprobe` con handshakes simulados. Además un fixture
  bloquea cualquier `connect`, `sendto` o `create_connection` real.
- **Sin tocar tu configuración**: cada test usa una carpeta temporal vía `WEBSCOPE_CONFIG_DIR`.
- Cubren cada analizador con fixtures (headers buenos y malos, WordPress/WooCommerce, SPA
  React, sitio estático, página mínima, login, JSON-LD de varios tipos, SPF/DMARC válidos
  e inválidos, certificado a punto de vencer), el catálogo de hallazgos (ids y severidades estables,
  texto en todos los idiomas, lenguaje prudente), la categoría (e-commerce, blog, SaaS,
  indeterminada), el JSON (claves en inglés iguales en ambos idiomas, `schema_version`), el
  Markdown, las **fallas parciales** (DNS caído, TLS caído o crawler roto → el reporte sale
  igual) y la paridad de claves es/en.

## Roadmap

- [ ] **Más reglas** de hallazgos y más firmas de tecnologías y CDNs.
- [ ] **Plugins**: cargar firmas, categorías y reglas desde archivos externos.
- [ ] **Exportar a SARIF** para integrarlo con GitHub Code Scanning y otras herramientas.
- [ ] **Comparar dos escaneos** (`webscope diff a.json b.json`) para ver qué cambió.
- [ ] **Más idiomas**: un diccionario nuevo en [`i18n.py`](src/webscope/i18n.py) con las
      mismas claves; el test de paridad avisa si falta alguna.
- [ ] **Publicar en PyPI** para instalarlo con `pip install webscope`.

## Licencia

[MIT](LICENSE) © 2026 Alvaro Aramayo Chain
