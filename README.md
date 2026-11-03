# 🔎 webscope

[Español](README.es.md) | **English**

[![CI](https://github.com/AlvaroAramayoChain/webscope/actions/workflows/ci.yml/badge.svg)](https://github.com/AlvaroAramayoChain/webscope/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.0.0-informational)](CHANGELOG.md)

**webscope** is a **passive reconnaissance** tool for the command line. Give it a URL and
within seconds it returns a first picture of the target, aimed at security analysts,
auditors and developers:

- **What the site is about**, in concrete terms: category (e-commerce, SaaS, blog…),
  description, name, language, country and technologies with versions.
- **Infrastructure**: IPs, reverse DNS, network (ASN), CDN/WAF/hosting, nameservers, mail and
  redirects.
- **TLS**: issuer, covered domains, days until expiry, protocol and chain validity.
- **Visible security**: security headers with an A–F grade, cookies, SPF/DMARC/DKIM,
  `security.txt`, third-party content, forms and exposed surface.
- **Prioritized findings** by severity, with evidence and a short recommendation.

All of it **without sending a single payload**: it only reads what the site already
publishes. The interface is bilingual (Spanish / English) and the output can be text, stable
**JSON** or **Markdown** to paste into a report.

```
$ webscope alvaroaramayochain.github.io --lang en
🔎 alvaroaramayochain.github.io  ·  https://alvaroaramayochain.github.io/
═══════════════════════════════════════════════════════════════════════════════
 GENERAL
 About          Personal portfolio — Full stack developer based in Argentina.
                Websites and web applications with WhatsApp and email
                integrations, built end to end.
 Type           Website (confidence: high)
 Site           Alvaro Aramayo Chain · language en
 Pages          1 (via link crawl)
 Technologies   HTML, CSS, JavaScript · GitHub Pages · Fastly
 Keywords       end, work, website, alvaro, aramayo, chain, full, stack

 INFRASTRUCTURE
 IPs            185.199.108.153 (IPv4) · 185.199.110.153 (IPv4) ·
                2606:50c0:8001::153 (IPv6) · 2606:50c0:8000::153 (IPv6) (+4)
 Reverse DNS    cdn-185-199-108-153.github.com, cdn-185-199-110-153.github.com
 Network        AS54113 Fastly, Inc. · US
 CDN / WAF      Fastly, GitHub Pages
 Nameservers    dns1.p05.nsone.net, dns2.p05.nsone.net, dns3.p05.nsone.net,
                dns4.p05.nsone.net
 Mail (MX)      no MX

 TLS
 Certificate    Let's Encrypt (YR1) · expires in 56 days · TLS 1.3
 Domains (SAN)  *.github.com, *.github.io, *.githubusercontent.com, github.com
                (+2)

 VISIBLE SECURITY
 Headers        Grade D (2/8) · missing: CSP, X-Frame-Options,
                X-Content-Type-Options, Referrer-Policy, Permissions-Policy
 Cookies        no cookies
 Email          SPF: no · DMARC: no
 Other          security.txt: no · HTTP→HTTPS: yes (301) · forms: 0

 FINDINGS
 [MEDIUM] Missing Content-Security-Policy
 [MEDIUM] No DMARC record was observed
 [LOW]    No framing protection (X-Frame-Options / frame-ancestors)
 [LOW]    Missing X-Content-Type-Options: nosniff
 [LOW]    No SPF record was observed
 [INFO]   Missing Referrer-Policy
 [INFO]   Missing Permissions-Policy
 [INFO]   No /.well-known/security.txt was observed

Passive reconnaissance. Observations do not confirm vulnerabilities.
```

## Contents

- [Scope and ethics](#scope-and-ethics)
- [Installation](#installation)
- [Usage](#usage)
- [What each block shows](#what-each-block-shows)
- [Output examples](#output-examples)
- [Findings catalog](#findings-catalog)
- [Interface language](#interface-language)
- [How it works](#how-it-works)
- [Third-party services](#third-party-services)
- [Limitations](#limitations)
- [Project structure](#project-structure)
- [Tests and quality](#tests-and-quality)
- [Roadmap](#roadmap)
- [License](#license)

## Scope and ethics

> ⚠️ **Only use webscope on your own sites, with the owner's authorization or within the
> scope of a bug bounty program.** The same notice appears in `webscope --help`.

webscope is **passive** by design, and that is enforced in the code, not only in this
documentation.

**The only things it does against the target:**

| Action | Purpose |
|---|---|
| `GET` the home page (following redirects) | Content, headers, cookies, redirect chain |
| `GET /robots.txt` and declared sitemaps | Count pages and honor `Disallow` |
| `GET /.well-known/security.txt` | Check whether there is a reporting channel |
| One `GET http://` | Check whether it redirects to HTTPS and with which status code |
| Light crawl of internal links (only when there is no sitemap) | Count pages, up to `--max-pages` |
| Up to 5 `GET`s of internal pages (about, products, contact, blog, docs) | Better understand what the site is about |
| One standard TLS connection | Read the certificate and what was negotiated |
| DNS queries | Public records, PTR and ASN |

**What it never does** (there is no code for it): port scanning, path brute forcing or
"discovery", fuzzing, login attempts, sending payloads, active testing of weak ciphers or
protocols, or exploitation of any kind. Endpoints such as `/admin` or `/api` are listed **only
when they are referenced in the HTML or JS**, and they are never probed.

**Built-in good practices:**

- Identifiable User-Agent: `webscope/2.0.0 (+https://github.com/AlvaroAramayoChain/webscope)`.
- Honors `robots.txt` for the crawl and for internal pages.
- 0.3 s pause between crawl requests and short timeouts everywhere.
- Findings are **observations**, not a verdict. The wording is cautious ("possible", "was not
  observed") and webscope never states that something "is vulnerable". Each observation is a
  starting point for a human to verify.

## Installation

Requires **Python 3.10 or newer**.

```bash
git clone https://github.com/AlvaroAramayoChain/webscope.git
cd webscope
pip install .
```

Optional: `pip install ".[fast]"` also installs `lxml`, a faster HTML parser. Without it the
standard library's `html.parser` is used.

### Development mode

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"          # includes pytest, responses, ruff and lxml
```

## Usage

```bash
webscope https://example.com                 # full report (5 blocks)
webscope example.com                         # no scheme: https:// is assumed
webscope example.com --brief                 # GENERAL block only (fast, no DNS or TLS)
webscope example.com --verbose               # signals, evidence, recommendations and details
webscope example.com --json                  # full, stable JSON, on stdout only
webscope example.com --md                    # Markdown report for notes or reports
webscope example.com --no-crawl              # do not count pages
webscope example.com --rdap                  # add domain registration data (opt-in)
webscope example.com --timeout 5             # timeout per request, TLS connection and DNS query
webscope example.com --max-pages 100         # crawl limit when there is no sitemap (default 50)
webscope example.com --lang es               # Spanish interface for this run only
webscope example.com --no-color              # no colors (NO_COLOR is honored too)
webscope --change-lang                       # pick the interface language again
python -m webscope example.com               # same thing, without the entry point
```

| Exit code | Meaning |
|---|---|
| `0` | Success (even if some block ended up "not available") |
| `1` | Network or URL error while downloading the home page (DNS, timeout, SSL, 4xx/5xx, not HTML) |
| `2` | Usage error (missing URL, invalid `--lang`, `--max-pages` < 1, `--timeout` ≤ 0, `--json` with `--md`) |

Errors are always shown as a short, translated message, never as a stack trace.

## What each block shows

### GENERAL: what the site is about

| Field | How it is obtained |
|---|---|
| **About** | `<Category> — <description>`. The description comes from the best available source: JSON-LD/schema.org, `meta description`, Open Graph or Twitter. Boilerplate is cleaned up ("Welcome to…", "Home \|", the site name repeated). When there is no useful metadata, an extractive summary is built from the most informative sentences of the home page and up to 5 internal pages, skipping cookie banners, menus and footers. |
| **Category** | Spanish/English dictionaries of weighted signals: schema.org types (`Product`, `BlogPosting`, `SoftwareApplication`, `Restaurant`…), `og:type`, TLD (`.gob`, `.edu`…), technologies (WooCommerce, Shopify…), link paths (`/cart`, `/pricing`, `/docs`…) and keywords. When confidence is not high enough, the summary says **`Undetermined — <description>`** instead of making up a category. |
| **Type** | Website or web app, with a confidence level. Saying "web app" requires at least one strong signal (SPA container `#root`/`#app`/`#__next`, JS bundles, `manifest.json`, service worker, `/login`, `/dashboard`, `/app` or `/api` routes, a `<noscript>` notice or a password form). A page with little text and none of those signals (like example.com) is "website (confidence: low)". |
| **Site** | Name (`og:site_name`, JSON-LD or title), detected language and country as a hint (ccTLD, schema.org address or regional `lang`). |
| **Pages** | From `sitemap.xml` (via `robots.txt`) or, when there is none, by crawling internal links. |
| **Technologies** | Declarative signatures over HTML and headers, **with versions** when visible (`WordPress 6.4.3`, `jQuery 3.7.1`, `nginx/1.25.3`…), grouped into language, CMS, e-commerce, frontend, libraries, backend, analytics, services, server and CDN. |
| **Keywords** | Weighted frequency (title, headings and metas weigh more). |

### INFRASTRUCTURE

A/AAAA IPs (and the IP actually used, when it differs), reverse DNS (PTR), network (ASN,
organization and country via Team Cymru), CDN/WAF/hosting inferred from headers (`cf-ray`,
`x-sucuri-id`, `x-akamai-*`, `x-amz-cf-id`, `x-served-by`, `via`…), CNAMEs (cloudfront,
azureedge, fastly, vercel, netlify, github.io…), ASN organization and PTR. Also nameservers and
MX (null MX is detected), and with `--verbose` TXT, CAA, root and `www` CNAMEs, the full
redirect chain and the evidence for each CDN. With `--rdap` it adds registrar, creation date,
expiry and domain age.

If the target is an IP, queries that do not apply are skipped. If it is `localhost` or a
private IP, the DNS block is marked "not available (local host or private IP)", with no errors.

### TLS

A single standard handshake: issuer, SANs, validity dates, **days until expiry**, negotiated
protocol version and cipher, and whether the chain validates. If verification fails it is
reported as a finding (`TLS-CERT-INVALID` or `TLS-EXPIRED`) and the program goes on. To do
that, the handshake is repeated without verification, only to read the certificate.

### VISIBLE SECURITY

| Row | What it evaluates |
|---|---|
| **Headers** | HSTS (`max-age`, `includeSubDomains`, `preload`), CSP (`unsafe-inline`, `unsafe-eval`, wildcards), X-Frame-Options or `frame-ancestors`, X-Content-Type-Options, Referrer-Policy and Permissions-Policy. Score out of 8 and an **A–F grade** ([criteria](docs/FINDINGS.md#criterio-del-puntaje-de-headers)). COOP/CORP/COEP are reported with `--verbose`. |
| **Cookies** | Count and, per cookie, `Secure`, `HttpOnly`, `SameSite` and `__Host-`/`__Secure-` prefixes. |
| **Email** | SPF (and its `-all`/`~all`/`?all`/`+all` policy), DMARC (`p=none/quarantine/reject`), DKIM on common selectors (DNS only), MTA-STS and BIMI. If a DNS query fails it shows `?`, never "no". |
| **Other** | `security.txt` (contact and expiry), HTTP→HTTPS redirect and its status code, forms and login forms. |
| **Third parties** | External domains that scripts, styles, images or iframes are loaded from. |
| **Surface** | Subdomains seen in the SANs and in the HTML/JS, and endpoints such as `/api`, `/graphql`, `/admin`, `/login`, `/wp-admin` or `/wp-json` **referenced in the content**. |

With `--verbose` it also shows each header's value, version leaks (`Server`,
`X-Powered-By`, `X-AspNet-Version`, `X-Generator`, meta generator, HTML comments), cookie
details, sensitive `robots.txt` paths, mixed content and resources without SRI.

### FINDINGS

A list sorted by severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`), with restrained
colors. With `--verbose` each finding shows its evidence, a short recommendation and its
stable id.

## Output examples

### In Spanish (`--lang es`)

```
$ webscope github.com --lang es
🔎 github.com  ·  https://github.com/
═══════════════════════════════════════════════════════════════════════════════
 GENERAL
 De qué trata    SaaS / software — Join the world's most widely adopted,
                 AI-powered developer platform where millions of developers,
                 businesses, and the largest open source community build
                 software that…
 Tipo            Sitio web (confianza: alta)
 Sitio           GitHub · idioma en
 Páginas         ~375 (vía sitemap.xml)
 Tecnologías     HTML, CSS, JavaScript
 Palabras clave  github, developer, code, nov, stars, week, mercado, libre

 INFRAESTRUCTURA
 IPs             4.228.31.150 (IPv4)
 Red             AS8075 Microsoft Corporation · US
 CDN / WAF       Microsoft Azure
 Nameservers     dns1.p08.nsone.net, dns2.p08.nsone.net, dns3.p08.nsone.net,
                 dns4.p08.nsone.net
 Correo (MX)     github-com.mail.protection.outlook.com

 TLS
 Certificado     Sectigo Limited (Sectigo Public Server Authentication CA DV
                 E36) · vence en 85 días · TLS 1.3
 Dominios (SAN)  github.com, www.github.com

 SEGURIDAD VISIBLE
 Headers         Nota A (7/8) · faltan: Permissions-Policy
 Cookies         3 cookies · 1 sin HttpOnly
 Email           SPF: ? · DMARC: p=quarantine · DKIM: google, selector1, k1, k2
 Otros           security.txt: sí · HTTP→HTTPS: ? · formularios: 2
 Terceros        3 dominios: github.githubassets.com, images.ctfassets.net,
                 videos.ctfassets.net
 Superficie      subdominios: 9 · endpoints: /cmc_internal/api, /login

 HALLAZGOS
 [BAJO] 1 cookie(s) sin HttpOnly
 [INFO] Falta Permissions-Policy
 [INFO] robots.txt menciona 4 ruta(s) que suenan sensibles
 [INFO] 28 recurso(s) externo(s) sin SRI (github.githubassets.com)
 [INFO] 2 endpoint(s) sensibles referenciados en el contenido

Reconocimiento pasivo. Las observaciones no confirman vulnerabilidades.
```

> `SPF: ?` and `HTTP→HTTPS: ?` mean that query got no answer from the network where the
> example was run (the local resolver did not return the large TXT record and port 80 did not
> respond). webscope does not turn that into a false finding.

### JSON (`--json`)

**Keys are always in English** and the schema is stable (`schema_version: "2.0"`). Only valid
JSON goes to stdout; finding texts (`title`, `recommendation`) follow the interface language.
Excerpt of `webscope example.com --json --lang en`:

```json
{
  "schema_version": "2.0",
  "webscope_version": "2.0.0",
  "scanned_at": "2026-11-03T05:30:27Z",
  "url": "https://example.com",
  "final_url": "https://example.com/",
  "domain": "example.com",
  "ui_lang": "en",
  "site_lang": "en",
  "general": {
    "summary": "Undetermined — This domain is for use in documentation examples without needing permission. …",
    "category": { "code": "unknown", "confidence": "low", "score": 4, "signals": [{ "category": "docs", "reason": "kw:documentation", "weight": 4 }] },
    "site_name": "Example Domain",
    "technologies": [{ "name": "Cloudflare", "category": "cdn", "version": null }],
    "pages": { "count": 1, "source": "crawl", "at_least": false }
  },
  "infrastructure": {
    "ipv4": ["104.20.23.154", "172.66.147.243"],
    "asn": { "104.20.23.154": { "asn": 13335, "org": "Cloudflare, Inc.", "country": "US", "prefix": "104.20.16.0/20", "registry": "arin" } },
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
      "title": "http:// does not redirect to https://",
      "evidence": "http:// -> 200 http://example.com/",
      "recommendation": "Redirect all HTTP traffic to HTTPS with a 301."
    }
  ],
  "unavailable": {}
}
```

| Section | Content |
|---|---|
| `schema_version`, `webscope_version`, `scanned_at` | Schema version, tool version and UTC date (ISO 8601) |
| `ui_lang`, `site_lang` | Interface language and the analyzed site's language |
| `general` | Summary, description and its source, category with signals, name, country, type, pages, technologies with versions and keywords |
| `infrastructure` | IPs, connected IP, PTR, ASN, CDN with evidence, DNS records, RDAP and redirects |
| `tls` | Subject, issuer, SANs, dates, `days_left`, protocol, cipher and verification |
| `security` | Headers (checks, score, grade), leaks, cookies, email, files, HTTP redirect, content and surface |
| `findings` | Sorted list of `{id, severity, title, evidence, recommendation}` |
| `unavailable` | Blocks that could not be completed and the reason code (e.g. `"dns": "dns_timeout"`) |

The v0.1 keys (`summary`, `site_type`, `pages`, `technologies`, `keywords`, `http`) are kept at
the top level for compatibility.

### Markdown (`--md`)

Ready to paste into a report, an issue or Obsidian. Excerpt of
`webscope example.com --md --lang en`:

```markdown
# 🔎 example.com

**URL:** https://example.com/
**Scanned:** 2026-11-03T05:29:19Z · webscope 2.0.0

## TLS

| Field | Value |
|---|---|
| Certificate | SSL Corporation (Cloudflare TLS Issuing ECC CA 3) · expires in 52 days · TLS 1.3 |
| Domains (SAN) | example.com, *.example.com |

## FINDINGS

| Severity | ID | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| MEDIUM | `HTTP-NO-REDIRECT` | http:// does not redirect to https:// | http:// -> 200 http://example.com/ | Redirect all HTTP traffic to HTTPS with a 301. |
| MEDIUM | `HDR-HSTS-MISSING` | Missing Strict-Transport-Security (HSTS) | Strict-Transport-Security: - | Add HSTS with a max-age of at least 6 months (ideally 1 year). |
| INFO | `DNS-NO-CAA` | No CAA record was observed | CAA: - | Publish CAA to limit which CAs may issue certificates. |

> Passive reconnaissance. Observations do not confirm vulnerabilities.
```

## Findings catalog

42 declarative, internationalized rules, each with a **stable id**. The full list, with
severity, what each rule observes and what it recommends, is in
[`docs/FINDINGS.md`](docs/FINDINGS.md) (in Spanish). Summary by family:

| Family | Example ids | Severities |
|---|---|---|
| TLS and HTTPS | `TLS-EXPIRED`, `TLS-CERT-INVALID`, `TLS-EXPIRING`, `TLS-OLD-PROTOCOL`, `HTTPS-MISSING`, `HTTP-NO-REDIRECT` | high / medium |
| Security headers | `HDR-HSTS-MISSING`, `HDR-CSP-MISSING`, `HDR-CSP-UNSAFE`, `HDR-XFO-MISSING`, `HDR-XCTO-MISSING`… | medium / low / info |
| Information leaks | `LEAK-SERVER-VERSION`, `LEAK-POWERED-BY`, `LEAK-ASPNET-VERSION`, `LEAK-GENERATOR`, `LEAK-HTML-COMMENT` | low / info |
| Cookies | `COOKIE-NO-SECURE`, `COOKIE-NO-HTTPONLY`, `COOKIE-NO-SAMESITE` | medium / low |
| Email | `SPF-PERMISSIVE`, `SPF-MISSING`, `SPF-NEUTRAL`, `SPF-MULTIPLE`, `DMARC-MISSING`, `DMARC-NONE`, `DKIM-NOT-FOUND` | high to info |
| Files | `SECTXT-MISSING`, `SECTXT-EXPIRED`, `ROBOTS-SENSITIVE` | low / info |
| Content and forms | `FORM-PASSWORD-HTTP`, `FORM-INSECURE-ACTION`, `CONTENT-MIXED`, `CONTENT-NO-SRI`, `FORM-EXTERNAL-ACTION`… | high to info |
| Surface and inventory | `SURFACE-ENDPOINTS`, `TECH-VERSIONS`, `DNS-NO-CAA` | info |

## Interface language

### First run

The first time you run webscope in a terminal (without `--lang` and with no saved
preference), this menu appears:

```
Select language / Elegí idioma
  1) Español
  2) English
>
```

It accepts `1`, `2`, `es` or `en`. If the answer is invalid it asks again, and after 3
attempts it falls back to Spanish. The choice is saved and later runs use it without asking.

### Priority

```
--lang  >  saved language  >  menu (interactive only)  >  system language
```

- `--lang es|en` always wins, skips the menu and **does not change** the saved language.
- `webscope --change-lang` shows the menu again and saves the new choice.
- In non-interactive mode (pipes, CI) or with `--json`/`--md` the menu **never** appears.

> The interface language is independent of the analyzed site's language: the description and
> keywords stay in the site's original language.

| System | Where the preference is stored |
|---|---|
| Linux / macOS | `~/.config/webscope/config.json` (or `$XDG_CONFIG_HOME/webscope/config.json`) |
| Windows | `%APPDATA%\webscope\config.json` |
| Any | `$WEBSCOPE_CONFIG_DIR/config.json` if that variable is set |

## How it works

```
              ┌────────────── network (only in these modules) ──────────┐
URL ─► fetcher ──► home ──┬─► crawler   (robots.txt, sitemaps, BFS)      │
                          ├─► dnsinfo   (dnspython: records, PTR, ASN)   │  in parallel
                          ├─► tlsprobe  (ssl/socket: one handshake)      │  (ThreadPoolExecutor)
                          └─► fetcher   (security.txt, http://, RDAP)    │
              └─────────────────────────────────────────────────────────┘
                                   │ raw data
                                   ▼
        analyzers/ (pure functions: no network, no language)
        topic · category · tech · keywords · site_type · infra · tls · security · findings
                                   │ stable codes + data
                                   ▼
        report.py ─► text (rich) · Markdown · JSON         i18n.py ─► es / en
```

Design decisions:

- **Isolated network**: only `fetcher`, `crawler`, `dnsinfo` and `tlsprobe` touch the network.
  Analyzers are pure functions that receive already-fetched headers, HTML or records, so they
  are tested without complicated mocks.
- **Each block fails on its own**: if DNS, TLS, the crawl or RDAP fail, the rest of the report
  still comes out and that block shows `not available (reason)`. Only a failure to download the
  home page ends the program with exit code 1.
- **"Failed" is not "missing"**: a DNS query that got no answer is shown as `?` and does not
  trigger findings such as `SPF-MISSING`.
- **Everything is declarative**: technology signatures (`analyzers/tech.py`), CDN/WAF rules
  (`analyzers/infra.py`), category dictionaries (`analyzers/category.py`) and the findings
  catalog (`analyzers/findings.py`). Extending any of them means adding one entry.
- **Analyzers return codes**, never text. `report.py` is the only place that translates, which
  is why text, Markdown and JSON show exactly the same information.
- A full analysis takes about 5–13 s on real sites (target: under 15 s).

## Third-party services

webscope only uses the services it strictly needs, none of them requiring API keys:

| Service | When | What is sent |
|---|---|---|
| **System DNS resolver** | Always (except `--brief`) | The target domain's names to query |
| **Team Cymru** (`origin.asn.cymru.com`, `origin6.asn.cymru.com`, `asn.cymru.com`) | Always (except `--brief`) | The target's IPs, as a DNS TXT query, to find their ASN |
| **rdap.org** | Only with `--rdap` (opt-in) | The registrable domain, over HTTPS, to get registration data |

`rdap.org` is opt-in precisely because it sends the domain to a third party over HTTP. No other
data leaves your machine.

## Limitations

What passive reconnaissance can and cannot know:

- **The backend is only detected when it leaves clues** (headers like `X-Powered-By`, cookies
  like `laravel_session`, tokens like `csrfmiddlewaretoken`). Many sites hide them on purpose.
- **The category is heuristic**: dictionaries of signals, not a language model. With little
  evidence, or tied evidence, it stays "undetermined". A site can show traits of several
  categories (a SaaS with a blog, for example).
- **A WAF/CDN can hide the origin**: IPs, ASN and reverse DNS are usually the CDN's
  (Cloudflare, Fastly, Akamai…), not the real server's. webscope does not try to uncover the
  origin.
- **DKIM is only looked up on common selectors** (`default`, `google`, `selector1`, `k1`…). Not
  finding it does not mean the domain does not sign its mail.
- **The page count is approximate**: with a sitemap it counts the declared URLs; without one,
  only pages reachable through links from the home page, up to `--max-pages`.
- **It does not run JavaScript**: in a pure SPA the real content may not be in the HTML.
- **The registrable domain is approximate** (`example.com.ar`, `example.co.uk`…): the Public
  Suffix List is not used, to avoid another dependency.
- DNS results depend on the resolver: some home routers do not return large TXT answers. In
  that case `?` is shown.
- Findings are observations to verify, not confirmed vulnerabilities.
- `click`'s own messages (`No such option`, `Usage:`) stay in English.

## Project structure

```
webscope/
├── pyproject.toml              # packaging (hatchling), dependencies, ruff and pytest
├── CHANGELOG.md
├── docs/FINDINGS.md            # findings rule catalog
├── .github/workflows/ci.yml    # ruff + pytest on Python 3.10–3.13
├── src/webscope/
│   ├── cli.py                  # typer: flags, language menu, errors, exit codes
│   ├── core.py                 # runs network + analyzers in parallel
│   ├── fetcher.py              # [network] requests: home, redirects, auxiliary resources
│   ├── crawler.py              # [network] robots.txt, sitemaps and BFS crawl
│   ├── dnsinfo.py              # [network] dnspython: records, PTR, ASN (Team Cymru)
│   ├── tlsprobe.py             # [network] ssl/socket: one standard TLS handshake
│   ├── report.py               # text (rich), Markdown and JSON; turns codes into text
│   ├── i18n.py                 # es/en strings and t()
│   ├── models.py               # immutable dataclasses
│   ├── config.py · parsing.py
│   └── analyzers/              # pure functions, no network
│       ├── topic.py · category.py · keywords.py · site_type.py · tech.py
│       ├── infra.py · tls.py · security.py · findings.py
│       └── _text.py
└── tests/
    ├── fixtures/               # WordPress, WooCommerce, React SPA, static, minimal,
    │                           # login, JSON-LD (SaaS, blog), good and bad headers
    └── test_*.py
```

## Tests and quality

```bash
pytest            # 359 tests, no real requests
ruff check .      # lint
ruff format .     # formatting
```

- **No real network**: `requests` is mocked with [`responses`](https://github.com/getsentry/responses),
  `dnspython` with a fake resolver and `tlsprobe` with simulated handshakes. On top of that, a
  fixture blocks any real `connect`, `sendto` or `create_connection`.
- **Your configuration is never touched**: each test uses a temporary folder through
  `WEBSCOPE_CONFIG_DIR`.
- They cover each analyzer with fixtures (good and bad headers, WordPress/WooCommerce, React
  SPA, static site, minimal page, login, JSON-LD of several types, valid and invalid SPF/DMARC,
  a certificate about to expire), the findings catalog (stable ids and severities, text in
  every language, cautious wording), the category (e-commerce, blog, SaaS, undetermined), the
  JSON (English keys identical in both languages, `schema_version`), the Markdown, **partial
  failures** (DNS down, TLS down or a broken crawler → the report still comes out) and es/en
  key parity.

## Roadmap

- [ ] **More rules** for findings and more technology and CDN signatures.
- [ ] **Plugins**: load signatures, categories and rules from external files.
- [ ] **SARIF export** to integrate with GitHub Code Scanning and other tools.
- [ ] **Compare two scans** (`webscope diff a.json b.json`) to see what changed.
- [ ] **More languages**: a new dictionary in [`i18n.py`](src/webscope/i18n.py) with the same
      keys; the parity test flags any missing key.
- [ ] **Publish to PyPI** so it can be installed with `pip install webscope`.

## License

[MIT](LICENSE) © 2026 Alvaro Aramayo Chain
