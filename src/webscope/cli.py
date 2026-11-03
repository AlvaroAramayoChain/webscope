"""Interfaz de línea de comandos: argumentos, menú de idioma, errores y exit codes.

Exit codes: 0 ok, 1 error de red o de URL, 2 error de uso.
"""

import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Annotated

import typer
from rich.console import Console
from rich.markup import escape

from webscope import __version__
from webscope.config import load_language, save_language, system_language
from webscope.core import AnalyzeOptions, analyze
from webscope.fetcher import DEFAULT_TIMEOUT, FetchError
from webscope.i18n import MENU_FALLBACK_LANG, SUPPORTED_LANGS, language_name, normalize_lang, t
from webscope.report import MAX_WIDTH, format_error, format_event, render, to_json, to_markdown

EXIT_OK = 0
EXIT_NETWORK = 1
EXIT_USAGE = 2
MENU_ATTEMPTS = 3
DEFAULT_MAX_PAGES = 50


@dataclass(frozen=True)
class RunOptions:
    """Opciones de una ejecución ya parseadas por typer."""

    url: str | None
    max_pages: int = DEFAULT_MAX_PAGES
    json_output: bool = False
    lang: str | None = None
    verbose: bool = False
    no_color: bool = False
    change_lang: bool = False
    brief: bool = False
    markdown: bool = False
    no_crawl: bool = False
    rdap: bool = False
    timeout: float = DEFAULT_TIMEOUT

    @property
    def machine_output(self) -> bool:
        """``--json`` o ``--md``: salida para otras herramientas, sin menú ni spinner."""
        return self.json_output or self.markdown

    def analyze_options(self) -> AnalyzeOptions:
        """Opciones del análisis derivadas de los flags."""
        return AnalyzeOptions(
            max_pages=self.max_pages,
            brief=self.brief,
            crawl=not self.no_crawl,
            rdap=self.rdap,
            timeout=self.timeout,
        )


# --- Idioma -------------------------------------------------------------------------


def is_interactive() -> bool:
    """``True`` si stdin es una terminal (los tests lo reemplazan con monkeypatch)."""
    return sys.stdin is not None and sys.stdin.isatty()


def prompt_language() -> str:
    """Muestra el menú bilingüe y devuelve el idioma elegido (español tras 3 fallos)."""
    options = {str(i): code for i, code in enumerate(SUPPORTED_LANGS, start=1)}
    for _ in range(MENU_ATTEMPTS):
        typer.echo(t("menu.title", MENU_FALLBACK_LANG), err=True)
        for number, code in options.items():
            typer.echo(f"  {number}) {language_name(code)}", err=True)
        typer.echo("> ", nl=False, err=True)
        answer = sys.stdin.readline().strip().lower()
        chosen = (options.get(answer) or normalize_lang(answer)) if answer else None
        if chosen in SUPPORTED_LANGS:
            return chosen
        typer.echo(t("menu.invalid", MENU_FALLBACK_LANG), err=True)
    typer.echo(t("menu.fallback", MENU_FALLBACK_LANG), err=True)
    return MENU_FALLBACK_LANG


def choose_and_save_language() -> str:
    """Pregunta el idioma con el menú, lo guarda y avisa si no se pudo guardar."""
    lang = prompt_language()
    message = "menu.saved" if save_language(lang) else "menu.not_saved"
    typer.echo(t(message, lang, name=language_name(lang)), err=True)
    return lang


def resolve_language(cli_lang: str | None, interactive: bool) -> str:
    """Prioridad: ``--lang`` > idioma guardado > menú (si es interactivo) > sistema."""
    if cli_lang:
        return cli_lang
    saved = load_language()
    if saved:
        return saved
    if interactive:
        return choose_and_save_language()
    return system_language()


def help_language(argv: Sequence[str]) -> str:
    """Idioma para ``--help`` sin mostrar menú: ``--lang`` > guardado > sistema."""
    for index, arg in enumerate(argv):
        value = None
        if arg == "--lang" and index + 1 < len(argv):
            value = argv[index + 1]
        elif arg.startswith("--lang="):
            value = arg.split("=", 1)[1]
        chosen = normalize_lang(value)
        if chosen:
            return chosen
    return load_language() or system_language()


# --- Ejecución ----------------------------------------------------------------------


def make_console(no_color: bool, stderr: bool = False) -> Console:
    """Consola ``rich`` con ancho máximo de ``MAX_WIDTH`` columnas y colores opcionales."""
    plain = no_color or bool(os.environ.get("NO_COLOR"))
    console = Console(stderr=stderr, color_system=None if plain else "auto", highlight=False)
    console.width = min(console.width, MAX_WIDTH)
    return console


def _fail(console: Console, message: str, lang: str, code: int) -> int:
    console.print(f"[bold red]{t('error.prefix', lang)}:[/] ", end="")
    console.print(message, markup=False)
    return code


def run(options: RunOptions) -> int:
    """Ejecuta el programa con opciones ya parseadas y devuelve el exit code."""
    err = make_console(options.no_color, stderr=True)
    cli_lang = normalize_lang(options.lang) if options.lang is not None else None
    if options.lang is not None and cli_lang is None:
        fallback = load_language() or system_language()
        supported = ", ".join(SUPPORTED_LANGS)
        message = t("error.invalid_lang", fallback, value=options.lang, options=supported)
        return _fail(err, message, fallback, EXIT_USAGE)

    if options.change_lang:
        chosen = choose_and_save_language()
        if options.url is None:
            return EXIT_OK
        lang = cli_lang or chosen
    elif options.url is None:
        # Error de uso: no tiene sentido mostrar el menú antes de avisarlo.
        lang = cli_lang or load_language() or system_language()
        return _fail(err, t("error.missing_url", lang), lang, EXIT_USAGE)
    else:
        lang = resolve_language(cli_lang, is_interactive() and not options.machine_output)

    if options.url is None:
        return _fail(err, t("error.missing_url", lang), lang, EXIT_USAGE)
    if options.max_pages < 1:
        return _fail(err, t("error.invalid_max_pages", lang), lang, EXIT_USAGE)
    if options.timeout <= 0:
        return _fail(err, t("error.invalid_timeout", lang), lang, EXIT_USAGE)
    if options.json_output and options.markdown:
        return _fail(err, t("error.json_and_md", lang), lang, EXIT_USAGE)
    return _analyze_and_print(options, lang, err)


def _analyze_and_print(options: RunOptions, lang: str, err: Console) -> int:
    assert options.url is not None

    def on_event(code: str, **params: object) -> None:
        if options.verbose:
            err.print(f"[dim]· {escape(format_event(code, lang, **params))}[/]")

    settings = options.analyze_options()
    try:
        if options.verbose or not err.is_terminal:
            result = analyze(options.url, options.max_pages, options=settings, on_event=on_event)
        else:
            with err.status(t("status.analyzing", lang, url=options.url)):
                result = analyze(
                    options.url, options.max_pages, options=settings, on_event=on_event
                )
    except FetchError as error:
        return _fail(err, format_error(error, lang), lang, EXIT_NETWORK)
    except KeyboardInterrupt:
        return _fail(err, t("error.interrupted", lang), lang, EXIT_NETWORK)
    except Exception as error:  # nunca mostrar un stack trace al usuario
        return _fail(err, t("error.unexpected", lang, detail=error), lang, EXIT_NETWORK)

    if options.json_output:
        typer.echo(to_json(result, lang))
    elif options.markdown:
        typer.echo(to_markdown(result, lang, verbose=options.verbose), nl=False)
    else:
        render(result, lang, make_console(options.no_color), verbose=options.verbose)
    return EXIT_OK


# --- Typer --------------------------------------------------------------------------


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"webscope {__version__}")
        raise typer.Exit()


def _help_callback(ctx: typer.Context, value: bool) -> None:
    if value and not ctx.resilient_parsing:
        text = ctx.get_help()
        if text:
            typer.echo(text)
        raise typer.Exit()


def build_app(lang: str) -> typer.Typer:
    """Crea la app de typer con la ayuda (``--help``) traducida a ``lang``."""
    app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)
    args_panel = t("help.panel_args", lang)
    opts_panel = t("help.panel_options", lang)

    @app.command(
        help=t("help.description", lang), epilog=t("help.epilog", lang), add_help_option=False
    )
    def main_command(
        url: Annotated[
            str | None,
            typer.Argument(
                metavar="URL",
                help=t("help.url", lang),
                show_default=False,
                rich_help_panel=args_panel,
            ),
        ] = None,
        max_pages: Annotated[
            int,
            typer.Option("--max-pages", help=t("help.max_pages", lang), rich_help_panel=opts_panel),
        ] = DEFAULT_MAX_PAGES,
        json_output: Annotated[
            bool, typer.Option("--json", help=t("help.json", lang), rich_help_panel=opts_panel)
        ] = False,
        markdown: Annotated[
            bool, typer.Option("--md", help=t("help.md", lang), rich_help_panel=opts_panel)
        ] = False,
        brief: Annotated[
            bool, typer.Option("--brief", help=t("help.brief", lang), rich_help_panel=opts_panel)
        ] = False,
        no_crawl: Annotated[
            bool,
            typer.Option("--no-crawl", help=t("help.no_crawl", lang), rich_help_panel=opts_panel),
        ] = False,
        rdap: Annotated[
            bool, typer.Option("--rdap", help=t("help.rdap", lang), rich_help_panel=opts_panel)
        ] = False,
        timeout: Annotated[
            float,
            typer.Option("--timeout", help=t("help.timeout", lang), rich_help_panel=opts_panel),
        ] = DEFAULT_TIMEOUT,
        lang_option: Annotated[
            str | None,
            typer.Option(
                "--lang",
                metavar="|".join(SUPPORTED_LANGS),
                help=t("help.lang", lang),
                show_default=False,
                rich_help_panel=opts_panel,
            ),
        ] = None,
        verbose: Annotated[
            bool,
            typer.Option(
                "--verbose", "-v", help=t("help.verbose", lang), rich_help_panel=opts_panel
            ),
        ] = False,
        no_color: Annotated[
            bool,
            typer.Option("--no-color", help=t("help.no_color", lang), rich_help_panel=opts_panel),
        ] = False,
        change_lang: Annotated[
            bool,
            typer.Option(
                "--change-lang", help=t("help.change_lang", lang), rich_help_panel=opts_panel
            ),
        ] = False,
        _version: Annotated[
            bool,
            typer.Option(
                "--version",
                help=t("help.version", lang),
                callback=_version_callback,
                is_eager=True,
                rich_help_panel=opts_panel,
            ),
        ] = False,
        _help: Annotated[
            bool,
            typer.Option(
                "--help",
                "-h",
                help=t("help.help", lang),
                callback=_help_callback,
                is_eager=True,
                expose_value=False,
                rich_help_panel=opts_panel,
            ),
        ] = False,
    ) -> None:
        options = RunOptions(
            url=url,
            max_pages=max_pages,
            json_output=json_output,
            lang=lang_option,
            verbose=verbose,
            no_color=no_color,
            change_lang=change_lang,
            brief=brief,
            markdown=markdown,
            no_crawl=no_crawl,
            rdap=rdap,
            timeout=timeout,
        )
        raise typer.Exit(run(options))

    return app


def _configure_stdio() -> None:
    """Usa UTF-8 al redirigir la salida (en Windows la consola por defecto es cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None and not stream.isatty():
            reconfigure(encoding="utf-8", errors="replace")


def main() -> None:
    """Entry point del comando ``webscope``."""
    _configure_stdio()
    build_app(help_language(sys.argv[1:]))(prog_name="webscope")
