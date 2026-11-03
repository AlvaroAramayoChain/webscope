# 🔎 webscope

[![CI](https://github.com/AlvaroAramayoChain/webscope/actions/workflows/ci.yml/badge.svg)](https://github.com/AlvaroAramayoChain/webscope/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**webscope** is a command-line tool that takes a URL and, in seconds, gives you a clear summary of the website: what it is about, how many pages it has, which technologies it uses, its keywords, and whether it is a website or a web app.
The interface is bilingual (Spanish / English), and there is a JSON output for integrating it with other tools.

<!-- Demo: record with asciinema/vhs and uncomment
![webscope in action](docs/demo.gif)
-->

```
$ webscope excalidraw.com
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

## Contents

- [Installation](#installation)
- [Usage](#usage)
- [Interface language](#interface-language)
- [Output examples](#output-examples)
- [How it works](#how-it-works)
- [Limitations](#limitations)
- [Project structure](#project-structure)
- [Tests and quality](#tests-and-quality)
- [Roadmap](#roadmap)
- [License](#license)

## Installation

Requires **Python 3.10 or newer**.

```bash
git clone https://github.com/AlvaroAramayoChain/webscope.git
cd webscope
pip install .
```

Optional: `pip install ".[fast]"` also installs `lxml`, a faster HTML parser. Without it, webscope falls back to the standard library's `html.parser`.

### Development mode

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # includes pytest, responses, ruff and lxml
```

## Usage

```bash
webscope https://example.com                 # regular analysis
webscope example.com                         # no scheme: https:// is assumed
webscope https://example.com --max-pages 100 # crawl limit when there is no sitemap (default 50)
webscope https://example.com --json          # JSON only, on stdout
webscope https://example.com --lang es       # Spanish interface for this run only
webscope https://example.com --verbose       # signals, HTTP details and crawl progress
webscope https://example.com --no-color      # no colors (NO_COLOR is honored too)
webscope --change-lang                       # pick the interface language again
python -m webscope https://example.com       # same thing, without the entry point
```

| Exit code | Meaning |
|---|---|
| `0` | Success |
| `1` | Network or URL error (DNS, timeout, SSL, 4xx/5xx, non-HTML content) |
| `2` | Usage error (missing URL, invalid `--lang`, `--max-pages` < 1...) |

Errors are always shown as a short, translated message, never as a stack trace:

```
$ webscope no-such-domain-zzz.invalid --lang en
Error: Could not resolve the domain no-such-domain-zzz.invalid. Is it spelled
correctly?
```

## Interface language

### First run

The first time you run webscope in a terminal (without `--lang` and with no saved preference), this menu appears before the analysis starts:

```
Select language / Elegí idioma
  1) Español
  2) English
>
```

It accepts `1`, `2`, `es` or `en` (case-insensitive). If the answer is invalid it asks again, and after 3 attempts it falls back to Spanish. The choice is saved and the analysis continues in that language. Later runs use the saved language without asking.

### `--lang` and `--change-lang`

- `--lang es|en` takes precedence over everything, skips the menu and **does not change** the saved language.
- `webscope --change-lang` shows the menu again and saves the new choice (works with or without a URL).

### Priority order

```
--lang  >  saved language  >  menu (interactive only)  >  system language
```

In non-interactive mode (redirected stdin, pipes, CI) or with `--json`, the menu is **never** shown: webscope uses `--lang`, then the saved language, then the system one (`LANG`/locale: anything starting with `es` → Spanish, otherwise → English).

> The interface language is independent of the language of the analyzed website. You can use the interface in English and analyze a Spanish website: the summary and the keywords stay in the website's original language.

### Where the preference is stored

| System | File |
|---|---|
| Linux / macOS | `~/.config/webscope/config.json` (or `$XDG_CONFIG_HOME/webscope/config.json`) |
| Windows | `%APPDATA%\webscope\config.json` |
| Any | `$WEBSCOPE_CONFIG_DIR/config.json` if that variable is set |

If the file is corrupt or the folder is not writable, webscope keeps working normally; it just does not remember the choice.

## Output examples

### In Spanish

```
$ webscope www.argentina.gob.ar --lang es
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

### In English

```
$ webscope python.org --lang en --max-pages 20
🔎 python.org
──────────────────────────────────────────────────────────────────────────────
About         Welcome to Python.org: The official home of the Python
              Programming Language
Type          Website (confidence: high)
Pages         at least 20 (via link crawl)
Technologies  HTML, CSS, JavaScript · jQuery · nginx
Keywords      python, software, welcome, programming, download, community,
              data, language
```

### With `--verbose`

Shows the crawl progress (on stderr) and a section with the details and the signals that decided the site type:

```
─────────────────────────────────── Details ───────────────────────────────────
Final URL      https://www.python.org/
HTTP status    200
Server         nginx
Response       352 ms
Site language  en
UI language    en
Score          app 1 · site 10
Signals        +1 app: Many JavaScript bundles
               +3 site: Lots of static text
               +2 site: Several content paragraphs
               +2 site: Classic navigation with many links
               +1 site: Many headings and sections
               +2 site: Informational pages (about, contact, services...)
```

### JSON

**JSON keys are always in English** and never change with the interface language, so integrations do not break. Values that are codes (`site`/`app`, `low`/`medium`/`high`, `sitemap`/`crawl`) are not translated either; free text such as `summary` stays in the website's original language.

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

(Signal list trimmed for the example.)

## How it works

```
URL ─► fetcher ─► HTML + headers ─┬─► topic      ─► summary
                                  ├─► tech       ─► technologies
                                  ├─► keywords   ─► keywords + site language
                                  ├─► site_type  ─► site / app + confidence + signals
                  crawler ◄───────┘
                  (robots.txt, sitemap.xml or BFS crawl) ─► page count
                                  │
                                  ▼
                       report (rich / JSON, translated with i18n)
```

The **analyzers are pure functions**: they take the HTML (and the headers when needed) and return data and codes, without doing any network calls and without knowing the interface language. All network code lives in `fetcher` and `crawler`, and translation happens only in `report`.

- **fetcher**: downloads the home page with `requests` (10 s timeout, custom `webscope/<version>` user agent, redirects, 5 MB limit) and turns any failure into an error with a stable code (`dns`, `timeout`, `ssl`, `http`, `not_html`...).
- **crawler**: honors `robots.txt`. It looks for the sitemap declared in `robots.txt` or at `/sitemap.xml`, supports *sitemap indexes* (with a depth limit) and `.xml.gz` sitemaps. Without a sitemap, it follows same-domain internal links breadth-first up to `--max-pages`, pausing 0.3 s between requests and deduplicating URLs (no fragments, no trailing slash). If it stops at the limit, it reports "at least N".
- **topic**: uses `meta description` / `og:description` and the `<title>`. Without a description, it builds an extractive summary from the most representative sentences of the main text (ignoring `nav`, `footer`, `script` and `style`). About 200 characters max.
- **tech**: detects technologies through signatures over the HTML and the headers. Signatures are a declarative table in [`tech.py`](src/webscope/analyzers/tech.py): adding a technology means adding one line. It covers HTML/CSS/JS, TypeScript, React, Next.js, Vue, Nuxt, Angular, Svelte, Astro, jQuery, Bootstrap, Tailwind, WordPress, Shopify, Wix, Drupal, Django, Laravel, Rails, PHP, ASP.NET, Cloudflare, nginx, Apache, Vercel, Netlify and more.
- **keywords**: counts words after removing Spanish and English stopwords (lists bundled in the code), numbers and words shorter than 3 letters. The title, headings and `meta keywords` weigh more, and singular/plural forms are merged (`zapatilla`/`zapatillas`). The website's language is detected from `<html lang>` or from the dominant stopwords.
- **site_type**: a scoring system. Points for *web app*: a nearly empty `#root`/`#app`/`#__next` container, many JS bundles, `manifest.json`, a service worker, routes like `/login`, `/dashboard` or `/api/`, password forms. Points for *website*: lots of static text, paragraphs, classic navigation, a blog or articles, informational pages, a CMS generator. Confidence depends on the score gap (`--verbose` lists every signal).

## Limitations

Being honest about what a static analysis of the home page can and cannot know:

- **The backend is only detected when it leaves clues** (headers like `X-Powered-By`, cookies like `laravel_session`, tokens like `csrfmiddlewaretoken`). Many sites hide them on purpose.
- **Pure SPAs** (React/Vue compiled without SSR) usually ship the framework inside hashed bundles, so webscope may detect "web app" but not the specific framework. It does not download or analyze JavaScript bundles.
- **It does not run JavaScript**: the summary and keywords come from the HTML the server returns. In an SPA the real content may not be there.
- **The page count is approximate**: with a sitemap it counts the declared URLs (which may be outdated, hence the `~`); without one, only pages reachable through links from the home page, up to `--max-pages`. At most 25 child sitemaps are read.
- **Simple language detection**: `<html lang>` or Spanish/English stopwords. For other languages, keywords may include stopwords.
- Websites that block bots or require login/captcha return 403/503 errors or partial content.
- `click`'s own messages for unknown options (for example `No such option`) and the word `Usage:` in the help stay in English.

## Project structure

```
webscope/
├── pyproject.toml              # packaging (hatchling), dependencies, ruff and pytest
├── .github/workflows/ci.yml    # ruff + pytest on Python 3.10, 3.11 and 3.12
├── src/webscope/
│   ├── __init__.py             # version
│   ├── __main__.py             # python -m webscope
│   ├── cli.py                  # typer: arguments, language menu, errors, exit codes
│   ├── core.py                 # wires network + analyzers into an AnalysisResult
│   ├── i18n.py                 # es/en strings and t()
│   ├── config.py               # saved language preference
│   ├── fetcher.py              # requests: timeout, user agent, coded errors
│   ├── crawler.py              # robots.txt, sitemap(s) and BFS crawl
│   ├── parsing.py              # BeautifulSoup (lxml when available) and visible text
│   ├── models.py               # immutable dataclasses (AnalysisResult, etc.)
│   ├── report.py               # rich and JSON rendering; turns codes into text
│   └── analyzers/
│       ├── _text.py            # tokenizer and es/en stopwords
│       ├── topic.py
│       ├── tech.py
│       ├── keywords.py
│       └── site_type.py
└── tests/
    ├── fixtures/               # WordPress, React SPA, static site, Next.js + Tailwind
    └── test_*.py
```

## Tests and quality

```bash
pytest          # 170 tests, no real requests
ruff check .    # lint
ruff format .   # formatting
```

- Tests **never make real requests**: the network is mocked with [`responses`](https://github.com/getsentry/responses), and a fixture blocks any attempt to open a socket.
- They **never touch your real configuration**: each test uses a temporary folder through `WEBSCOPE_CONFIG_DIR`.
- They cover each analyzer with fixtures, the crawler (sitemap, sitemap index, gzip, limits, robots.txt, BFS), fetcher errors, the CLI through `typer.testing.CliRunner` (language priority, menu with valid and invalid input, corrupt or unwritable config, `--json` without a menu, exit codes), key parity between languages, and that JSON keys stay in English.

## Roadmap

- [ ] **More technologies**: add signatures to the table in `tech.py` (one line per technology) and, optionally, analyze JS bundles to detect frameworks in SPAs.
- [ ] **More languages**: adding a language means adding one dictionary to [`i18n.py`](src/webscope/i18n.py) with the same keys; the menu, `--lang` and validation pick it up automatically, and the parity test flags any missing key.
- [ ] **Markdown export** (`--markdown`) to paste the report into issues or docs.
- [ ] **Basic SEO checks**: missing or duplicated titles and descriptions, image `alt` text, `canonical`, `hreflang`.
- [ ] **Publish to PyPI** so it can be installed with `pip install webscope`.

## License

[MIT](LICENSE) © 2026 Alvaro Aramayo Chain
