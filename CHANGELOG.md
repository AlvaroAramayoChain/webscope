# Changelog

Todos los cambios relevantes de este proyecto se documentan en este archivo.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el proyecto
usa [Versionado Semántico](https://semver.org/lang/es/).

## [2.0.0] - 2026-11-03

De "resumen de una web" a **herramienta de reconocimiento pasivo** para analistas de
ciberseguridad. La CLI de la v0.1 sigue funcionando igual: mismos flags, mismos exit codes
y las mismas claves de JSON de nivel superior.

### Agregado

- **Bloques nuevos en el reporte**: `INFRAESTRUCTURA`, `TLS`, `SEGURIDAD VISIBLE` y
  `HALLAZGOS`, además de `GENERAL`.
- **De qué trata concreto** (`analyzers/topic.py`, `analyzers/category.py`): combina
  JSON-LD/schema.org, Open Graph, `<title>`, `meta description`, `h1`/`h2` y `meta keywords`;
  lee hasta 5 páginas internas (nosotros, productos, contacto, blog, docs); clasifica la
  categoría (e-commerce, blog/medios, SaaS, portfolio, corporativo, gobierno, educación,
  salud, finanzas, gastronomía/turismo, comunidad, documentación, landing) con confianza y
  devuelve "indeterminada" si no alcanza; limpia boilerplate ("Bienvenido a…", "Home |");
  agrega nombre del sitio y país como pista (ccTLD, schema.org o `lang`).
- **Infraestructura** (`dnsinfo.py`, `analyzers/infra.py`): IPs A/AAAA, IP de la conexión,
  reverse DNS, ASN/organización/país vía Team Cymru (DNS, sin API keys), NS, MX, TXT, CAA,
  CNAME de raíz y `www`, cadena de redirecciones y CDN/WAF/hosting inferido por headers,
  CNAME, ASN y PTR (reglas declarativas).
- **TLS** (`tlsprobe.py`, `analyzers/tls.py`): emisor, sujeto, SANs, vigencia, días para
  vencer, protocolo y cipher negociados y validación de la cadena. Un solo handshake estándar.
- **Seguridad visible** (`analyzers/security.py`): security headers con puntaje y nota A–F,
  fugas de versión (headers, meta generator, comentarios HTML), cookies (`Secure`,
  `HttpOnly`, `SameSite`, prefijos), SPF/DMARC/DKIM/MTA-STS/BIMI, `security.txt`, rutas
  sensibles en `robots.txt`, redirección HTTP→HTTPS, recursos de terceros, scripts y
  estilos sin SRI, contenido mixto, formularios, `target=_blank` sin `noopener`, subdominios
  y endpoints referenciados en el contenido.
- **Catálogo de hallazgos** (`analyzers/findings.py`): 42 reglas declarativas con id estable,
  severidad (`critical|high|medium|low|info`), evidencia y recomendación, traducidas a
  español e inglés. Documentado en [`docs/FINDINGS.md`](docs/FINDINGS.md).
- **Tecnologías con versión**: captura versiones de meta generator, query strings de assets,
  headers y CDNs. Nuevas firmas: WooCommerce, Elementor, Divi, Magento, PrestaShop, Remix,
  SvelteKit, Flask, Spring, Java, Google Analytics, Google Tag Manager, Meta Pixel, Hotjar,
  reCAPTCHA, Stripe, Cloudflare Turnstile, Fastly y Akamai. Categorías nuevas: `ecommerce`,
  `analytics`, `service` y `cdn`.
- **Flags nuevos**: `--brief`, `--md`, `--no-crawl`, `--rdap` (opt-in, consulta a
  `rdap.org`) y `--timeout`.
- **Salida Markdown** (`--md`) con encabezados y tablas, lista para pegar en un informe.
- **JSON 2.0**: `schema_version`, `scanned_at` (UTC, ISO 8601) y una sección por bloque
  (`general`, `infrastructure`, `tls`, `security`, `findings`, `unavailable`).
- Aviso de alcance ético en `--help` y aviso de "reconocimiento pasivo" al final del reporte.
- `CHANGELOG.md` y `docs/FINDINGS.md`.
- Tests sin red real para cada analizador nuevo, el catálogo, la categoría, el JSON, el
  Markdown y las fallas parciales (359 tests).

### Cambiado

- Análisis en paralelo (`ThreadPoolExecutor`): crawl, DNS, TLS, `security.txt`, sondeo HTTP
  y RDAP corren a la vez; cada bloque falla de forma independiente y muestra
  "no disponible (motivo)".
- El ancho máximo del reporte pasa de 80 a 100 columnas.
- `Cloudflare` y `Amazon CloudFront` pasan de la categoría `server` a `cdn`.
- `GitHub Pages` solo se detecta con `Server: GitHub.com` exacto (github.com responde en
  minúsculas y antes daba un falso positivo).
- La verificación TLS usa el almacén del sistema más el bundle de `certifi`.
- `site_type`: una página con poco texto y sin señales fuertes de app (contenedor SPA,
  bundles, manifest, service worker, rutas de app, aviso de `<noscript>` o formulario de
  contraseña) se clasifica como "sitio web" con confianza baja, nunca como "app web".
- Con categoría indeterminada, el resumen mantiene el formato
  `Indeterminada — <descripción>` (`Undetermined — …` en inglés).
- El README principal pasa a estar en inglés; la versión en español está en `README.es.md`.

### Dependencias

- Nuevas: `dnspython>=2.4` y `certifi` (ya llegaba como dependencia de `requests`).

## [0.1.0] - 2026-11-03

### Agregado

- Primera versión: resumen, tipo sitio/app, conteo de páginas por sitemap o rastreo,
  tecnologías por firmas, palabras clave, interfaz es/en con menú de idioma y salida JSON.

[2.0.0]: https://github.com/AlvaroAramayoChain/webscope/compare/7a8a114...v2.0.0
[0.1.0]: https://github.com/AlvaroAramayoChain/webscope/tree/7a8a114
