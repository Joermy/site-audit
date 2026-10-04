from __future__ import annotations

from html import escape

from ..audit import AuditResult
from ..finding import SEVERITY_ORDER, Finding

STYLE = """
:root{--bg:#fbfbfa;--fg:#1b1b1a;--muted:#5f5f5b;--line:#dcdcd6;--card:#ffffff;
--kritisch:#b3261e;--hoch:#c2410c;--mittel:#8a6100;--hinweis:#1d4f91;--ok:#1b6e3c}
@media (prefers-color-scheme:dark){:root{--bg:#121211;--fg:#ececea;--muted:#a3a39d;--line:#2c2c29;--card:#1a1a18;
--kritisch:#ff8a80;--hoch:#ffab76;--mittel:#f2c14e;--hinweis:#8ab4f8;--ok:#7fd49a}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,Segoe UI,sans-serif}
main{max-width:860px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:1.6rem;margin:0 0 4px;overflow-wrap:anywhere}
h2{font-size:1.15rem;margin:36px 0 12px}
p.meta{color:var(--muted);margin:0 0 24px}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:12px;margin:0 0 8px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.tile b{display:block;font-size:1.6rem}
.tile span{color:var(--muted);font-size:.9rem}
.finding{background:var(--card);border:1px solid var(--line);border-left-width:5px;border-radius:10px;padding:14px 16px;margin:0 0 12px}
.finding h3{font-size:1rem;margin:0 0 6px}
.finding p{margin:0 0 6px}
.finding dl{margin:0;color:var(--muted);font-size:.9rem;overflow-wrap:anywhere}
.finding dt{display:inline;font-weight:600}
.finding dd{display:inline;margin:0 12px 0 4px}
.kritisch{border-left-color:var(--kritisch)}.hoch{border-left-color:var(--hoch)}
.mittel{border-left-color:var(--mittel)}.hinweis{border-left-color:var(--hinweis)}
.tag{display:inline-block;font-size:.78rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;margin-right:6px}
.tag.kritisch{color:var(--kritisch)}.tag.hoch{color:var(--hoch)}.tag.mittel{color:var(--mittel)}.tag.hinweis{color:var(--hinweis)}
code{font-family:ui-monospace,Consolas,monospace;font-size:.88em}
table{width:100%;border-collapse:collapse;font-size:.92rem}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}
.warn{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px}
footer{color:var(--muted);font-size:.88rem;margin-top:40px}
"""


def _value(value) -> str:
    from . import format_value

    return escape(format_value(value))


def _problem(finding: Finding) -> str:
    parts = [
        f'<article class="finding {finding.severity.value}">',
        f'<h3><span class="tag {finding.severity.value}">{escape(finding.severity.value)}</span>'
        f'<code>{escape(finding.check_id)}</code> {escape(finding.title)}</h3>',
        f"<p>{escape(finding.message)}</p>",
    ]
    details = []
    if finding.value not in (None, "", [], {}):
        details.append(f"<dt>Messwert</dt><dd>{_value(finding.value)}</dd>")
    if finding.where:
        details.append(f"<dt>Fundstelle</dt><dd>{escape(finding.where)}</dd>")
    if finding.estimate:
        details.append("<dt>Hinweis</dt><dd>Schätzung, keine Messung</dd>")
    if details:
        parts.append("<dl>" + "".join(details) + "</dl>")
    parts.append("</article>")
    return "".join(parts)


def render(result: AuditResult) -> str:
    counts = result.count_by_severity()
    tiles = "".join(
        f'<div class="tile"><b>{counts[s]}</b><span>{escape(s.value)}</span></div>' for s in SEVERITY_ORDER
    )
    tiles += f'<div class="tile"><b>{len(result.passed)}</b><span>bestanden</span></div>'
    tiles += f'<div class="tile"><b>{len(result.unknown)}</b><span>nicht bestimmbar</span></div>'

    body = [
        f"<h1>Prüfbericht für {escape(result.final_url)}</h1>",
        f'<p class="meta">Erstellt am {result.started_at.strftime("%d.%m.%Y %H:%M")} UTC mit site-audit {escape(result.version)}</p>',
        f'<div class="summary">{tiles}</div>',
    ]
    if result.warnings:
        body.append("<h2>Einschränkungen dieses Laufs</h2>")
        body.append('<div class="warn"><ul>' + "".join(f"<li>{escape(w)}</li>" for w in result.warnings) + "</ul></div>")
    body.append("<h2>Befunde</h2>")
    if result.problems:
        body.extend(_problem(f) for f in result.problems)
    else:
        body.append("<p>Keine Auffälligkeiten gefunden.</p>")
    if result.unknown:
        body.append("<h2>Nicht bestimmbar</h2><table><tr><th>Prüfung</th><th>Grund</th></tr>")
        body.extend(f"<tr><td><code>{escape(f.check_id)}</code></td><td>{escape(f.message)}</td></tr>" for f in result.unknown)
        body.append("</table>")
    if result.passed:
        body.append("<h2>Bestanden</h2><table><tr><th>Prüfung</th><th>Ergebnis</th><th>Messwert</th></tr>")
        body.extend(
            f"<tr><td><code>{escape(f.check_id)}</code></td><td>{escape(f.message)}</td><td>{_value(f.value)}</td></tr>"
            for f in result.passed
        )
        body.append("</table>")
    body.append(
        "<footer>Dieser Bericht beschreibt technische Beobachtungen auf der Startseite. "
        "Er ist keine Rechtsberatung. Es wurde kein JavaScript ausgeführt.</footer>"
    )
    return (
        '<!doctype html><html lang="de"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Prüfbericht {escape(result.final_url)}</title><style>{STYLE}</style></head>"
        f"<body><main>{''.join(body)}</main></body></html>\n"
    )
