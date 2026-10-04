# site-audit

Kommandozeilenwerkzeug, das die Startseite einer Website auf Technik- und Pflichtmängel prüft und einen Bericht schreibt, als Konsolenübersicht, Markdown, HTML oder JSON.

Jede Prüfung liefert einen **Befund mit Messwert und Fundstelle**. Es gibt keine Bewertung ohne Zahl, und was nur geschätzt ist, steht als Schätzung im Bericht.

```
Prüfbericht für https://joermy.github.io/
┌────────┬─────────────┬──────────────────────────────────────────────────────┐
│ Grad   │ Prüfung     │ Befund                                               │
├────────┼─────────────┼──────────────────────────────────────────────────────┤
│ mittel │ sec.headers │ 5 von 6 Sicherheits-Headern fehlen:                  │
│        │             │ Content-Security-Policy, X-Content-Type-Options:     │
│        │             │ nosniff, X-Frame-Options oder frame-ancestors,       │
│        │             │ Referrer-Policy, Permissions-Policy.                 │
└────────┴─────────────┴──────────────────────────────────────────────────────┘
0 kritisch · 0 hoch · 1 mittel · 0 hinweis · 24 bestanden · 0 nicht bestimmbar
```

Das ist ein echter Lauf gegen die eigene Portfolio-Seite am 04.10.2026. Dass die fünf Header fehlen, liegt am Hoster: GitHub Pages erlaubt keine eigenen Antwort-Header. Der vollständige Bericht liegt in [`beispiele/joermy.github.io.md`](beispiele/joermy.github.io.md).

## Installieren

Python 3.10 oder neuer.

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[test]"
```

Unter Linux und macOS heißt der Ordner `.venv/bin` statt `.venv/Scripts`.

## Benutzen

```bash
python -m site_audit https://www.beispiel.de
python -m site_audit https://www.beispiel.de --format md --out bericht.md
python -m site_audit https://www.beispiel.de --format html --out bericht.html
python -m site_audit --datei urls.txt --out-dir berichte/
python -m site_audit https://www.beispiel.de --nur tls,legal.impressum
python -m site_audit --liste
```

| Option | Wirkung |
|---|---|
| `--format console\|md\|html\|json` | Ausgabeformat. Standard `console`, bei `--out-dir` `md` |
| `--out DATEI` | Bericht in eine Datei schreiben |
| `--datei DATEI` | Textdatei mit einer Adresse je Zeile, `#` leitet einen Kommentar ein |
| `--out-dir ORDNER` | Ein Bericht je Adresse, Dateiname aus dem Host |
| `--nur IDS` | Nur diese Prüfungen oder Gruppen, kommagetrennt |
| `--delay SEKUNDEN` | Mindestabstand zwischen Anfragen an dieselbe Domain, Standard 1,0 |
| `--timeout SEKUNDEN` | Zeitlimit je Anfrage, Standard 15 |
| `--max-resources N` | Höchstzahl gemessener eigener Ressourcen, Standard 60 |
| `--fail-on kritisch\|hoch\|mittel\|hinweis\|nie` | Exit-Code 1, sobald ein Befund diesen Schweregrad erreicht. Standard `nie` |

Exit-Codes: `0` in Ordnung, `1` Befund über der Schwelle von `--fail-on`, `2` Eingabe- oder Verbindungsfehler, `3` `robots.txt` verbietet den Abruf.

Schweregrade: `kritisch`, `hoch`, `mittel`, `hinweis`. Der Bericht sortiert Befunde danach.

## Was geprüft wird

| ID | Schwere | Messwert |
|---|---|---|
| `tls.reachable` | kritisch | HTTPS erreichbar, Fehlertext wortgleich |
| `tls.cert` | kritisch | Gültigkeit und Restlaufzeit des Zertifikats in Tagen |
| `tls.redirect` | hoch | Kette der Statuscodes von `http://` bis zum Ziel |
| `meta.viewport` | hoch | Inhalt des viewport-Attributs |
| `meta.zoom` | mittel | `maximum-scale` unter 2 oder `user-scalable=no` |
| `layout.overflow375` | mittel | Stellen mit fester Breite über 375 px, **geschätzt** |
| `legal.impressum` | hoch | Link auf der Startseite, Adresse und Statuscode der Zielseite |
| `legal.datenschutz` | hoch | wie oben |
| `privacy.external` | mittel | Anfragen an fremde Domains, gruppiert |
| `privacy.fonts` | hoch | Schriften von Google oder anderen Diensten |
| `privacy.tracker` | mittel | bekannte Mess- und Werbedienste |
| `a11y.alt` | mittel | Bilder ohne `alt`, absolute Zahl und Gesamtzahl |
| `a11y.lang` | mittel | Wert von `<html lang>` |
| `a11y.headings` | mittel | fehlende `h1`, mehrfache `h1`, Sprünge zwischen Ebenen |
| `a11y.contrast` | mittel | niedrigstes Kontrastverhältnis aus Farbpaaren im CSS |
| `perf.weight` | mittel | Bytes je Ressourcentyp und gesamt |
| `perf.requests` | mittel | Anzahl der Anfragen, eigene und fremde |
| `content.stale` | hinweis | jüngstes Copyright-Jahr, `Last-Modified` |
| `seo.title`, `seo.description` | mittel, hinweis | Länge in Zeichen |
| `sec.headers` | mittel | fehlende der sechs Sicherheits-Header |
| `sec.cookies` | mittel | Cookies ohne `Secure`, `HttpOnly`, `SameSite` |
| `sec.mixed` | hoch | über HTTP geladene Ressourcen auf einer HTTPS-Seite |
| `sec.server` | hinweis | Software und Version im `Server`-Header |
| `sec.sri` | hinweis | fremde Skripte und Stile ohne `integrity` |

Eine Prüfung ist **eine Funktion** mit Dekorator. Neue Prüfung heißt, eine Funktion zu schreiben:

```python
from . import check

@check("a11y.lang", title="Sprache der Seite angegeben", severity="mittel")
def language(page, make):
    lang = (page.soup.find("html") or {}).get("lang", "").strip()
    if not lang:
        return make.problem("Das html-Element hat kein lang-Attribut.", where="<html>")
    return make.ok(f"Sprache: {lang}", value=lang)
```

Wirft eine Prüfung eine Ausnahme, wird daraus ein Befund „nicht bestimmbar“ und der Lauf geht weiter.

## So verhält sich das Werkzeug gegenüber fremden Seiten

- Es liest `robots.txt` und ruft nichts ab, was dort für den Agenten `site-audit` oder `*` verboten ist. Ist schon die Startseite gesperrt, bricht der Lauf mit Exit-Code 3 ab.
- Höchstens **eine Anfrage pro Sekunde** je Domain.
- Der `User-Agent` nennt Werkzeug, Version und den Link zu diesem Repository.
- Nur die aufgerufene Domain wird abgefragt. Fremde Ressourcen werden aufgelistet, aber **nicht** geladen.
- Es werden keine Formulare abgeschickt und keine Zugangsdaten verwendet.

Prüfe nur Seiten, für die du verantwortlich bist oder zu deren Prüfung du beauftragt wurdest.

## Grenzen

- **Kein Browser, kein JavaScript.** Seiten, die ihren Inhalt erst im Browser aufbauen, werden unvollständig bewertet. Ist der sichtbare Text sehr kurz und es gibt Skripte, steht dazu ein Hinweis im Bericht. (Beispiel: `https://example.com/` baut seine Überschrift per Skript auf, `a11y.headings` meldet dort deshalb keine Überschriften.)
- `layout.overflow375` ist eine **Schätzung** aus festen Breiten in CSS und HTML. Elemente mit `position: absolute` oder `fixed` und Regeln, die nur in `@media`-Blöcken stehen, zählen nicht. Eine Messung im Browser ersetzt das nicht.
- `a11y.contrast` rechnet nur Farbpaare, bei denen Textfarbe und Hintergrund **im selben CSS-Block** stehen, dazu das Paar aus `html` und `body`. Farben aus Verläufen, Bildern oder dem Dunkelmodus (`prefers-color-scheme`) bleiben außen vor.
- Das Gewicht zählt nur eigene Ressourcen der Domain. Fremde Ressourcen fehlen in der Summe.
- Geprüft wird die **Startseite** und die dort verlinkten Seiten Impressum und Datenschutz, nicht die ganze Website.
- Kein Ersatz für Lighthouse oder einen Penetrationstest. Das Werkzeug ergänzt beides.
- Die Berichte beschreiben technische Beobachtungen. Sie sind keine Rechtsberatung. Ob ein Impressum oder eine Datenschutzerklärung rechtlich ausreicht, prüft das Werkzeug nicht.

## Aufbau

```
site_audit/
  __main__.py     Einstieg für python -m site_audit
  cli.py          Argumente, Ausgabe, Exit-Codes
  audit.py        Ablauf: Seite laden, Prüfungen laufen lassen, Ergebnis sortieren
  fetch.py        HTTP mit Ratenbegrenzung, robots.txt, Weiterleitungsketten, Zertifikatsabfrage
  page.py         geladene Seite und alle Unterressourcen
  css.py          kleiner CSS-Leser, Farben, Kontrastverhältnis
  finding.py      Befund, Schweregrad, Status
  checks/         eine Datei je Gruppe, jede Prüfung meldet sich selbst an
  report/         Markdown, HTML, JSON
tests/
  fixtures/       gespeicherte Seiten, im Test gibt es keinen Netzzugriff
```

Abhängigkeiten: `httpx`, `beautifulsoup4`, `lxml`, `rich`. Zum Testen `pytest` und `respx`.

## Tests

```bash
.venv/Scripts/python -m pytest
```

Die Tests laufen ohne Netzwerk. Eine Test-Netzschicht liefert gespeicherte Antworten, `respx` ersetzt `httpx` für die Prüfung der Abrufschicht (Weiterleitungen, `robots.txt`, Größengrenze, Ratenbegrenzung). Zwei Fixture-Seiten dienen als Gegenstück: `gute-seite.html` darf keinen Befund auslösen, `kaputte-seite.html` muss 16 bestimmte Befunde auslösen, darunter fehlendes Impressum, gesperrten Zoom, Bilder ohne `alt` und Google Fonts.

## Lizenz

MIT, siehe [LICENSE](LICENSE).
