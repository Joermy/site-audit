# Prüfbericht für https://joermy.github.io/

Erstellt am 04.10.2026 08:50 UTC mit site-audit 0.1.0.

## Zusammenfassung

| Schweregrad | Anzahl |
|---|---:|
| kritisch | 0 |
| hoch | 0 |
| mittel | 1 |
| hinweis | 0 |

Bestanden: 24 · Nicht bestimmbar: 0

## Befunde

### [mittel] `sec.headers` — Sicherheits-Header

5 von 6 Sicherheits-Headern fehlen: Content-Security-Policy, X-Content-Type-Options: nosniff, X-Frame-Options oder frame-ancestors, Referrer-Policy, Permissions-Policy.

- Messwert: fehlend: Content-Security-Policy, X-Content-Type-Options: nosniff, X-Frame-Options oder frame-ancestors, Referrer-Policy, Permissions-Policy, vorhanden: strict-transport-security

## Bestanden

| Prüfung | Ergebnis | Messwert |
|---|---|---|
| `a11y.alt` | Das einzige Bild hat ein alt-Attribut. | ohne_alt: 0, gesamt: 1 |
| `a11y.contrast` | Niedrigster gemessener Kontrast 7.64:1 bei 7 Farbpaaren. | niedrigster: 7.64, bei: .demo-hinweis, gemessen: 7 |
| `a11y.headings` | 10 Überschriften ohne Sprünge. | 1, 2, 2, 3, 3, 3 … (+4) |
| `a11y.lang` | Sprache: de | de |
| `content.stale` | Die jüngste Jahresangabe ist 2026. | copyright_jahr: 2026, last_modified: 2026-10-03 |
| `layout.overflow375` | Keine festen Breiten über 375 px gefunden (Schätzung ohne Browser). |  |
| `legal.datenschutz` | Datenschutzerklärung ist verlinkt und erreichbar. | url: https://joermy.github.io/datenschutz/index.html, status: 200 |
| `legal.impressum` | Impressum ist verlinkt und erreichbar. | url: https://joermy.github.io/impressum/index.html, status: 200 |
| `meta.viewport` | viewport ist gesetzt. | width=device-width, initial-scale=1 |
| `meta.zoom` | Zoom ist nicht eingeschränkt. | width=device-width, initial-scale=1 |
| `perf.requests` | 19 Anfragen. | gesamt: 19, eigene: 19, fremde: 0 |
| `perf.weight` | Die Seite wiegt 180 KB. Fremde Ressourcen sind nicht eingerechnet. | css: 10704, font: 89360, html: 3607, img: 62858, js: 17766, gesamt: 184295 |
| `privacy.external` | Die Seite lädt nichts von fremden Domains. |  |
| `privacy.fonts` | Keine Schriften von fremden Diensten gefunden. |  |
| `privacy.tracker` | Keine bekannten Mess- oder Werbedienste gefunden. |  |
| `sec.cookies` | Die Startseite setzt keine Cookies. |  |
| `sec.mixed` | Alle Ressourcen werden über HTTPS geladen. |  |
| `sec.server` | Keine Versionsangabe im Server-Header. |  |
| `sec.sri` | Keine fremden Skripte oder Stile ohne integrity-Attribut. |  |
| `seo.description` | Beschreibung mit 91 Zeichen. | 91 |
| `seo.title` | Titel mit 27 Zeichen. | zeichen: 27, text: Joermy — Creative Developer |
| `tls.cert` | Zertifikat gültig, noch 27 Tage. | tage: 27, bis: 2026-10-31, aussteller: Let's Encrypt, tls: TLSv1.3 |
| `tls.reachable` | Die Seite wird über HTTPS ausgeliefert. | https://joermy.github.io/ |
| `tls.redirect` | HTTP leitet dauerhaft auf HTTPS um. | 301 http://joermy.github.io/, 200 https://joermy.github.io/ |

---

Dieser Bericht beschreibt technische Beobachtungen auf der Startseite. Er ist keine Rechtsberatung.
Es wurde kein JavaScript ausgeführt.
