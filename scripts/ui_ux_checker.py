#!/usr/bin/env python3
"""
UI/UX Mechanical Checker v1.2 (Zero-dependency Python 3.9+ stdlib only)
Evaluates HTML, CSS, Markdown, and Design Token JSON files deterministically.
"""

import argparse
import colorsys
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# -----------------------------
# Color & WCAG 2.2 Contrast Math
# -----------------------------
NAMED_COLORS = {
    "white": "#FFFFFF", "black": "#000000", "red": "#FF0000",
    "gray": "#808080", "grey": "#808080", "lightgray": "#D3D3D3",
    "lightgrey": "#D3D3D3", "darkgray": "#A9A9A9", "darkgrey": "#A9A9A9",
    "dimgray": "#696969", "dimgrey": "#696969", "silver": "#C0C0C0",
    "blue": "#0000FF", "navy": "#000080", "royalblue": "#4169E1",
    "green": "#008000", "darkgreen": "#006400", "lime": "#00FF00",
    "yellow": "#FFFF00", "orange": "#FFA500", "purple": "#800080",
    "teal": "#008080", "cyan": "#00FFFF", "magenta": "#FF00FF",
    "maroon": "#800000", "olive": "#808000", "crimson": "#DC143C",
    "indigo": "#4B0082", "slate": "#708090", "slategray": "#708090",
    "whitesmoke": "#F5F5F5", "ivory": "#FFFFF0", "beige": "#F5F5DC",
}

HEX_RE = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
VAR_RE = re.compile(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*(?:,\s*([^)]+))?\)")
RGBA = Tuple[int, int, int, float]


def clean_css_val(val: str) -> str:
    return re.sub(r"\s*!important\s*$", "", val.strip(), flags=re.IGNORECASE).strip()


def resolve_css_value(val: str, css_vars: Dict[str, str], depth: int = 0) -> str:
    v = clean_css_val(val)
    if depth > 5 or "var(" not in v:
        return v

    def repl(m: re.Match) -> str:
        var_name = m.group(1)
        fallback = m.group(2).strip() if m.group(2) else ""
        resolved = css_vars.get(var_name, fallback)
        return resolve_css_value(resolved, css_vars, depth + 1) if resolved else m.group(0)

    return VAR_RE.sub(repl, v).strip()


def parse_rgba(color_str: str, css_vars: Optional[Dict[str, str]] = None) -> Optional[RGBA]:
    s = resolve_css_value(color_str, css_vars or {}).strip().lower()
    if s == "transparent":
        return (0, 0, 0, 0.0)
    if s in NAMED_COLORS:
        s = NAMED_COLORS[s].lower()

    # Hex: #RGB, #RGBA, #RRGGBB, #RRGGBBAA
    if s.startswith("#"):
        h = s[1:]
        if all(c in "0123456789abcdef" for c in h):
            if len(h) == 3:
                return (int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16), 1.0)
            if len(h) == 4:
                return (int(h[0]*2, 16), int(h[1]*2, 16), int(h[2]*2, 16), int(h[3]*2, 16) / 255.0)
            if len(h) == 6:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 1.0)
            if len(h) == 8:
                return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) / 255.0)

    # rgb() / rgba()
    m = re.match(
        r"rgba?\(\s*(\d+(?:\.\d+)?)\s*[,\s]\s*(\d+(?:\.\d+)?)\s*[,\s]\s*(\d+(?:\.\d+)?)\s*(?:[,/]\s*(\d*\.?\d+%?))?\s*\)",
        s,
    )
    if m:
        r, g, b = int(float(m.group(1))), int(float(m.group(2))), int(float(m.group(3)))
        a_str = m.group(4)
        a = 1.0
        if a_str is not None:
            a = float(a_str[:-1]) / 100.0 if a_str.endswith("%") else float(a_str)
        return (min(255, r), min(255, g), min(255, b), max(0.0, min(1.0, a)))

    # hsl() / hsla()
    mh = re.match(
        r"hsla?\(\s*(\d+(?:\.\d+)?)(?:deg)?\s*[,\s]\s*(\d+(?:\.\d+)?)%\s*[,\s]\s*(\d+(?:\.\d+)?)%\s*(?:[,/]\s*(\d*\.?\d+%?))?\s*\)",
        s,
    )
    if mh:
        h_deg = (float(mh.group(1)) % 360.0) / 360.0
        sat = float(mh.group(2)) / 100.0
        light = float(mh.group(3)) / 100.0
        a_str = mh.group(4)
        a = 1.0
        if a_str is not None:
            a = float(a_str[:-1]) / 100.0 if a_str.endswith("%") else float(a_str)
        rf, gf, bf = colorsys.hls_to_rgb(h_deg, light, sat)
        return (round(rf * 255), round(gf * 255), round(bf * 255), max(0.0, min(1.0, a)))

    return None


def extract_color_from_shorthand(val: str, css_vars: Dict[str, str]) -> Optional[str]:
    resolved = resolve_css_value(val, css_vars)
    # Match functional colors or hex or named colors inside shorthand like "url(x.png) no-repeat #fff"
    for m in re.finditer(r"rgba?\([^)]+\)|hsla?\([^)]+\)|#[0-9a-fA-F]{3,8}\b|\b[a-zA-Z]+\b", resolved):
        tok = m.group(0)
        if parse_rgba(tok, css_vars) is not None and tok.lower() != "transparent":
            return tok
    return None


def composite_over(fg: RGBA, bg: RGBA) -> Tuple[int, int, int]:
    a = fg[3]
    r = round(fg[0] * a + bg[0] * (1.0 - a))
    g = round(fg[1] * a + bg[1] * (1.0 - a))
    b = round(fg[2] * a + bg[2] * (1.0 - a))
    return (r, g, b)


def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(c1: str, c2: str, css_vars: Optional[Dict[str, str]] = None) -> Tuple[Optional[float], Optional[str]]:
    fg = parse_rgba(c1, css_vars)
    bg = parse_rgba(c2, css_vars)
    if fg is None:
        return None, f"unparseable foreground color '{c1}'"
    if bg is None:
        return None, f"unparseable background color '{c2}'"
    if bg[3] < 1.0:
        return None, f"semi-transparent background '{c2}' requires rendered backdrop"
    fg_rgb = composite_over(fg, bg) if fg[3] < 1.0 else (fg[0], fg[1], fg[2])
    bg_rgb = (bg[0], bg[1], bg[2])
    l1 = relative_luminance(fg_rgb)
    l2 = relative_luminance(bg_rgb)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2), None


# -----------------------------
# Token Verification
# -----------------------------
def check_tokens_file(token_path: Path) -> Dict[str, Any]:
    data = json.loads(token_path.read_text(encoding="utf-8"))
    findings = []
    colors = data.get("colors", {})
    pairs = colors.get("verified_pairs", [])
    evaluated = 0
    for pair in pairs:
        theme = pair["theme"]
        fg_key = pair["fg"]
        bg_key = pair["bg"]
        min_ratio = pair["min_ratio"]
        palette = colors.get(theme, {})
        fg_val = palette.get(fg_key)
        bg_val = palette.get(bg_key)
        ratio, err = contrast_ratio(fg_val or "", bg_val or "")
        if ratio is not None:
            evaluated += 1
        if ratio is None or ratio < min_ratio:
            findings.append({
                "severity": "Blocker",
                "rule_id": "BLK-03",
                "target": f"tokens:{theme}:{fg_key} on {bg_key}",
                "evidence": f"fg={fg_val}, bg={bg_val}, ratio={ratio} (required >= {min_ratio}; {err or 'below threshold'})",
                "message": "Design token pair fails WCAG 2.2 AA contrast requirement.",
            })
    return {
        "file": str(token_path),
        "type": "design-tokens",
        "blocker_count": sum(1 for f in findings if f["severity"] == "Blocker"),
        "major_count": 0,
        "minor_count": 0,
        "coverage": {"color_pairs_found": len(pairs), "evaluated": evaluated, "skipped": []},
        "findings": findings,
    }


# -----------------------------
# CSS Theme-Scoped Parser & Inspector
# -----------------------------
def strip_css_comments(css: str) -> str:
    # Preserve newlines when stripping comments so line numbers stay exact
    return re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), css, flags=re.DOTALL)


def parse_declarations(decl_str: str) -> Dict[str, str]:
    props: Dict[str, str] = {}
    for decl in decl_str.split(";"):
        if ":" in decl:
            k, v = decl.split(":", 1)
            props[k.strip().lower()] = v.strip()
    return props


def parse_px(val: str, css_vars: Optional[Dict[str, str]] = None) -> Optional[float]:
    resolved = resolve_css_value(val, css_vars or {})
    m = re.match(r"^(\d+(?:\.\d+)?)px$", resolved.strip().lower())
    return float(m.group(1)) if m else None


def extract_css_rules_with_scopes(css: str, base_line: int = 1) -> Tuple[Dict[str, Dict[str, str]], List[Dict[str, Any]]]:
    """
    Lightweight brace-aware CSS walker supporting top-level rules and @media blocks.
    Returns (theme_vars_map, rules_list).
    """
    cleaned = strip_css_comments(css)
    theme_vars: Dict[str, Dict[str, str]] = {"default": {}}
    rules: List[Dict[str, Any]] = []

    i = 0
    n = len(cleaned)
    current_media: Optional[str] = None

    while i < n:
        # Skip whitespace
        while i < n and cleaned[i].isspace():
            i += 1
        if i >= n:
            break

        if cleaned[i] == "}":
            current_media = None
            i += 1
            continue

        # Find next '{' or ';'
        start = i
        while i < n and cleaned[i] not in "{;}":
            i += 1
        if i >= n:
            break
        if cleaned[i] == ";":
            i += 1
            continue
        if cleaned[i] == "}":
            current_media = None
            i += 1
            continue

        header = cleaned[start:i]
        sel_start = start + (len(header) - len(header.lstrip()))
        line_no = base_line + cleaned[:sel_start].count("\n")
        selector = " ".join(header.strip().split())
        i += 1  # consume '{'

        # @media / @supports container
        if selector.startswith("@media"):
            current_media = selector.lower()
            continue
        if selector.startswith("@"):
            # Skip other @-blocks like @keyframes
            depth = 1
            while i < n and depth > 0:
                if cleaned[i] == "{":
                    depth += 1
                elif cleaned[i] == "}":
                    depth -= 1
                i += 1
            continue

        # Normal rule body
        body_start = i
        depth = 1
        while i < n and depth > 0:
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
            i += 1
        body = cleaned[body_start : i - 1]
        props = parse_declarations(body)

        # Determine variable scope
        is_dark_media = current_media is not None and "prefers-color-scheme" in current_media and "dark" in current_media
        is_dark_attr = 'data-theme="dark"' in selector or "data-theme='dark'" in selector
        scope = "dark" if (is_dark_media or is_dark_attr) else "default"

        for k, v in props.items():
            if k.startswith("--"):
                theme_vars.setdefault(scope, {})[k] = clean_css_val(v)

        rules.append({
            "selector": selector,
            "line": line_no,
            "props": props,
            "scope": scope,
            "media": current_media,
        })

    return theme_vars, rules


INTERACTIVE_SEL_RE = re.compile(
    r"(?:^|[\s>+~,])(?:button|input|a)(?:$|[\s>+~,:.\[#])|\.(?:btn|icon-btn|button)(?:$|[\s>+~,:.\[#])",
    re.IGNORECASE,
)


def has_visible_focus_fallback(props: Dict[str, str]) -> bool:
    bs = clean_css_val(props.get("box-shadow", "")).lower()
    if bs and bs != "none" and "transparent" not in bs:
        return True
    for bprop in ("border", "border-color"):
        bv = clean_css_val(props.get(bprop, "")).lower()
        if bv and bv not in ("0", "0px", "none") and "transparent" not in bv and not re.match(r"^0(?:px)?\b", bv):
            return True
    return False


def inspect_style_props(
    findings: List[Dict[str, Any]],
    coverage: Dict[str, Any],
    target: str,
    props: Dict[str, str],
    theme_vars: Dict[str, Dict[str, str]],
    rule_scope: str = "default",
    tag: str = "",
    selector: str = "",
    strict_tokens: bool = False,
    has_focus_visible_rule: bool = False,
) -> None:
    # 1. Contrast check (BLK-03) across applicable themes
    fg_raw = props.get("color")
    bg_raw = props.get("background-color") or props.get("background")
    if fg_raw and bg_raw:
        uses_var = "var(" in fg_raw or "var(" in bg_raw
        themes_to_check = ["dark"] if rule_scope == "dark" else (
            ["default", "dark"] if (uses_var and "dark" in theme_vars) else ["default"]
        )
        for th in themes_to_check:
            merged_vars = dict(theme_vars.get("default", {}))
            if th == "dark":
                merged_vars.update(theme_vars.get("dark", {}))

            coverage["color_pairs_found"] += 1
            fg_token = extract_color_from_shorthand(fg_raw, merged_vars) or resolve_css_value(fg_raw, merged_vars)
            bg_token = extract_color_from_shorthand(bg_raw, merged_vars) or resolve_css_value(bg_raw, merged_vars)
            ratio, err = contrast_ratio(fg_token, bg_token, merged_vars)
            if ratio is None:
                coverage["skipped"].append({
                    "target": f"{target} [theme:{th}]",
                    "reason": err or "unparseable color pair",
                })
                continue

            coverage["evaluated"] += 1
            font_size = parse_px(props.get("font-size", ""), merged_vars)
            is_bold = clean_css_val(props.get("font-weight", "")).lower() in ("bold", "700", "800", "900")
            is_large = (font_size is not None and font_size >= 24) or (
                font_size is not None and font_size >= 18.66 and is_bold
            )
            threshold = 3.0 if is_large else 4.5
            if ratio < threshold:
                findings.append({
                    "severity": "Blocker",
                    "rule_id": "BLK-03",
                    "target": f"{target} [theme:{th}]" if len(themes_to_check) > 1 else target,
                    "evidence": f"color={fg_raw} ({fg_token}), background={bg_raw} ({bg_token}), contrast={ratio}:1 (required >= {threshold}:1)",
                    "message": "Text contrast ratio is below WCAG 2.2 AA threshold.",
                })
    elif fg_raw and not bg_raw:
        coverage["skipped"].append({
            "target": target,
            "reason": "color specified without background in same rule (inherited backdrop requires rendered check)",
        })

    # 2. Focus outline suppression (BLK-05)
    outline_val = clean_css_val(props.get("outline", "")).lower()
    is_focus_selector = ":focus" in selector.lower()
    is_not_focus_visible = ":not(:focus-visible)" in selector.lower()
    if outline_val in ("none", "0", "0px") and is_focus_selector and not is_not_focus_visible:
        if not has_visible_focus_fallback(props):
            # Allow :focus { outline: none } ONLY if a separate :focus-visible rule exists? No, still risky unless :not(:focus-visible)
            findings.append({
                "severity": "Blocker",
                "rule_id": "BLK-05",
                "target": target,
                "evidence": f"outline: {props.get('outline')} without visible replacement (box-shadow/border)",
                "message": "Removing focus outline without a visible replacement breaks keyboard accessibility.",
            })

    # 3. Interactive target size check (CHK-W2): width, height, min-width, min-height
    is_interactive = tag in ("button", "a", "input") or bool(INTERACTIVE_SEL_RE.search(selector))
    if is_interactive:
        default_vars = theme_vars.get("default", {})
        dims = {
            k: parse_px(props.get(k, ""), default_vars)
            for k in ("width", "height", "min-width", "min-height")
        }
        too_small = [f"{k}={props.get(k)}" for k, v in dims.items() if v is not None and v < 24]
        if too_small:
            findings.append({
                "severity": "Major",
                "rule_id": "CHK-W2",
                "target": target,
                "evidence": f"{', '.join(too_small)} (WCAG 2.2 AA min 24x24px)",
                "message": "Interactive target size is smaller than 24x24px.",
            })

    # 4. Token compliance check (CHK-W6): raw hex outside :root and [data-theme]
    if strict_tokens and ":root" not in selector and "data-theme" not in selector:
        for prop_name in ("color", "background-color", "background", "border", "border-color", "box-shadow"):
            val = props.get(prop_name, "")
            if val and "var(" not in val and HEX_RE.search(val):
                findings.append({
                    "severity": "Minor",
                    "rule_id": "CHK-W6",
                    "target": target,
                    "evidence": f"{prop_name}: {val} (raw hex instead of CSS token var(--...))",
                    "message": "Use semantic CSS token variables from tokens/design-tokens.css instead of raw hex values.",
                })


def check_css_file(path: Path, strict_tokens: bool = False) -> Dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    theme_vars, rules = extract_css_rules_with_scopes(content, base_line=1)
    findings: List[Dict[str, Any]] = []
    coverage: Dict[str, Any] = {"color_pairs_found": 0, "evaluated": 0, "skipped": []}
    has_fv = any(":focus-visible" in r["selector"].lower() for r in rules)

    for r in rules:
        inspect_style_props(
            findings,
            coverage,
            target=f"{path.name} '{r['selector']}' (line {r['line']})",
            props=r["props"],
            theme_vars=theme_vars,
            rule_scope=r["scope"],
            selector=r["selector"],
            strict_tokens=strict_tokens,
            has_focus_visible_rule=has_fv,
        )

    return {
        "file": str(path),
        "type": "css",
        "blocker_count": sum(1 for f in findings if f["severity"] == "Blocker"),
        "major_count": sum(1 for f in findings if f["severity"] == "Major"),
        "minor_count": sum(1 for f in findings if f["severity"] == "Minor"),
        "coverage": coverage,
        "findings": findings,
        "unverified_notes": [
            "UNV-W1: Visual hierarchy, inherited backgrounds & layout overlap require rendered viewport inspection.",
        ],
    }


# -----------------------------
# HTML Checker
# -----------------------------
GENERIC_LINK_EXACT = {
    "こちら", "ここ", "詳細", "詳細はこちら", "詳しくはこちら", "もっと見る", "続きを読む",
    "クリック", "リンク", "click here", "here", "more", "read more", "details", "link"
}


class UIHTMLChecker(HTMLParser):
    def __init__(self, base_dir: Path, strict_tokens: bool = False) -> None:
        super().__init__()
        self.base_dir = base_dir
        self.strict_tokens = strict_tokens
        self.findings: List[Dict[str, Any]] = []
        self.coverage: Dict[str, Any] = {"color_pairs_found": 0, "evaluated": 0, "skipped": []}
        self.headings: List[Tuple[int, int, str]] = []
        self.labels_for: set = set()
        self.inputs: List[Tuple[int, Dict[str, str]]] = []
        self.inline_styles: List[Tuple[int, str, Dict[str, str]]] = []
        self.external_css_hrefs: List[Tuple[int, str]] = []
        self.in_label = False
        self.in_style = False
        self.style_blocks: List[Tuple[int, str]] = []
        self.current_link: Optional[Dict[str, Any]] = None
        self.current_heading: Optional[Tuple[int, int, List[str]]] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        line = self.getpos()[0]
        attr_map = {k.lower(): (v or "") for k, v in attrs}

        if re.match(r"^h[1-6]$", tag):
            self.current_heading = (int(tag[1]), line, [])

        # External stylesheet link
        if tag == "link" and attr_map.get("rel", "").lower() == "stylesheet" and attr_map.get("href"):
            self.external_css_hrefs.append((line, attr_map["href"]))

        # Image alt check (BLK-05)
        if tag == "img":
            if "alt" not in attr_map:
                self.findings.append({
                    "severity": "Blocker",
                    "rule_id": "BLK-05",
                    "target": f"<img> at line {line}",
                    "evidence": f"src='{attr_map.get('src', '')}' has no alt attribute",
                    "message": "Missing alt attribute on <img>. Use descriptive text or alt=\"\" for decorative images.",
                })
            if self.current_link is not None and attr_map.get("alt", "").strip():
                self.current_link["has_alt"] = True

        # Non-semantic clickable div/span (BLK-05)
        if tag in ("div", "span") and "onclick" in attr_map:
            role = attr_map.get("role", "")
            tabindex = attr_map.get("tabindex", "")
            has_key_handler = any(k in attr_map for k in ("onkeydown", "onkeyup", "onkeypress"))
            if role not in ("button", "link") or not tabindex or not has_key_handler:
                self.findings.append({
                    "severity": "Blocker",
                    "rule_id": "BLK-05",
                    "target": f"<{tag} onclick=...> at line {line}",
                    "evidence": f"role='{role}', tabindex='{tabindex}', key_handler={has_key_handler}",
                    "message": "Clickable non-semantic element lacks full keyboard support. Use native <button> or <a href>.",
                })

        if tag == "label":
            self.in_label = True
            if attr_map.get("for"):
                self.labels_for.add(attr_map["for"])

        if tag in ("input", "textarea", "select"):
            itype = attr_map.get("type", "text").lower()
            if itype not in ("hidden", "submit", "button", "reset"):
                attr_map["_inside_label"] = "yes" if self.in_label else "no"
                self.inputs.append((line, attr_map))

        if tag == "a":
            self.current_link = {
                "line": line,
                "text": [],
                "aria_label": attr_map.get("aria-label", "").strip() or attr_map.get("aria-labelledby", "").strip(),
                "has_alt": False,
                "href": attr_map.get("href"),
            }

        if tag == "style":
            self.in_style = True

        style_str = attr_map.get("style", "")
        if style_str:
            self.inline_styles.append((line, tag, parse_declarations(style_str)))

    def handle_endtag(self, tag: str) -> None:
        if tag == "label":
            self.in_label = False
        if tag == "style":
            self.in_style = False
        if tag == "a" and self.current_link is not None:
            txt = "".join(self.current_link["text"]).strip()
            ln = self.current_link["line"]
            if self.current_link["href"] is not None:
                if not txt and not self.current_link["aria_label"] and not self.current_link["has_alt"]:
                    self.findings.append({
                        "severity": "Blocker",
                        "rule_id": "BLK-05",
                        "target": f"<a> at line {ln}",
                        "evidence": "Link has no visible text, non-empty img alt, or aria-label",
                        "message": "Link lacks an accessible name.",
                    })
                elif txt.lower() in GENERIC_LINK_EXACT:
                    self.findings.append({
                        "severity": "Major",
                        "rule_id": "CHK-W5",
                        "target": f"<a> at line {ln}",
                        "evidence": f"link text='{txt}'",
                        "message": "Generic link text fails scannability and accessibility. Describe the destination.",
                    })
            self.current_link = None
        if re.match(r"^h[1-6]$", tag) and self.current_heading is not None:
            lvl, ln, parts = self.current_heading
            self.headings.append((lvl, ln, "".join(parts).strip()))
            self.current_heading = None

    def handle_data(self, data: str) -> None:
        if self.in_style:
            self.style_blocks.append((self.getpos()[0], data))
        if self.current_link is not None:
            self.current_link["text"].append(data)
        if self.current_heading is not None:
            self.current_heading[2].append(data)

    def finalize(self) -> None:
        theme_vars: Dict[str, Dict[str, str]] = {"default": {}}
        all_css_sources: List[Tuple[str, List[Dict[str, Any]]]] = []

        # 1. Load local external CSS files
        for ln, href in self.external_css_hrefs:
            if href.startswith(("http://", "https://", "//")):
                self.coverage["skipped"].append({
                    "target": f"<link href='{href}'> at line {ln}",
                    "reason": "remote stylesheet skipped (offline checker)",
                })
                continue
            css_path = (self.base_dir / href).resolve()
            if css_path.exists() and css_path.is_file():
                tv, rules = extract_css_rules_with_scopes(css_path.read_text(encoding="utf-8"), base_line=1)
                for sc, mp in tv.items():
                    theme_vars.setdefault(sc, {}).update(mp)
                all_css_sources.append((css_path.name, rules))
            else:
                self.coverage["skipped"].append({
                    "target": f"<link href='{href}'> at line {ln}",
                    "reason": "local stylesheet file not found",
                })

        # 2. Extract embedded <style> blocks
        for base_line, css in self.style_blocks:
            tv, rules = extract_css_rules_with_scopes(css, base_line=base_line)
            for sc, mp in tv.items():
                theme_vars.setdefault(sc, {}).update(mp)
            all_css_sources.append(("<style>", rules))

        has_fv = any(
            ":focus-visible" in r["selector"].lower()
            for _, rlist in all_css_sources
            for r in rlist
        )

        # 3. Inspect inline styles
        for ln, tag, props in self.inline_styles:
            inspect_style_props(
                self.findings,
                self.coverage,
                target=f"<{tag}> at line {ln}",
                props=props,
                theme_vars=theme_vars,
                tag=tag,
                strict_tokens=self.strict_tokens,
                has_focus_visible_rule=has_fv,
            )

        # 4. Inspect CSS rules
        for src_name, rlist in all_css_sources:
            for r in rlist:
                inspect_style_props(
                    self.findings,
                    self.coverage,
                    target=f"{src_name} '{r['selector']}' (line {r['line']})",
                    props=r["props"],
                    theme_vars=theme_vars,
                    rule_scope=r["scope"],
                    selector=r["selector"],
                    strict_tokens=self.strict_tokens,
                    has_focus_visible_rule=has_fv,
                )

        # 5. Heading hierarchy checks (BLK-07): skip or starting at h3+
        prev_level = 0
        for idx_h, (lvl, ln, text) in enumerate(self.headings):
            if idx_h == 0 and lvl >= 3:
                self.findings.append({
                    "severity": "Blocker",
                    "rule_id": "BLK-07",
                    "target": f"<h{lvl}> at line {ln}",
                    "evidence": f"First heading starts at <h{lvl}> ('{text}') instead of <h1>/<h2>",
                    "message": "Document heading hierarchy starts too deep.",
                })
            elif prev_level > 0 and lvl > prev_level + 1:
                self.findings.append({
                    "severity": "Blocker",
                    "rule_id": "BLK-07",
                    "target": f"<h{lvl}> at line {ln}",
                    "evidence": f"Jumped from <h{prev_level}> to <h{lvl}> ('{text}')",
                    "message": "Heading hierarchy skipped a level.",
                })
            prev_level = lvl

        # 6. Form inputs without labels (BLK-04)
        for ln, attrs in self.inputs:
            iid = attrs.get("id", "")
            has_label = (
                attrs.get("_inside_label") == "yes"
                or (iid and iid in self.labels_for)
                or bool(attrs.get("aria-label"))
                or bool(attrs.get("aria-labelledby"))
            )
            if not has_label:
                placeholder = attrs.get("placeholder", "")
                self.findings.append({
                    "severity": "Blocker",
                    "rule_id": "BLK-04",
                    "target": f"form control at line {ln}",
                    "evidence": f"id='{iid}', placeholder='{placeholder}', no associated <label> or aria-label",
                    "message": "Form input lacks an accessible label (place <label for> above the input).",
                })


def check_html_file(path: Path, strict_tokens: bool = False) -> Dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    parser = UIHTMLChecker(base_dir=path.parent, strict_tokens=strict_tokens)
    parser.feed(content)
    parser.finalize()
    return {
        "file": str(path),
        "type": "html",
        "blocker_count": sum(1 for f in parser.findings if f["severity"] == "Blocker"),
        "major_count": sum(1 for f in parser.findings if f["severity"] == "Major"),
        "minor_count": sum(1 for f in parser.findings if f["severity"] == "Minor"),
        "coverage": parser.coverage,
        "findings": parser.findings,
        "unverified_notes": [
            "UNV-W1: Visual hierarchy, inherited backgrounds & layout overlap require rendered viewport inspection.",
            "UNV-W2: Perceived performance (100ms / 1s thresholds) requires runtime measurement.",
        ],
    }


# -----------------------------
# Markdown Checker
# -----------------------------
def strip_inline_code(line: str) -> str:
    return re.sub(r"`[^`]+`", "", line)


def visible_markdown_text(text: str) -> str:
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    t = re.sub(r"https?://\S+", "", t)
    return t.strip()


def is_mostly_english(text: str) -> bool:
    if not text:
        return False
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    return (ascii_chars / len(text)) > 0.75


def check_markdown_file(path: Path, doc_type: str = "general") -> Dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    findings: List[Dict[str, Any]] = []
    in_fence_char: Optional[str] = None
    prev_heading = 0
    seen_heading = False
    para_lines: List[Tuple[int, str]] = []

    ja_limit = 800 if doc_type == "spec" else 400
    en_word_limit = 250 if doc_type == "spec" else 150

    def flush_paragraph() -> None:
        nonlocal para_lines
        if not para_lines:
            return
        start_ln = para_lines[0][0]
        raw_text = " ".join(t for _, t in para_lines).strip()
        vis_text = visible_markdown_text(raw_text)
        if is_mostly_english(vis_text):
            words = len(vis_text.split())
            if words > en_word_limit:
                findings.append({
                    "severity": "Major",
                    "rule_id": "CHK-D2",
                    "target": f"Paragraph starting at line {start_ln}",
                    "evidence": f"visible_words={words} (> {en_word_limit} words for doc_type={doc_type})",
                    "message": "Wall of text detected. Split into shorter paragraphs, bullets, or add subheadings.",
                })
        else:
            compact = re.sub(r"\s+", "", vis_text)
            if len(compact) > ja_limit:
                findings.append({
                    "severity": "Major",
                    "rule_id": "CHK-D2",
                    "target": f"Paragraph starting at line {start_ln}",
                    "evidence": f"visible_length={len(compact)} chars (> {ja_limit} chars for doc_type={doc_type}, URLs excluded)",
                    "message": "Wall of text detected. Split into shorter paragraphs, bullets, or add subheadings.",
                })
        para_lines = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Code fences: ``` or ~~~
        fm = re.match(r"^(`{3,}|~{3,})", stripped)
        if fm:
            flush_paragraph()
            fence_char = fm.group(1)[0]
            if in_fence_char is None:
                in_fence_char = fence_char
            elif in_fence_char == fence_char:
                in_fence_char = None
            continue
        if in_fence_char is not None:
            continue

        # Horizontal rule (***, ---, ___) -> not bold+italic
        if re.match(r"^(?:\*\s*){3,}$|^(?:-\s*){3,}$|^(?:_\s*){3,}$", stripped):
            flush_paragraph()
            continue

        # Headings
        hm = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if hm:
            flush_paragraph()
            lvl = len(hm.group(1))
            if not seen_heading and lvl >= 3:
                findings.append({
                    "severity": "Blocker",
                    "rule_id": "BLK-07",
                    "target": f"Heading at line {idx}",
                    "evidence": f"First heading starts at H{lvl}: '{hm.group(2)}'",
                    "message": "Markdown heading hierarchy starts too deep.",
                })
            elif prev_heading > 0 and lvl > prev_heading + 1:
                findings.append({
                    "severity": "Blocker",
                    "rule_id": "BLK-07",
                    "target": f"Heading at line {idx}",
                    "evidence": f"Jumped from H{prev_heading} to H{lvl}: '{hm.group(2)}'",
                    "message": "Markdown heading hierarchy skipped a level.",
                })
            prev_heading = lvl
            seen_heading = True
            continue

        if not stripped or stripped.startswith(("-", "*", ">", "|", "<!--")) or re.match(r"^\d+\.\s", stripped):
            flush_paragraph()
        else:
            para_lines.append((idx, stripped))

        # Ignore inline code spans when checking link text & decorative overuse
        line_no_code = strip_inline_code(line)

        for lm in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", line_no_code):
            ltxt = lm.group(1).strip()
            if ltxt.lower() in GENERIC_LINK_EXACT:
                findings.append({
                    "severity": "Major",
                    "rule_id": "CHK-D3",
                    "target": f"Link at line {idx}",
                    "evidence": f"[{ltxt}]({lm.group(2)})",
                    "message": "Generic link text reduces scannability. Use self-contained descriptive link text.",
                })

        if re.search(r"\*\*\*[^*]+\*\*\*", line_no_code) or "<u>" in line_no_code.lower():
            findings.append({
                "severity": "Minor",
                "rule_id": "CHK-D4",
                "target": f"Line {idx}",
                "evidence": stripped[:80],
                "message": "Use bold alone for key phrases and reserve underline for hyperlinks.",
            })

    flush_paragraph()

    return {
        "file": str(path),
        "type": "markdown",
        "doc_type": doc_type,
        "blocker_count": sum(1 for f in findings if f["severity"] == "Blocker"),
        "major_count": sum(1 for f in findings if f["severity"] == "Major"),
        "minor_count": sum(1 for f in findings if f["severity"] == "Minor"),
        "coverage": {"color_pairs_found": 0, "evaluated": 0, "skipped": []},
        "findings": findings,
        "unverified_notes": [
            "UNV-D1: Rendered line wrapping and table overflow depend on target viewer.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="UI/UX Mechanical Checker v1.2")
    ap.add_argument("target", nargs="?", help="Path to HTML, CSS, or Markdown file")
    ap.add_argument("--check-tokens", help="Path to design-tokens.json to verify color pairs")
    ap.add_argument("--strict-tokens", action="store_true", help="Enable CHK-W6 check for raw hex colors outside :root")
    ap.add_argument("--doc-type", choices=("general", "spec"), default="general", help="Markdown wall-of-text threshold preset")
    ap.add_argument("--json", action="store_true", help="Output JSON format")
    args = ap.parse_args()

    if args.check_tokens:
        result = check_tokens_file(Path(args.check_tokens))
    elif args.target:
        p = Path(args.target)
        if not p.exists():
            print(f"Error: File not found: {p}", file=sys.stderr)
            return 2
        ext = p.suffix.lower()
        if ext in (".html", ".htm"):
            result = check_html_file(p, strict_tokens=args.strict_tokens)
        elif ext == ".css":
            result = check_css_file(p, strict_tokens=args.strict_tokens)
        elif ext in (".md", ".markdown"):
            result = check_markdown_file(p, doc_type=args.doc_type)
        else:
            print(f"Error: Unsupported file extension: {p.suffix}", file=sys.stderr)
            return 2
    else:
        ap.print_help()
        return 2

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        cov = result.get("coverage", {})
        print(f"=== UI/UX Check Report: {result['file']} ===")
        print(
            f"Blockers: {result.get('blocker_count', 0)} | "
            f"Majors: {result.get('major_count', 0)} | "
            f"Minors: {result.get('minor_count', 0)} | "
            f"Color pairs evaluated: {cov.get('evaluated', 0)}/{cov.get('color_pairs_found', 0)} "
            f"(skipped: {len(cov.get('skipped', []))})"
        )
        for f in result["findings"]:
            print(f"  [{f['severity']}] {f['rule_id']} @ {f['target']}")
            print(f"    Evidence: {f['evidence']}")
            print(f"    Message : {f['message']}")
        if not result["findings"]:
            print("  No mechanical defects detected within checked scope.")
        for note in result.get("unverified_notes", []):
            print(f"  [Unverified] {note}")

    return 1 if result.get("blocker_count", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
