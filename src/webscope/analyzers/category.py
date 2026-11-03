"""Categoría del sitio (e-commerce, blog, SaaS...) por señales ponderadas declarativas.

Cada categoría suma puntos por tipos de schema.org, ``og:type``, TLD, tecnologías,
rutas de los links y palabras clave en español e inglés. Si el ganador no supera
``MIN_SCORE`` o no se despega del segundo, la categoría queda ``unknown``: es
preferible decir "indeterminada" a inventar.

Ampliar una categoría = sumar entradas a los diccionarios de abajo.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from webscope.models import CategoryResult, CategorySignal, Confidence

UNKNOWN: Final = "unknown"
MIN_SCORE: Final = 5
_MAX_KEYWORD_HITS = 3

CATEGORIES: Final = (
    "ecommerce",
    "blog_media",
    "saas",
    "portfolio",
    "corporate",
    "government",
    "education",
    "health",
    "finance",
    "restaurant_travel",
    "community",
    "docs",
    "landing",
)

# Tipos de schema.org (JSON-LD o microdata) -> (categoría, peso).
SCHEMA_TYPES: Final[Mapping[str, tuple[str, int]]] = {
    "product": ("ecommerce", 5),
    "offer": ("ecommerce", 3),
    "aggregateoffer": ("ecommerce", 3),
    "store": ("ecommerce", 5),
    "onlinestore": ("ecommerce", 6),
    "article": ("blog_media", 3),
    "blogposting": ("blog_media", 5),
    "blog": ("blog_media", 5),
    "newsarticle": ("blog_media", 5),
    "newsmediaorganization": ("blog_media", 6),
    "softwareapplication": ("saas", 5),
    "webapplication": ("saas", 5),
    "mobileapplication": ("saas", 3),
    "person": ("portfolio", 3),
    "profilepage": ("portfolio", 5),
    "organization": ("corporate", 2),
    "corporation": ("corporate", 4),
    "professionalservice": ("corporate", 4),
    "localbusiness": ("corporate", 2),
    "governmentorganization": ("government", 7),
    "governmentoffice": ("government", 7),
    "educationalorganization": ("education", 6),
    "collegeoruniversity": ("education", 7),
    "school": ("education", 6),
    "course": ("education", 4),
    "medicalorganization": ("health", 6),
    "hospital": ("health", 7),
    "physician": ("health", 6),
    "dentist": ("health", 6),
    "medicalclinic": ("health", 7),
    "pharmacy": ("health", 5),
    "financialservice": ("finance", 6),
    "bankorcreditunion": ("finance", 7),
    "insuranceagency": ("finance", 5),
    "restaurant": ("restaurant_travel", 7),
    "foodestablishment": ("restaurant_travel", 6),
    "cafeorcoffeeshop": ("restaurant_travel", 6),
    "hotel": ("restaurant_travel", 7),
    "lodgingbusiness": ("restaurant_travel", 6),
    "touristattraction": ("restaurant_travel", 5),
    "travelagency": ("restaurant_travel", 6),
    "discussionforumposting": ("community", 6),
    "techarticle": ("docs", 5),
    "apireference": ("docs", 6),
}

OG_TYPES: Final[Mapping[str, tuple[str, int]]] = {
    "product": ("ecommerce", 4),
    "og:product": ("ecommerce", 4),
    "product.item": ("ecommerce", 4),
    "article": ("blog_media", 2),
    "blog": ("blog_media", 3),
    "profile": ("portfolio", 3),
    "restaurant.restaurant": ("restaurant_travel", 5),
}

# Sufijos de dominio -> (categoría, peso).
TLD_HINTS: Final[tuple[tuple[str, str, int], ...]] = (
    (r"\.(?:gov|gob|gub|mil)(?:\.[a-z]{2})?$", "government", 8),
    (r"\.gov\.[a-z]{2}$|\.gouv\.fr$|\.gc\.ca$", "government", 8),
    (r"\.(?:edu)(?:\.[a-z]{2})?$|\.ac\.[a-z]{2}$", "education", 8),
    (r"\.bank$", "finance", 6),
    (r"\.shop$|\.store$", "ecommerce", 3),
    (r"\.dev$|\.io$", "saas", 1),
)

# Tecnologías detectadas -> (categoría, peso).
TECH_HINTS: Final[Mapping[str, tuple[str, int]]] = {
    "WooCommerce": ("ecommerce", 6),
    "Shopify": ("ecommerce", 6),
    "Magento": ("ecommerce", 6),
    "PrestaShop": ("ecommerce", 6),
    "Ghost": ("blog_media", 3),
    "Jekyll": ("blog_media", 1),
    "Docusaurus": ("docs", 5),
    "Stripe": ("saas", 2),
}

# Rutas en los links internos -> (categoría, peso). Se cuenta una vez por regla.
PATH_HINTS: Final[tuple[tuple[str, str, int], ...]] = (
    (r"/(?:cart|carrito|checkout|basket|cesta)(?:/|$|\?)", "ecommerce", 4),
    (r"/(?:product|products|producto|productos|shop|tienda|store|collections)(?:/|$)", "ecommerce", 2),
    (r"/(?:blog|news|noticias|novedades|articulos|articles|posts?)(?:/|$)", "blog_media", 2),
    (r"/(?:pricing|precios|planes|plans)(?:/|$)", "saas", 3),
    (r"/(?:signup|sign-up|register|registro|login|signin|app)(?:/|$)", "saas", 1),
    (r"/(?:docs|documentation|documentacion|reference|api-reference|guides?)(?:/|$)", "docs", 3),
    (r"/(?:forum|foro|community|comunidad|threads?|topics?)(?:/|$)", "community", 3),
    (r"/(?:portfolio|portafolio|projects|proyectos|cv|resume)(?:/|$)", "portfolio", 3),
    (r"/(?:servicios|services|clientes|clients|empresa|company|about|nosotros)(?:/|$)", "corporate", 1),
    (r"/(?:menu|carta|reservas|reservations|booking|habitaciones|rooms)(?:/|$)", "restaurant_travel", 3),
    (r"/(?:cursos|courses|carreras|admisiones|admissions|campus)(?:/|$)", "education", 3),
    (r"/(?:tramites|tr%C3%A1mites|servicios-al-ciudadano|transparencia)(?:/|$)", "government", 4),
)  # fmt: skip

# Palabras o frases clave (minúsculas) -> peso, por categoría. Español e inglés.
KEYWORDS: Final[Mapping[str, Mapping[str, int]]] = {
    "ecommerce": {
        "carrito": 3, "add to cart": 4, "agregar al carrito": 4, "añadir al carrito": 4,
        "checkout": 3, "comprar": 2, "buy now": 3, "tienda online": 4, "online store": 4,
        "tienda": 1, "shop": 1, "envío gratis": 3, "free shipping": 3, "envíos": 2,
        "shipping": 1, "ofertas": 1, "descuento": 1, "discount": 1, "cuotas sin interés": 3,
        "precio": 1, "price": 1, "productos": 1, "products": 1, "catálogo": 1,
    },
    "blog_media": {
        "blog": 2, "artículo": 1, "artículos": 2, "articles": 2, "noticias": 2, "news": 2,
        "posts": 1, "leer más": 2, "read more": 2, "publicado": 1, "published": 1,
        "autor": 1, "author": 1, "newsletter": 1, "periodismo": 3, "journalism": 3,
        "últimas noticias": 3, "latest news": 3, "podcast": 1, "editorial": 1,
    },
    "saas": {
        "software": 2, "plataforma": 2, "platform": 2, "free trial": 4, "prueba gratis": 4,
        "start for free": 4, "empezá gratis": 4, "comenzar gratis": 4, "pricing": 3,
        "precios": 1, "planes": 1, "sign up": 2, "registrate": 2, "dashboard": 2, "api": 1,
        "integraciones": 1, "integrations": 1, "workflow": 2, "teams": 1, "equipos": 1,
        "automatización": 2, "automation": 2, "cloud": 1, "saas": 4, "request a demo": 3,
        "solicitar demo": 3, "app": 1,
    },
    "portfolio": {
        "portfolio": 4, "portafolio": 4, "mis proyectos": 4, "my projects": 4, "proyectos": 1,
        "projects": 1, "sobre mí": 4, "about me": 4, "curriculum": 3, "resume": 2, "cv": 2,
        "freelance": 3, "desarrollador": 2, "developer": 2, "diseñador": 2, "designer": 2,
        "hola, soy": 4, "hi, i'm": 4, "i'm a": 2, "soy un": 2, "soy una": 2, "github": 1,
        "full stack": 4, "fullstack": 4, "full-stack": 4, "web developer": 3,
        "desarrollador web": 3, "frontend developer": 3, "backend developer": 3,
        "based in": 2, "radicado en": 2, "hire me": 4, "contratame": 4, "contrátame": 4,
        "my work": 2, "mi trabajo": 2, "selected work": 3, "case studies": 2, "skills": 2,
        "habilidades": 2, "tech stack": 2, "linkedin": 1,
    },
    "corporate": {
        "servicios": 2, "services": 2, "empresa": 2, "company": 2, "clientes": 2,
        "clients": 2, "soluciones": 2, "solutions": 2, "consultoría": 3, "consulting": 3,
        "quiénes somos": 2, "about us": 2, "nuestro equipo": 2, "our team": 2,
        "contactanos": 1, "contact us": 1, "industria": 1, "industry": 1, "b2b": 2,
    },
    "government": {
        "gobierno": 4, "government": 4, "ministerio": 4, "ministry": 3, "municipalidad": 4,
        "municipio": 3, "trámites": 4, "ciudadanos": 2, "citizens": 2, "secretaría": 2,
        "boletín oficial": 4, "official website": 2, "sitio oficial": 2, "transparencia": 2,
    },
    "education": {
        "universidad": 4, "university": 4, "facultad": 3, "escuela": 3, "school": 2,
        "colegio": 3, "cursos": 3, "courses": 3, "estudiantes": 3, "students": 3,
        "alumnos": 3, "carreras": 3, "inscripciones": 3, "admissions": 3, "campus": 2,
        "aprendé": 2, "learn": 1, "clases": 2, "docentes": 2, "teachers": 2, "e-learning": 3,
    },
    "health": {
        "salud": 3, "health": 2, "clínica": 4, "clinic": 4, "hospital": 4, "médico": 3,
        "médicos": 3, "doctor": 2, "pacientes": 3, "patients": 3, "turnos": 2,
        "appointment": 2, "odontología": 4, "dental": 3, "farmacia": 4, "pharmacy": 4,
        "especialidades": 2, "tratamiento": 2, "treatment": 2,
    },
    "finance": {
        "banco": 4, "bank": 3, "banking": 4, "préstamos": 3, "loans": 3, "tarjeta de crédito": 3,
        "credit card": 3, "inversiones": 3, "investments": 3, "seguros": 3, "insurance": 3,
        "homebanking": 4, "cuenta": 1, "account": 1, "finanzas": 2, "finance": 2,
        "crypto": 2, "trading": 3, "billetera": 2, "wallet": 2, "tasa": 1,
    },
    "restaurant_travel": {
        "restaurante": 4, "restaurant": 4, "menú": 2, "carta": 2, "reservas": 3,
        "reservations": 3, "delivery": 2, "hotel": 4, "habitaciones": 3, "rooms": 2,
        "viajes": 3, "travel": 3, "turismo": 4, "tourism": 4, "vuelos": 3, "flights": 3,
        "excursiones": 3, "tours": 2, "hospedaje": 3, "cafetería": 3, "brunch": 2,
    },
    "community": {
        "foro": 4, "forum": 4, "comunidad": 3, "community": 3, "miembros": 2, "members": 2,
        "discusiones": 3, "discussions": 3, "threads": 3, "temas": 1, "topics": 2,
        "respuestas": 2, "replies": 2, "preguntas": 1, "questions": 1, "upvote": 3,
    },
    "docs": {
        "documentación": 4, "documentation": 4, "docs": 3, "api reference": 4,
        "referencia": 2, "guía": 2, "guide": 2, "getting started": 4, "primeros pasos": 4,
        "installation": 3, "instalación": 3, "tutorial": 2, "sdk": 3, "changelog": 2,
        "npm install": 4, "pip install": 4, "configuration": 2, "configuración": 1,
    },
    "landing": {
        "lista de espera": 4, "waitlist": 4, "join the waitlist": 5, "early access": 4,
        "acceso anticipado": 4, "coming soon": 4, "próximamente": 4, "pre-order": 3,
        "preventa": 3, "descargá la app": 3, "download the app": 3, "get started": 1,
    },
}  # fmt: skip


@dataclass(frozen=True)
class CategoryInput:
    """Datos ya extraídos que usa la clasificación (sin HTML ni red)."""

    schema_types: Sequence[str] = ()
    og_type: str = ""
    host: str = ""
    technologies: Sequence[str] = ()
    links: Sequence[str] = ()
    strong_text: str = ""
    body_text: str = ""
    extra: Sequence[CategorySignal] = field(default_factory=tuple)


def _keyword_hits(text: str, phrase: str) -> int:
    pattern = r"(?<![\w])" + re.escape(phrase) + r"(?![\w])"
    return len(re.findall(pattern, text))


def _schema_signals(data: CategoryInput) -> Iterable[CategorySignal]:
    for raw in dict.fromkeys(t.lower() for t in data.schema_types):
        if raw in SCHEMA_TYPES:
            category, weight = SCHEMA_TYPES[raw]
            yield CategorySignal(category, f"schema:{raw}", weight)
    og = data.og_type.strip().lower()
    if og in OG_TYPES:
        category, weight = OG_TYPES[og]
        yield CategorySignal(category, f"og:{og}", weight)


def _context_signals(data: CategoryInput) -> Iterable[CategorySignal]:
    host = data.host.lower()
    for pattern, category, weight in TLD_HINTS:
        tld = re.search(pattern, host) if host else None
        if tld:
            yield CategorySignal(category, f"tld:{tld.group(0)}", weight)
    for tech in data.technologies:
        if tech in TECH_HINTS:
            category, weight = TECH_HINTS[tech]
            yield CategorySignal(category, f"tech:{tech}", weight)
    for pattern, category, weight in PATH_HINTS:
        for link in data.links:
            path = re.search(pattern, link, re.I)
            if path:
                yield CategorySignal(category, f"path:{path.group(0)}", weight)
                break


def _keyword_signals(data: CategoryInput) -> Iterable[CategorySignal]:
    strong = data.strong_text.lower()
    body = data.body_text.lower()
    for category, phrases in KEYWORDS.items():
        for phrase, weight in phrases.items():
            hits = min(_MAX_KEYWORD_HITS, _keyword_hits(body, phrase))
            strong_hits = min(2, _keyword_hits(strong, phrase))
            score = weight * strong_hits * 2 + (weight if hits else 0) + (hits > 2)
            if score:
                yield CategorySignal(category, f"kw:{phrase}", score)


def confidence_for(top: int, margin: int) -> Confidence:
    """Confianza según el puntaje ganador y la diferencia con el segundo."""
    if top >= 18 and margin >= 8:
        return "high"
    if top >= 10 and margin >= 4:
        return "medium"
    return "low"


def classify_category(data: CategoryInput) -> CategoryResult:
    """Categoría ganadora; ``unknown`` si el puntaje es bajo o hay empate cercano."""
    signals = (
        *_schema_signals(data),
        *_context_signals(data),
        *_keyword_signals(data),
        *data.extra,
    )
    scores: dict[str, int] = defaultdict(int)
    for signal in signals:
        scores[signal.category] += signal.weight
    ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    if not ranked:
        return CategoryResult(UNKNOWN, "low")
    best, top = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else 0
    used = tuple(sorted((s for s in signals if s.category == best), key=lambda s: -s.weight))
    if top < MIN_SCORE or top - second < 2:
        return CategoryResult(UNKNOWN, "low", top, used)
    return CategoryResult(best, confidence_for(top, top - second), top, used)
