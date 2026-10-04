from site_audit.css import (
    collect_variables,
    contrast_ratio,
    extract_urls,
    parse_color,
    parse_css,
    parse_declarations,
    resolve_variables,
)


def test_rules_and_media_context():
    sheet = parse_css(
        """
        body { color: #222; background: #fff }
        @media (min-width: 800px) { .box { width: 900px; } }
        @font-face { font-family: X; src: url(data:font/woff2;base64,AAAA) format("woff2"); }
        @import url("other.css");
        """
    )
    selectors = {r.selector: r for r in sheet.rules}
    assert selectors["body"].declarations["color"] == "#222"
    assert selectors[".box"].context.startswith("@media")
    assert "src" in selectors["@font-face"].declarations
    assert sheet.imports == ["other.css"]


def test_semicolon_inside_url_does_not_split_declaration():
    declarations = parse_declarations("background: url(data:image/png;base64,AAAA) no-repeat; color: red")
    assert declarations["color"] == "red"
    assert declarations["background"].startswith("url(data:image/png;base64")


def test_extract_urls_skips_data_uris():
    css = "a{background:url('x.png')} @import 'y.css'; b{background:url(data:image/gif;base64,R0lG)}"
    assert sorted(extract_urls(css)) == ["x.png", "y.css"]


def test_parse_color_variants():
    assert parse_color("#fff") == (255, 255, 255)
    assert parse_color("#336699") == (51, 102, 153)
    assert parse_color("rgb(10, 20, 30)") == (10, 20, 30)
    assert parse_color("rgb(10 20 30 / 50%)") is None
    assert parse_color("hsl(0 100% 50%)") == (255, 0, 0)
    assert parse_color("transparent") is None
    assert parse_color("kein-wert") is None


def test_contrast_ratio_reference_values():
    assert round(contrast_ratio((0, 0, 0), (255, 255, 255)), 1) == 21.0
    assert round(contrast_ratio((119, 119, 119), (255, 255, 255)), 2) == 4.48
    assert contrast_ratio((255, 255, 255), (255, 255, 255)) == 1.0


def test_variables_resolve_with_fallback():
    sheet = parse_css(":root{--text:#112233;--bg:var(--text)} p{color:var(--missing, #abc)}")
    variables = collect_variables(sheet.rules)
    assert resolve_variables("var(--bg)", variables) == "#112233"
    assert resolve_variables("var(--missing, #abc)", variables) == "#abc"
