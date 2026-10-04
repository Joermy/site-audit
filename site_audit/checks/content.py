from __future__ import annotations

import re
from datetime import timezone
from email.utils import parsedate_to_datetime

from . import check

COPYRIGHT = re.compile(r"(?:©|&copy;|\(c\)|copyright)\s*(?:(\d{4})\s*[-–—]\s*)?(\d{4})", re.I)


def _latest_copyright_year(text: str) -> int | None:
    years = [int(m.group(2)) for m in COPYRIGHT.finditer(text) if 1990 <= int(m.group(2)) <= 2100]
    return max(years) if years else None


@check("content.stale", title="Letzte sichtbare Aktualisierung", severity="hinweis")
def stale(page, make):
    this_year = page.now.year
    year = _latest_copyright_year(page.soup.get_text(" ", strip=True))
    modified = None
    header = page.headers.get("last-modified")
    if header:
        try:
            modified = parsedate_to_datetime(header)
            if modified.tzinfo is None:
                modified = modified.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            modified = None
    value = {"copyright_jahr": year, "last_modified": modified.date().isoformat() if modified else None}
    if year is None and modified is None:
        return make.unknown("Weder ein Copyright-Jahr noch ein Last-Modified-Header gefunden.", value=value)
    newest = max(y for y in (year, modified.year if modified else None) if y is not None)
    age = this_year - newest
    if age >= 3:
        return make.problem(f"Die jüngste Jahresangabe ist {newest}, das sind {age} Jahre.", value=value, severity="mittel")
    if age >= 2:
        return make.problem(f"Die jüngste Jahresangabe ist {newest}.", value=value)
    return make.ok(f"Die jüngste Jahresangabe ist {newest}.", value=value)
