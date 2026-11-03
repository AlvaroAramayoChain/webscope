"""Tokenización y stopwords español/inglés incluidas en el código (sin descargas)."""

from __future__ import annotations

import re
from typing import Final

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)
MIN_WORD_LEN: Final = 3

STOPWORDS_ES: Final = frozenset(
    """
    a al algo algun alguna algunas alguno algunos ante antes aqui asi aun aunque bajo
    bien cada casi como con contra cual cuales cuando cuanto de del desde donde dos el
    ella ellas ello ellos en entre era eran eres es esa esas ese eso esos esta estaba
    estado estamos estan estar estas este esto estos estoy fue fueron fui ha hace hacen
    hacer hacia han hasta hay la las le les lo los mas me mi mis mismo mucho muchos muy
    nada ni no nos nosotros nuestra nuestras nuestro nuestros o otra otras otro otros
    para pero poco por porque puede pueden que quien quienes se sea sean segun ser si
    sido siempre sin sobre solo son su sus tambien tan tanto te tener tenemos tiene
    tienen todo todos toda todas tu tus un una unas uno unos usted ustedes ver vez y ya
    más está están también aquí así aún según sólo qué cómo dónde cuándo él ésta éste
    ahora año años cosa cosas día días hoy mejor nuevo nueva nuevos nuevas parte tipo
    través vía cualquier mientras menos dentro fuera luego después sí podemos puedes
    haz conoce descubre leer ver más inicio menú buscar búsqueda cerrar abrir siguiente
    anterior contacto aviso legal política privacidad derechos reservados términos
    condiciones aceptar configuración ir saltar contenido principal página páginas
    """.split()
)

STOPWORDS_EN: Final = frozenset(
    """
    a about above after again against all also am an and any are as at be because been
    before being below between both but by can cannot could did do does doing down
    during each even ever every few for from further get gets got had has have having he
    her here hers herself him himself his how however i if in into is it its itself
    just let like made make many may me might more most much must my myself new no nor
    not now of off on once one only or other our ours ourselves out over own per same
    she should since so some such than that the their theirs them themselves then there
    these they this those through to too under until up upon us use used using very
    via was we well were what when where which while who whom why will with within
    without would yet you your yours yourself yourselves its it's don't can't won't
    able across already always another anything around away back best better come
    each easy first go going good great help here know last learn less look lot more
    need next part read really right see seem something still take thing things think
    want way ways year years home menu search close open skip content main page pages
    privacy policy cookie cookies terms conditions rights reserved copyright accept
    settings login sign log click view all toggle navigation subscribe follow share
    com org net www http https html
    """.split()
)


def tokenize(text: str) -> list[str]:
    """Palabras en minúsculas (solo letras, con acentos) de al menos 3 letras."""
    return [word for word in _WORD_RE.findall(text.lower()) if len(word) >= MIN_WORD_LEN]


def stopwords_for(lang: str) -> frozenset[str]:
    """Stopwords a filtrar según el idioma detectado de la web.

    En español también se filtran las inglesas (menús en inglés son comunes), pero
    en inglés no se usan las españolas: algunas son palabras inglesas válidas
    (``son``, ``sin``, ``era``...).
    """
    if lang == "en":
        return STOPWORDS_EN
    return STOPWORDS_ES | STOPWORDS_EN


def count_stopwords(words: list[str]) -> tuple[int, int]:
    """Cantidad de stopwords ``(español, inglés)`` presentes en ``words``."""
    es = sum(1 for word in words if word in STOPWORDS_ES and word not in STOPWORDS_EN)
    en = sum(1 for word in words if word in STOPWORDS_EN and word not in STOPWORDS_ES)
    return es, en
