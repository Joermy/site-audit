from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Sequence
from urllib.parse import urlsplit

from . import __version__
from .audit import AuditResult, available_checks, run_audit
from .fetch import HttpNetwork, Network, RobotsBlocked
from .finding import SEVERITY_ORDER, Severity, Status, parse_severity
from .page import normalize_url
from .report import EXTENSIONS, RENDERERS

EXIT_OK = 0
EXIT_FINDINGS = 1
EXIT_ERROR = 2
EXIT_ROBOTS = 3

SEVERITY_STYLE = {
    Severity.CRITICAL: "bold red",
    Severity.HIGH: "red",
    Severity.MEDIUM: "yellow",
    Severity.NOTE: "cyan",
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="site-audit",
        description="Prüft die Startseite einer Website auf Technik- und Pflichtmängel und schreibt einen Bericht.",
    )
    parser.add_argument("url", nargs="?", help="Adresse der Seite, zum Beispiel https://www.beispiel.de")
    parser.add_argument("--datei", metavar="DATEI", help="Textdatei mit einer Adresse je Zeile")
    parser.add_argument("--format", choices=["console", "md", "html", "json"], help="Ausgabeformat (Standard: console, bei --out-dir md)")
    parser.add_argument("--out", metavar="DATEI", help="Bericht in diese Datei schreiben")
    parser.add_argument("--out-dir", metavar="ORDNER", help="Bei mehreren Adressen: ein Bericht je Adresse in diesen Ordner")
    parser.add_argument("--nur", metavar="IDS", help="Nur diese Prüfungen oder Gruppen, kommagetrennt, zum Beispiel tls,legal.impressum")
    parser.add_argument("--delay", type=float, default=1.0, help="Mindestabstand zwischen zwei Anfragen an dieselbe Domain in Sekunden (Standard 1.0)")
    parser.add_argument("--timeout", type=float, default=15.0, help="Zeitlimit je Anfrage in Sekunden (Standard 15)")
    parser.add_argument("--max-resources", type=int, default=60, help="Höchstzahl gemessener eigener Ressourcen (Standard 60)")
    parser.add_argument(
        "--fail-on",
        choices=["kritisch", "hoch", "mittel", "hinweis", "nie"],
        default="nie",
        help="Exit-Code 1, wenn ein Befund mindestens diesen Schweregrad hat (Standard nie)",
    )
    parser.add_argument("--liste", action="store_true", help="Alle Prüfungen auflisten und beenden")
    parser.add_argument("--version", action="version", version=f"site-audit {__version__}")
    return parser


def make_network(args: argparse.Namespace) -> Network:
    return HttpNetwork(delay=args.delay, timeout=args.timeout)


def read_url_file(path: str) -> list[str]:
    urls = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


def file_stem(url: str) -> str:
    host = urlsplit(normalize_url(url)).hostname or "seite"
    return re.sub(r"[^a-z0-9.-]+", "-", host.lower()).strip("-.")


def print_console(result: AuditResult) -> None:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    console.print(f"[bold]Prüfbericht für {result.final_url}[/bold]")
    for warning in result.warnings:
        console.print(f"[yellow]Hinweis:[/yellow] {warning}")
    table = Table(show_lines=False, header_style="bold")
    table.add_column("Grad")
    table.add_column("Prüfung", no_wrap=True)
    table.add_column("Befund")
    for finding in result.problems:
        style = SEVERITY_STYLE[finding.severity]
        suffix = " (Schätzung)" if finding.estimate else ""
        table.add_row(f"[{style}]{finding.severity.value}[/{style}]", finding.check_id, finding.message + suffix)
    if result.problems:
        console.print(table)
    else:
        console.print("[green]Keine Auffälligkeiten gefunden.[/green]")
    counts = result.count_by_severity()
    summary = " · ".join(f"{counts[s]} {s.value}" for s in SEVERITY_ORDER)
    console.print(f"{summary} · {len(result.passed)} bestanden · {len(result.unknown)} nicht bestimmbar")


def write_report(result: AuditResult, fmt: str, target: Path | None) -> None:
    text = RENDERERS[fmt](result)
    if target is None:
        sys.stdout.write(text)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8", newline="\n")


def exit_code_for(results: Sequence[AuditResult], fail_on: str) -> int:
    if fail_on == "nie":
        return EXIT_OK
    threshold = parse_severity(fail_on)
    for result in results:
        worst = result.worst()
        if worst is not None and worst.rank <= threshold.rank:
            return EXIT_FINDINGS
    return EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.liste:
        for check_id, severity, title in available_checks():
            print(f"{check_id:22} {severity:8} {title}")
        return EXIT_OK

    urls: list[str] = []
    if args.datei:
        try:
            urls = read_url_file(args.datei)
        except OSError as exc:
            print(f"Datei nicht lesbar: {exc}", file=sys.stderr)
            return EXIT_ERROR
    if args.url:
        urls.insert(0, args.url)
    if not urls:
        parser.print_usage(sys.stderr)
        print("Es fehlt eine Adresse oder --datei.", file=sys.stderr)
        return EXIT_ERROR

    batch = len(urls) > 1 or bool(args.out_dir)
    fmt = args.format or ("md" if args.out_dir else "console")
    if fmt == "console" and args.out:
        fmt = "md"
    if batch and not args.out_dir and fmt != "console":
        print("Bei mehreren Adressen --out-dir angeben.", file=sys.stderr)
        return EXIT_ERROR

    only = [part.strip() for part in args.nur.split(",") if part.strip()] if args.nur else None
    results: list[AuditResult] = []
    exit_code = EXIT_OK
    network = make_network(args)
    try:
        for url in urls:
            try:
                result = run_audit(url, network, max_resources=args.max_resources, only=only)
            except RobotsBlocked:
                print(f"{url}: robots.txt verbietet den Abruf, es wird nichts geprüft.", file=sys.stderr)
                exit_code = max(exit_code, EXIT_ROBOTS)
                continue
            except (ConnectionError, ValueError) as exc:
                print(f"{url}: {exc}", file=sys.stderr)
                exit_code = max(exit_code, EXIT_ERROR)
                continue
            results.append(result)
            if fmt == "console":
                print_console(result)
            elif args.out_dir:
                target = Path(args.out_dir) / f"{file_stem(url)}{EXTENSIONS[fmt]}"
                write_report(result, fmt, target)
                print(f"{url}: {len(result.problems)} Befunde -> {target}")
            else:
                write_report(result, fmt, Path(args.out) if args.out else None)
                if args.out:
                    print(f"Bericht geschrieben: {args.out}", file=sys.stderr)
    finally:
        close = getattr(network, "close", None)
        if close:
            close()

    findings_code = exit_code_for(results, args.fail_on)
    return max(exit_code, findings_code)


if __name__ == "__main__":
    raise SystemExit(main())
