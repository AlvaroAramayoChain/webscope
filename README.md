# 🔎 webscope

[![CI](https://github.com/AlvaroAramayoChain/webscope/actions/workflows/ci.yml/badge.svg)](https://github.com/AlvaroAramayoChain/webscope/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**webscope** es una herramienta de consola que recibe una URL y te devuelve, en segundos, un resumen claro de la web: de qué trata, cuántas páginas tiene, qué tecnologías usa, sus palabras clave y si es un sitio o una app web.
La interfaz es bilingüe (español / inglés) y también tiene salida JSON para integrarla con otras herramientas.

<!-- Demo: grabar con asciinema/vhs y descomentar
![webscope en acción](docs/demo.gif)
-->

```
$ webscope www.argentina.gob.ar
🔎 argentina.gob.ar
──────────────────────────────────────────────────────────────────────────────
De qué trata    Portal oficial del Estado argentino. Conocé cómo hacer trámites
                en organismos públicos, tramitalos en línea y recibí servicios
                digitales y beneficios.
Tipo            Sitio web (confianza: media)
Páginas         ~176046 (vía sitemap.xml)
Tecnologías     HTML, CSS, JavaScript, PHP · Drupal · jQuery, Bootstrap ·
                Cloudflare
Palabras clave  servicios, argentina, organismos, argentino, gobierno,
                trámites, digital, beneficios
```

## Índice

- [Instalación](#instalación)
- [Uso](#uso)
- [Idioma de la interfaz](#idioma-de-la-interfaz)
- [Ejemplos de salida](#ejemplos-de-salida)
- [Cómo funciona](#cómo-funciona)
- [Limitaciones](#limitaciones)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Tests y calidad](#tests-y-calidad)
- [Roadmap](#roadmap)
- [Licencia](#licencia)

## Instalación

Requiere **Python 3.10 o superior**.

```bash
git clone https://github.com/AlvaroAramayoChain/webscope.git
cd webscope
pip install .
```

Opcional: con `pip install ".[fast]"` se instala `lxml`, un parser HTML más rápido. Si no está, webscope usa `html.parser` de la librería estándar.

### Modo desarrollo

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # incluye pytest, responses, ruff y lxml
```

## Uso

```bash
webscope https://ejemplo.com                 # análisis normal
webscope ejemplo.com                         # sin esquema: se asume https://
webscope https://ejemplo.com --max-pages 100 # límite del rastreo si no hay sitemap (default 50)
webscope https://ejemplo.com --json          # solo JSON por stdout
webscope https://ejemplo.com --lang en       # interfaz en inglés solo para esta ejecución
webscope https://ejemplo.com --verbose       # señales, detalles HTTP y progreso del rastreo
webscope https://ejemplo.com --no-color      # sin colores (también respeta NO_COLOR)
webscope --change-lang                       # vuelve a elegir el idioma de la interfaz
python -m webscope https://ejemplo.com       # equivalente sin el entry point
```

| Código de salida | Significado |
|---|---|
| `0` | Todo OK |
| `1` | Error de red o de URL (DNS, timeout, SSL, 4xx/5xx, contenido no HTML) |
| `2` | Error de uso (falta la URL, `--lang` inválido, `--max-pages` < 1...) |

Los errores siempre se muestran como un mensaje corto y traducido, nunca como un stack trace:

```
$ webscope no-existe-dominio-zzz.invalid --lang en
Error: Could not resolve the domain no-existe-dominio-zzz.invalid. Is it spelled
correctly?
```

## Idioma de la interfaz

### Primera ejecución

La primera vez que usás webscope en una terminal (sin `--lang` y sin preferencia guardada) aparece este menú antes de analizar:

```
Select language / Elegí idioma
  1) Español
  2) English
>
```

Acepta `1`, `2`, `es` o `en` (sin distinguir mayúsculas). Si la opción no es válida vuelve a preguntar, y después de 3 intentos usa español. La elección se guarda y el análisis sigue en ese idioma. Las siguientes ejecuciones usan el idioma guardado sin preguntar.

### `--lang` y `--change-lang`

- `--lang es|en` tiene prioridad sobre todo, no muestra el menú y **no modifica** el idioma guardado.
- `webscope --change-lang` muestra el menú otra vez y guarda la nueva elección (funciona con o sin URL).

### Orden de prioridad

```
--lang  >  idioma guardado  >  menú (solo si es interactivo)  >  idioma del sistema
```

En modo no interactivo (stdin redirigido, pipes, CI) o con `--json`, **nunca** se muestra el menú: se usa `--lang`, si no el idioma guardado y si no el del sistema (`LANG`/locale: si empieza con `es` → español, si no → inglés).

> El idioma de la interfaz es independiente del idioma de la web analizada. Podés ver la interfaz en inglés y analizar una web en español: el resumen y las palabras clave quedan en el idioma original de la web.

### Dónde se guarda la preferencia

| Sistema | Archivo |
|---|---|
| Linux / macOS | `~/.config/webscope/config.json` (o `$XDG_CONFIG_HOME/webscope/config.json`) |
| Windows | `%APPDATA%\webscope\config.json` |
| Cualquiera | `$WEBSCOPE_CONFIG_DIR/config.json` si definís esa variable |

Si el archivo está corrupto o la carpeta no se puede escribir, webscope sigue funcionando normalmente; solo no recuerda la elección.

## Ejemplos de salida

### En español

```
$ webscope python.org --lang es --max-pages 20
🔎 python.org
──────────────────────────────────────────────────────────────────────────────
De qué trata    Welcome to Python.org: The official home of the Python
                Programming Language
Tipo            Sitio web (confianza: alta)
Páginas         al menos 20 (vía rastreo de links)
Tecnologías     HTML, CSS, JavaScript · jQuery · nginx
Palabras clave  python, software, welcome, programming, download, community,
                data, language
```

### En inglés

```
$ webscope excalidraw.com --lang en
🔎 excalidraw.com
──────────────────────────────────────────────────────────────────────────────
About         Excalidraw is a virtual collaborative whiteboard tool that lets
              you easily sketch diagrams that have a hand-drawn feel to them.
Type          Web app (confidence: high)
Pages         ~1 (via sitemap.xml)
Technologies  HTML, CSS, JavaScript · Vercel
Keywords      excalidraw, whiteboard, collaborative, virtual, tool, sketch,
              diagrams, hand
```

### Con `--verbose`

Muestra el progreso del rastreo (por stderr) y una sección con los detalles y las señales que decidieron el tipo de web:

```
────────────────────────────────── Detalles ──────────────────────────────────
URL final         https://www.python.org/
Estado HTTP       200
Servidor          nginx
Respuesta         469 ms
Idioma de la web  en
Idioma interfaz   es
Puntaje           app 1 · sitio 10
Señales           +1 app: Muchos bundles de JavaScript
                  +3 sitio: Mucho texto estático
                  +2 sitio: Varios párrafos de contenido
                  +2 sitio: Navegación clásica con muchos links
                  +1 sitio: Muchos títulos y secciones
                  +2 sitio: Páginas informativas (nosotros, contacto,
                  servicios...)
```

### JSON

Las **claves del JSON están siempre en inglés** y no cambian con el idioma de la interfaz, así las integraciones no se rompen. Los valores que son códigos (`site`/`app`, `low`/`medium`/`high`, `sitemap`/`crawl`) tampoco se traducen; los textos libres como `summary` quedan en el idioma original de la web.

```
$ webscope excalidraw.com --json --lang es
```

```json
{
  "url": "https://excalidraw.com",
  "final_url": "https://excalidraw.com/",
  "domain": "excalidraw.com",
  "ui_lang": "es",
  "site_lang": "en",
  "summary": "Excalidraw is a virtual collaborative whiteboard tool that lets you easily sketch diagrams that have a hand-drawn feel to them.",
  "site_type": {
    "type": "app",
    "confidence": "high",
    "scores": { "app": 9, "site": 0 },
    "signals": [
      { "code": "spa_root", "target": "app", "weight": 3 },
      { "code": "little_text", "target": "app", "weight": 2 },
      { "code": "module_scripts", "target": "app", "weight": 1 }
    ]
  },
  "pages": { "count": 1, "source": "sitemap", "at_least": false },
  "technologies": [
    { "name": "HTML", "category": "language" },
    { "name": "CSS", "category": "language" },
    { "name": "JavaScript", "category": "language" },
    { "name": "Vercel", "category": "server" }
  ],
  "keywords": ["excalidraw", "whiteboard", "collaborative", "virtual", "tool", "sketch", "diagrams", "hand"],
  "http": { "status": 200, "server": "Vercel", "elapsed_ms": 232 },
  "webscope_version": "0.1.0"
}
```

(Lista de señales recortada para el ejemplo.)

## Cómo funciona

```
URL ─► fetcher ─► HTML + headers ─┬─► topic      ─► resumen
                                  ├─► tech       ─► tecnologías
                                  ├─► keywords   ─► palabras clave + idioma de la web
                                  ├─► site_type  ─► sitio / app + confianza + señales
                  crawler ◄───────┘
                  (robots.txt, sitemap.xml o rastreo BFS) ─► cantidad de páginas
                                  │
                                  ▼
                       report (rich / JSON, traducido con i18n)
```

Los **analizadores son funciones puras**: reciben el HTML (y los headers cuando hace falta) y devuelven datos y códigos, sin hacer red y sin conocer el idioma de la interfaz. Toda la red está aislada en `fetcher` y `crawler`, y la traducción ocurre solo en `report`.

- **fetcher**: descarga la home con `requests` (timeout de 10 s, user-agent propio `webscope/<versión>`, redirects, límite de 5 MB) y convierte cualquier falla en un error con código estable (`dns`, `timeout`, `ssl`, `http`, `not_html`...).
- **crawler**: respeta `robots.txt`. Busca el sitemap declarado en `robots.txt` o en `/sitemap.xml`, soporta *sitemap index* (con límite de profundidad) y sitemaps `.xml.gz`. Si no hay sitemap, sigue links internos del mismo dominio en BFS hasta `--max-pages`, con una pausa de 0,3 s entre requests y URLs deduplicadas (sin fragmentos y sin barra final). Si corta por el límite informa "al menos N".
- **topic**: usa `meta description` / `og:description` y el `<title>`. Si no hay descripción, arma un resumen extractivo con las frases más representativas del texto principal (ignorando `nav`, `footer`, `script` y `style`). Máximo ~200 caracteres.
- **tech**: detecta tecnologías por firmas sobre el HTML y los headers. Las firmas son una tabla declarativa en [`tech.py`](src/webscope/analyzers/tech.py): agregar una tecnología es sumar una línea. Incluye HTML/CSS/JS, TypeScript, React, Next.js, Vue, Nuxt, Angular, Svelte, Astro, jQuery, Bootstrap, Tailwind, WordPress, Shopify, Wix, Drupal, Django, Laravel, Rails, PHP, ASP.NET, Cloudflare, nginx, Apache, Vercel, Netlify y más.
- **keywords**: cuenta palabras quitando stopwords en español e inglés (listas incluidas en el código), números y palabras de menos de 3 letras. El título, los headings y `meta keywords` pesan más, y une singular/plural (`zapatilla`/`zapatillas`). Detecta el idioma de la web con `<html lang>` o por las stopwords dominantes.
- **site_type**: un sistema de puntaje. Suman a *app web*: contenedor `#root`/`#app`/`#__next` casi vacío, muchos bundles JS, `manifest.json`, service worker, rutas como `/login`, `/dashboard` o `/api/`, formularios de contraseña. Suman a *sitio web*: mucho texto estático, párrafos, navegación clásica, blog/artículos, páginas informativas, generador CMS. La confianza depende de la diferencia de puntaje (`--verbose` muestra cada señal).

## Limitaciones

Siendo honestos sobre lo que un análisis estático de la home puede y no puede saber:

- **El backend solo se detecta si deja pistas** (headers como `X-Powered-By`, cookies como `laravel_session`, tokens como `csrfmiddlewaretoken`). Muchos sitios los ocultan a propósito.
- **Las SPA puras** (React/Vue compilados sin SSR) suelen traer el framework dentro de bundles con hash, por lo que a veces se detecta "app web" pero no el framework concreto. webscope no descarga ni analiza los bundles de JavaScript.
- **No ejecuta JavaScript**: el resumen y las palabras clave salen del HTML que entrega el servidor. En una SPA el contenido real puede no estar ahí.
- **El conteo de páginas es aproximado**: con sitemap se cuentan las URLs declaradas (que pueden estar desactualizadas, por eso el `~`); sin sitemap, solo las alcanzables por links desde la home, hasta `--max-pages`. Se leen hasta 25 sitemaps hijos.
- **Detección de idioma simple**: `<html lang>` o stopwords en español/inglés. Para otros idiomas las palabras clave pueden incluir stopwords.
- Webs que bloquean bots o exigen login/captcha devuelven errores 403/503 o contenido parcial.
- Los mensajes propios de `click` para opciones desconocidas (por ejemplo `No such option`) y la palabra `Usage:` de la ayuda quedan en inglés.

## Estructura del proyecto

```
webscope/
├── pyproject.toml              # empaquetado (hatchling), dependencias, ruff y pytest
├── .github/workflows/ci.yml    # ruff + pytest en Python 3.10, 3.11 y 3.12
├── src/webscope/
│   ├── __init__.py             # versión
│   ├── __main__.py             # python -m webscope
│   ├── cli.py                  # typer: argumentos, menú de idioma, errores, exit codes
│   ├── core.py                 # orquesta red + analizadores y arma el AnalysisResult
│   ├── i18n.py                 # textos es/en y t()
│   ├── config.py               # preferencia de idioma guardada
│   ├── fetcher.py              # requests: timeout, user-agent, errores con código
│   ├── crawler.py              # robots.txt, sitemap(s) y rastreo BFS
│   ├── parsing.py              # BeautifulSoup (lxml si está) y texto visible
│   ├── models.py               # dataclasses inmutables (AnalysisResult, etc.)
│   ├── report.py               # render con rich y JSON; traduce códigos a texto
│   └── analyzers/
│       ├── _text.py            # tokenizador y stopwords es/en
│       ├── topic.py
│       ├── tech.py
│       ├── keywords.py
│       └── site_type.py
└── tests/
    ├── fixtures/               # WordPress, SPA React, sitio estático, Next.js + Tailwind
    └── test_*.py
```

## Tests y calidad

```bash
pytest          # 170 tests, sin requests reales
ruff check .    # lint
ruff format .   # formato
```

- Los tests **nunca hacen requests reales**: la red se simula con [`responses`](https://github.com/getsentry/responses) y un fixture bloquea cualquier intento de abrir un socket.
- **Nunca tocan tu configuración real**: cada test usa una carpeta temporal vía `WEBSCOPE_CONFIG_DIR`.
- Cubren cada analizador con fixtures, el crawler (sitemap, sitemap index, gzip, límites, robots.txt, BFS), los errores del fetcher, el CLI con `typer.testing.CliRunner` (prioridad de idioma, menú con entradas válidas e inválidas, config corrupta o sin permisos, `--json` sin menú, exit codes), la paridad de claves entre idiomas y que el JSON mantenga sus claves en inglés.

## Roadmap

- [ ] **Más tecnologías**: sumar firmas a la tabla de `tech.py` (una línea por tecnología) y, opcionalmente, analizar los bundles JS para detectar frameworks en SPAs.
- [ ] **Más idiomas**: agregar un idioma es sumar un diccionario en [`i18n.py`](src/webscope/i18n.py) con las mismas claves; el menú, `--lang` y la validación lo toman solos, y el test de paridad avisa si falta alguna clave.
- [ ] **Exportar a Markdown** (`--markdown`) para pegar el reporte en issues o documentación.
- [ ] **Análisis de SEO básico**: títulos y descriptions duplicados o ausentes, `alt` en imágenes, `canonical`, `hreflang`.
- [ ] **Publicar en PyPI** para instalar con `pip install webscope`.

## Licencia

[MIT](LICENSE) © 2026 Alvaro Aramayo Chain
