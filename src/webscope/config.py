"""Preferencia de idioma guardada en un JSON por usuario.

Ubicación:
- ``$WEBSCOPE_CONFIG_DIR/config.json`` si la variable existe (la usan los tests).
- ``%APPDATA%\\webscope\\config.json`` en Windows.
- ``$XDG_CONFIG_HOME/webscope/config.json`` o ``~/.config/webscope/config.json`` en Linux/macOS.

Cualquier problema de lectura o escritura se ignora en silencio: el programa sigue
funcionando y simplemente no recuerda la preferencia.
"""

from __future__ import annotations

import json
import locale
import os
from pathlib import Path

from webscope.i18n import DEFAULT_LANG, normalize_lang

CONFIG_FILENAME = "config.json"
ENV_CONFIG_DIR = "WEBSCOPE_CONFIG_DIR"
_LOCALE_ENV_VARS = ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE")


def config_dir() -> Path:
    """Carpeta donde se guarda la configuración según el sistema operativo."""
    override = os.environ.get(ENV_CONFIG_DIR)
    if override:
        return Path(override)
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "webscope"
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "webscope"


def config_path() -> Path:
    """Ruta completa del archivo de configuración."""
    return config_dir() / CONFIG_FILENAME


def _read_config() -> dict[str, object]:
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def load_language() -> str | None:
    """Idioma guardado, o ``None`` si no hay uno válido."""
    value = _read_config().get("lang")
    return normalize_lang(value) if isinstance(value, str) else None


def save_language(lang: str) -> bool:
    """Guarda el idioma; devuelve ``False`` si no se pudo escribir (sin lanzar)."""
    data = _read_config()
    data["lang"] = lang
    try:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        return False
    return True


def system_language() -> str:
    """Idioma del sistema: ``es`` si la configuración regional empieza con ``es``."""
    candidates = [os.environ.get(name, "") for name in _LOCALE_ENV_VARS]
    try:
        candidates.append(locale.getlocale()[0] or "")
    except ValueError:
        pass
    for value in candidates:
        if not value or value in ("C", "POSIX"):
            continue
        # Windows a veces devuelve nombres largos como "Spanish_Argentina".
        if value.lower().startswith("spanish"):
            return "es"
        return "es" if normalize_lang(value) == "es" else DEFAULT_LANG
    return DEFAULT_LANG
