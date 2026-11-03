# Catálogo de hallazgos

Reglas que webscope evalúa sobre los datos que ya obtuvo de forma pasiva. Cada hallazgo
tiene un **id estable** (no cambia entre versiones ni idiomas), una **severidad** y una
recomendación corta. El catálogo vive en
[`src/webscope/analyzers/findings.py`](../src/webscope/analyzers/findings.py) y los textos
en [`src/webscope/i18n.py`](../src/webscope/i18n.py) (`finding.<id>.title` / `.rec`).

> Son **observaciones**, no un escáner de vulnerabilidades. Que una regla aplique no
> confirma que el sitio sea explotable: es un punto para revisar manualmente.

## Severidades

| Severidad | Criterio |
|---|---|
| `critical` | Reservada para observaciones de impacto inmediato. Ninguna regla pasiva actual la usa. |
| `high` | Exposición directa de datos o confianza rota: certificado vencido o inválido, sin HTTPS, contraseñas por HTTP, SPF `+all`. |
| `medium` | Falta una defensa estándar importante: HSTS, CSP, redirección a HTTPS, DMARC, cookies sin `Secure`. |
| `low` | Endurecimiento recomendado o fuga de información menor. |
| `info` | Dato útil para el analista; no es un problema en sí. |

Los hallazgos se ordenan por severidad y, dentro de cada severidad, por el orden del catálogo.

## TLS y HTTPS

| ID | Severidad | Qué observa | Recomendación |
|---|---|---|---|
| `TLS-EXPIRED` | alta | El certificado TLS está vencido (desde fecha) | Renovar el certificado y automatizar la renovación (p. ej. ACME). |
| `TLS-CERT-INVALID` | alta | El certificado TLS no valida contra las CAs de confianza | Revisar la cadena, el nombre (SAN) y la CA emisora. |
| `HTTPS-MISSING` | alta | El sitio se sirve sin HTTPS | Servir todo por HTTPS y redirigir HTTP con 301. |
| `TLS-EXPIRING` | media | El certificado TLS vence en N días | Renovar antes del vencimiento y verificar la renovación automática. |
| `TLS-OLD-PROTOCOL` | media | Se negoció un protocolo TLS antiguo (protocolo) | Habilitar TLS 1.2 o superior y deshabilitar TLS 1.0/1.1. |
| `HTTP-NO-REDIRECT` | media | http:// no redirige a https:// | Redirigir todo el tráfico HTTP a HTTPS con 301. |

## Security headers

| ID | Severidad | Qué observa | Recomendación |
|---|---|---|---|
| `HDR-HSTS-MISSING` | media | Falta Strict-Transport-Security (HSTS) | Agregar HSTS con max-age de al menos 6 meses (idealmente 1 año). |
| `HDR-CSP-MISSING` | media | Falta Content-Security-Policy | Definir una CSP restrictiva (se puede empezar en modo Report-Only). |
| `HDR-HSTS-WEAK` | baja | HSTS con max-age corto (menos de 6 meses) | Subir max-age a 15552000 o más. |
| `HDR-CSP-UNSAFE` | baja | La CSP permite fuentes riesgosas (problemas) | Reemplazar unsafe-inline/unsafe-eval y comodines por nonces, hashes u orígenes concretos. |
| `HDR-XFO-MISSING` | baja | Sin protección contra framing (X-Frame-Options / frame-ancestors) | Agregar frame-ancestors a la CSP o X-Frame-Options: DENY/SAMEORIGIN. |
| `HDR-XCTO-MISSING` | baja | Falta X-Content-Type-Options: nosniff | Agregar X-Content-Type-Options: nosniff. |
| `HDR-REFERRER-MISSING` | info | Falta Referrer-Policy | Agregar Referrer-Policy: strict-origin-when-cross-origin. |
| `HDR-PERMISSIONS-MISSING` | info | Falta Permissions-Policy | Declarar qué APIs del navegador (cámara, geolocalización...) puede usar el sitio. |

## Fugas de información

| ID | Severidad | Qué observa | Recomendación |
|---|---|---|---|
| `LEAK-SERVER-VERSION` | baja | El header Server expone la versión (valor) | Ocultar la versión del servidor (p. ej. server_tokens off en nginx). |
| `LEAK-POWERED-BY` | baja | X-Powered-By expone la tecnología (valor) | Quitar el header X-Powered-By. |
| `LEAK-ASPNET-VERSION` | baja | Headers de ASP.NET exponen la versión (valor) | Deshabilitar X-AspNet-Version y X-AspNetMvc-Version. |
| `LEAK-GENERATOR` | info | El generador del sitio es visible (valor) | Considerar ocultar meta generator / X-Generator. |
| `LEAK-HTML-COMMENT` | info | Comentarios HTML mencionan software o versiones (N) | Quitar en producción los comentarios que revelan versiones. |

## Cookies

| ID | Severidad | Qué observa | Recomendación |
|---|---|---|---|
| `COOKIE-NO-SECURE` | media | N cookie(s) sin el atributo Secure | Marcar las cookies con Secure en sitios HTTPS. |
| `COOKIE-NO-HTTPONLY` | baja | N cookie(s) sin HttpOnly | Usar HttpOnly en las cookies que JavaScript no necesita leer (sobre todo las de sesión). |
| `COOKIE-NO-SAMESITE` | baja | N cookie(s) sin SameSite explícito | Definir SameSite=Lax o Strict. |

## Correo (SPF, DMARC, DKIM)

| ID | Severidad | Qué observa | Recomendación |
|---|---|---|---|
| `SPF-PERMISSIVE` | alta | SPF con +all: cualquier servidor podría enviar correo por el dominio | Terminar el registro SPF con -all o ~all. |
| `DMARC-MISSING` | media | No se observó un registro DMARC | Publicar _dmarc con p=none para monitorear y luego pasar a quarantine/reject. |
| `SPF-MISSING` | baja | No se observó un registro SPF | Publicar SPF; si el dominio no envía correo, usar "v=spf1 -all". |
| `SPF-NEUTRAL` | baja | SPF con ?all (neutral): no indica qué hacer con correo no autorizado | Usar ~all o -all. |
| `SPF-MULTIPLE` | baja | Hay N registros SPF (esto puede invalidar SPF) | Unificarlos en un solo registro v=spf1. |
| `DMARC-NONE` | baja | DMARC en modo monitoreo (p=none) | Cuando los reportes estén limpios, pasar a p=quarantine o p=reject. |
| `DKIM-NOT-FOUND` | info | No se encontró DKIM en selectores comunes (puede usar otros) | Verificar que el correo saliente esté firmado con DKIM. |

## Archivos y políticas

| ID | Severidad | Qué observa | Recomendación |
|---|---|---|---|
| `SECTXT-EXPIRED` | baja | security.txt vencido | Actualizar el campo Expires. |
| `SECTXT-MISSING` | info | No se observó /.well-known/security.txt | Publicar un security.txt (RFC 9116) con un contacto para reportes. |
| `ROBOTS-SENSITIVE` | info | robots.txt menciona N ruta(s) que suenan sensibles | robots.txt es público: no usarlo para ocultar rutas; protegerlas con autenticación. |

## Contenido y formularios

| ID | Severidad | Qué observa | Recomendación |
|---|---|---|---|
| `FORM-PASSWORD-HTTP` | alta | Formulario con contraseña en una página sin HTTPS (N) | Servir los formularios de login solo por HTTPS. |
| `FORM-INSECURE-ACTION` | alta | N formulario(s) envían datos a una URL http:// | Usar URLs https:// en el atributo action. |
| `CONTENT-MIXED` | media | Posible contenido mixto: N recurso(s) http:// en una página HTTPS | Cargar todos los recursos por HTTPS. |
| `CONTENT-NO-SRI` | info | N recurso(s) externo(s) sin SRI (dominios) | Agregar integrity y crossorigin a scripts y estilos de CDNs. |
| `FORM-EXTERNAL-ACTION` | info | N formulario(s) envían datos a otro dominio | Confirmar que el destino sea un proveedor esperado. |
| `FORM-PASSWORD-AUTOCOMPLETE` | info | N campo(s) de contraseña sin autocomplete explícito | Usar autocomplete="current-password" o "new-password". |
| `LINK-NO-NOOPENER` | info | N link(s) target=_blank sin rel=noopener (informativo) | Agregar rel="noopener noreferrer" (los navegadores modernos ya lo aplican). |

## Superficie, inventario y DNS

| ID | Severidad | Qué observa | Recomendación |
|---|---|---|---|
| `SURFACE-ENDPOINTS` | info | N endpoint(s) sensibles referenciados en el contenido | Revisar que estén protegidos (webscope no los sondea). |
| `TECH-VERSIONS` | info | N tecnología(s) con versión visible | Cruzar las versiones con avisos de seguridad y mantenerlas actualizadas. |
| `DNS-NO-CAA` | info | No se observó un registro CAA | Publicar CAA para limitar qué CAs pueden emitir certificados. |

## Criterio del puntaje de headers

| Header | Puntos |
|---|---|
| `Strict-Transport-Security` | 2 si `max-age` ≥ 15552000 (6 meses), 1 si es menor. Solo cuenta en HTTPS. |
| `Content-Security-Policy` | 2 sin `unsafe-inline`/`unsafe-eval`/comodines, 1 si los usa (`unsafe-inline` con nonce o hash no penaliza). |
| `X-Frame-Options` o `frame-ancestors` | 1 |
| `X-Content-Type-Options: nosniff` | 1 |
| `Referrer-Policy` | 1 |
| `Permissions-Policy` | 1 |

Nota: **A** = 7–8, **B** = 6, **C** = 4–5, **D** = 2–3, **F** = 0–1. `Cross-Origin-Opener-Policy`,
`Cross-Origin-Resource-Policy` y `Cross-Origin-Embedder-Policy` se informan con `--verbose`
pero no suman puntos.

## Agregar una regla

1. Escribir una función pura `check(ctx: FindingContext) -> (evidencia, parámetros) | None` en `findings.py`.
2. Sumar `Rule("MI-ID", "low", check)` a `RULES`.
3. Agregar `finding.MI-ID.title` y `finding.MI-ID.rec` en **todos** los idiomas de `i18n.py`.
4. Sumar el id y su severidad a `EXPECTED` en `tests/test_findings.py` (el test falla si falta).
5. Documentarla en este archivo.
