from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass, field

COMMENT = re.compile(r"/\*.*?\*/", re.S)
URL_FUNC = re.compile(r"url\(\s*(['\"]?)(.*?)\1\s*\)", re.I | re.S)
IMPORT = re.compile(r"@import\s+(?:url\(\s*)?(['\"]?)([^'\")\s;]+)\1", re.I)
VAR_FUNC = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^)]*))?\)", re.I)

CONTAINER_AT_RULES = ("@media", "@supports", "@layer", "@container", "@document")

NAMED_COLORS = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "orange": (255, 165, 0),
    "purple": (128, 0, 128),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "silver": (192, 192, 192),
    "lightgray": (211, 211, 211),
    "lightgrey": (211, 211, 211),
    "darkgray": (169, 169, 169),
    "darkgrey": (169, 169, 169),
    "navy": (0, 0, 128),
    "teal": (0, 128, 128),
    "maroon": (128, 0, 0),
    "lime": (0, 255, 0),
    "aqua": (0, 255, 255),
    "cyan": (0, 255, 255),
    "fuchsia": (255, 0, 255),
    "magenta": (255, 0, 255),
    "pink": (255, 192, 203),
    "brown": (165, 42, 42),
    "gold": (255, 215, 0),
    "ivory": (255, 255, 240),
    "beige": (245, 245, 220),
}


@dataclass
class Rule:
    selector: str
    declarations: dict[str, str]
    context: str = ""


@dataclass
class Stylesheet:
    rules: list[Rule] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


def split_top_level(text: str, separator: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    quote = ""
    current: list[str] = []
    for ch in text:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            current.append(ch)
        elif ch == "(":
            depth += 1
            current.append(ch)
        elif ch == ")":
            depth = max(0, depth - 1)
            current.append(ch)
        elif ch == separator and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return parts


def parse_declarations(body: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for part in split_top_level(body, ";"):
        if ":" not in part:
            continue
        name, _, value = part.partition(":")
        name = name.strip().lower()
        value = re.sub(r"\s*!important\s*$", "", value.strip(), flags=re.I)
        if name:
            result[name] = value
    return result


def parse_css(text: str) -> Stylesheet:
    text = COMMENT.sub("", text)
    sheet = Stylesheet()
    stack: list[dict] = []
    buffer: list[str] = []
    paren = 0
    quote = ""
    for ch in text:
        if quote:
            buffer.append(ch)
            if ch == quote:
                quote = ""
            continue
        if ch in "\"'":
            quote = ch
            buffer.append(ch)
            continue
        if ch == "(":
            paren += 1
        elif ch == ")":
            paren = max(0, paren - 1)
        if paren > 0:
            buffer.append(ch)
            continue
        if ch == "{":
            stack.append({"header": "".join(buffer).strip(), "body": []})
            buffer = []
        elif ch == "}":
            if stack:
                if buffer:
                    stack[-1]["body"].append("".join(buffer))
                node = stack.pop()
                header = node["header"]
                is_container = header.lower().startswith(CONTAINER_AT_RULES)
                if not is_container and header:
                    context = " ".join(s["header"].lower() for s in stack if s["header"].startswith("@"))
                    sheet.rules.append(
                        Rule(
                            selector=header,
                            declarations=parse_declarations(";".join(node["body"])),
                            context=context,
                        )
                    )
            buffer = []
        elif ch == ";":
            if stack:
                stack[-1]["body"].append("".join(buffer))
            else:
                statement = "".join(buffer).strip()
                match = IMPORT.match(statement)
                if match:
                    sheet.imports.append(match.group(2))
            buffer = []
        else:
            buffer.append(ch)
    return sheet


def extract_urls(text: str) -> list[str]:
    urls = [m.group(2).strip() for m in URL_FUNC.finditer(COMMENT.sub("", text))]
    urls += [m.group(2) for m in IMPORT.finditer(COMMENT.sub("", text))]
    return [u for u in urls if u and not u.startswith(("data:", "#"))]


def collect_variables(rules: list[Rule]) -> dict[str, str]:
    variables: dict[str, str] = {}
    for rule in rules:
        selectors = {s.strip().lower() for s in rule.selector.split(",")}
        if "prefers-color-scheme" in rule.context:
            continue
        if selectors & {":root", "html", "body"}:
            for name, value in rule.declarations.items():
                if name.startswith("--"):
                    variables[name] = value
    return variables


def resolve_variables(value: str, variables: dict[str, str], depth: int = 0) -> str:
    if depth > 4 or "var(" not in value:
        return value

    def replace(match: re.Match) -> str:
        name, fallback = match.group(1), match.group(2)
        if name in variables:
            return variables[name]
        return fallback.strip() if fallback else match.group(0)

    return resolve_variables(VAR_FUNC.sub(replace, value), variables, depth + 1)


def parse_color(value: str) -> tuple[int, int, int] | None:
    value = value.strip().lower()
    if not value or value in {"transparent", "inherit", "initial", "unset", "currentcolor"}:
        return None
    if value in NAMED_COLORS:
        return NAMED_COLORS[value]
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits)
        if len(digits) == 8:
            if int(digits[6:], 16) < 255:
                return None
            digits = digits[:6]
        if len(digits) == 6 and re.fullmatch(r"[0-9a-f]{6}", digits):
            return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
        return None
    match = re.fullmatch(r"rgba?\(([^)]*)\)", value)
    if match:
        parts = [p for p in re.split(r"[\s,/]+", match.group(1).strip()) if p]
        if len(parts) >= 4:
            alpha = parts[3]
            alpha_value = float(alpha[:-1]) / 100 if alpha.endswith("%") else float(alpha)
            if alpha_value < 1:
                return None
        if len(parts) >= 3:
            channels = []
            for part in parts[:3]:
                if part.endswith("%"):
                    channels.append(round(float(part[:-1]) * 2.55))
                else:
                    channels.append(round(float(part)))
            return tuple(max(0, min(255, c)) for c in channels)
        return None
    match = re.fullmatch(r"hsla?\(([^)]*)\)", value)
    if match:
        parts = [p for p in re.split(r"[\s,/]+", match.group(1).strip()) if p]
        if len(parts) >= 4 and float(parts[3].rstrip("%")) / (100 if parts[3].endswith("%") else 1) < 1:
            return None
        if len(parts) >= 3:
            hue = float(parts[0].rstrip("deg")) / 360
            sat = float(parts[1].rstrip("%")) / 100
            light = float(parts[2].rstrip("%")) / 100
            r, g, b = colorsys.hls_to_rgb(hue % 1, light, sat)
            return (round(r * 255), round(g * 255), round(b * 255))
    return None


def first_color_in(value: str) -> tuple[int, int, int] | None:
    for token in split_top_level(value, " "):
        token = token.strip()
        if not token:
            continue
        color = parse_color(token)
        if color:
            return color
    return None


def _channel(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4


def luminance(color: tuple[int, int, int]) -> float:
    r, g, b = color
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast_ratio(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = luminance(a), luminance(b)
    high, low = max(la, lb), min(la, lb)
    return (high + 0.05) / (low + 0.05)
