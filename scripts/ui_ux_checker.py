#!/usr/bin/env python3
"""
UI/UX Mechanical Checker v1.3 (Zero-dependency Python 3.9+ stdlib; optional Pillow for JPEG/PNG)
Evaluates HTML, CSS, Markdown, Design Token JSON, and JPEG/PNG UI image files deterministically.
"""

import argparse
import colorsys
import json
import math
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from PIL import Image  # type: ignore
except ImportError:
    Image = None

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
    for m in re.finditer(r"rgba?\([^)]+\)|hsla?\([^)]+\)|#[0-9a-fA-F]{3,8}\b|\b[a-zA-Z]+\b", resolved):
        tok = m.group(0)
        if parse_rgba(tok, css_vars) is not None and tok.lower() != "transparent":
            return tok
    return None


def composite_over(fg: RGBA, bg: RGBA) -> Tuple[int, int, int]:
    a = fg[3]
    return (
        round(fg[0] * a + bg[0] * (1.0 - a)),
        round(fg[1] * a + bg[1] * (1.0 - a)),
        round(fg[2] * a + bg[2] * (1.0 - a)),
    )


def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio_rgb(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    return round((max(l1, l2) + 0.05) / (min(l1, l2) + 0.05), 2)


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#{:02X}{:02X}{:02X}".format(rgb[0], rgb[1], rgb[2])


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
    return contrast_ratio_rgb(fg_rgb, (bg[0], bg[1], bg[2])), None


def check_tokens_file(token_path: Path) -> Dict[str, Any]:
    data = json.loads(token_path.read_text(encoding="utf-8"))
    findings = []
    colors = data.get("colors", {})
    pairs = colors.get("verified_pairs", [])
    evaluated = 0
    for pair in pairs:
        theme = pair["theme"]
        fg_val = colors.get(theme, {}).get(pair["fg"])
        bg_val = colors.get(theme, {}).get(pair["bg"])
        ratio, err = contrast_ratio(fg_val or "", bg_val or "")
        if ratio is not None:
            evaluated += 1
        if ratio is None or ratio < pair["min_ratio"]:
            findings.append({
                "severity": "Blocker",
                "rule_id": "BLK-03",
                "target": f"tokens:{theme}:{pair['fg']} on {pair['bg']}",
                "evidence": f"fg={fg_val}, bg={bg_val}, ratio={ratio} (required >= {pair['min_ratio']}; {err or 'below threshold'})",
                "message": "Design token pair fails WCAG 2.2 AA contrast requirement.",
            })
    return {
        "file": str(token_path),
        "type": "design-tokens",
        "blocker_count": len(findings),
        "major_count": 0,
        "minor_count": 0,
        "coverage": {"color_pairs_found": len(pairs), "evaluated": evaluated, "skipped": []},
        "findings": findings,
    }


def strip_css_comments(css: str) -> str:
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
    cleaned = strip_css_comments(css)
    theme_vars: Dict[str, Dict[str, str]] = {"default": {}}
    rules: List[Dict[str, Any]] = []
    i, n = 0, len(cleaned)
    current_media: Optional[str] = None
    while i < n:
        while i < n and cleaned[i].isspace():
            i += 1
        if i >= n:
            break
        if cleaned[i] == "}":
            current_media = None
            i += 1
            continue
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
        i += 1
        if selector.startswith("@media"):
            current_media = selector.lower()
            continue
        if selector.startswith("@"):
            depth = 1
            while i < n and depth > 0:
                if cleaned[i] == "{":
                    depth += 1
                elif cleaned[i] == "}":
                    depth -= 1
                i += 1
            continue
        body_start = i
        depth = 1
        while i < n and depth > 0:
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
            i += 1
        props = parse_declarations(cleaned[body_start : i - 1])
        is_dark = (current_media is not None and "prefers-color-scheme" in current_media and "dark" in current_media) or (
            'data-theme="dark"' in selector or "data-theme='dark'" in selector
        )
        scope = "dark" if is_dark else "default"
        for k, v in props.items():
            if k.startswith("--"):
                theme_vars.setdefault(scope, {})[k] = clean_css_val(v)
        rules.append({"selector": selector, "line": line_no, "props": props, "scope": scope, "media": current_media})
    return theme_vars, rules


INTERACTIVE_SEL_RE = re.compile(
    r"(?:^|[\s>+~,])(?:button|input|a)(?:$|[\s>+~,:.[#])|\.(?:btn|icon-btn|button)(?:$|[\s>+~,:.[#])",
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
) -> None:
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
                coverage["skipped"].append({"target": f"{target} [theme:{th}]", "reason": err or "unparseable color pair"})
                continue
            coverage["evaluated"] += 1
            font_size = parse_px(props.get("font-size", ""), merged_vars)
            is_bold = clean_css_val(props.get("font-weight", "")).lower() in ("bold", "700", "800", "900")
            is_large = (font_size is not None and font_size >= 24) or (font_size is not None and font_size >= 18.66 and is_bold)
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
        coverage["skipped"].append({"target": target, "reason": "color specified without background in same rule"})

    outline_val = clean_css_val(props.get("outline", "")).lower()
    if outline_val in ("none", "0", "0px") and ":focus" in selector.lower() and ":not(:focus-visible)" not in selector.lower():
        if not has_visible_focus_fallback(props):
            findings.append({
                "severity": "Blocker",
                "rule_id": "BLK-05",
                "target": target,
                "evidence": f"outline: {props.get('outline')} without visible replacement",
                "message": "Removing focus outline without a visible replacement breaks keyboard accessibility.",
            })

    if tag in ("button", "a", "input") or bool(INTERACTIVE_SEL_RE.search(selector)):
        default_vars = theme_vars.get("default", {})
        dims = {k: parse_px(props.get(k, ""), default_vars) for k in ("width", "height", "min-width", "min-height")}
        too_small = [f"{k}={props.get(k)}" for k, v in dims.items() if v is not None and v < 24]
        if too_small:
            findings.append({
                "severity": "Major",
                "rule_id": "CHK-W2",
                "target": target,
                "evidence": f"{', '.join(too_small)} (WCAG 2.2 AA min 24x24px)",
                "message": "Interactive target size is smaller than 24x24px.",
            })

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
    theme_vars, rules = extract_css_rules_with_scopes(path.read_text(encoding="utf-8"), base_line=1)
    findings: List[Dict[str, Any]] = []
    coverage: Dict[str, Any] = {"color_pairs_found": 0, "evaluated": 0, "skipped": []}
    for r in rules:
        inspect_style_props(
            findings, coverage,
            target=f"{path.name} '{r['selector']}' (line {r['line']})",
            props=r["props"], theme_vars=theme_vars, rule_scope=r["scope"],
            selector=r["selector"], strict_tokens=strict_tokens,
        )
    return {
        "file": str(path), "type": "css",
        "blocker_count": sum(1 for f in findings if f["severity"] == "Blocker"),
        "major_count": sum(1 for f in findings if f["severity"] == "Major"),
        "minor_count": sum(1 for f in findings if f["severity"] == "Minor"),
        "coverage": coverage, "findings": findings,
        "unverified_notes": ["UNV-W1: Visual hierarchy, inherited backgrounds & layout overlap require rendered viewport inspection."],
    }


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
        if tag == "link" and attr_map.get("rel", "").lower() == "stylesheet" and attr_map.get("href"):
            self.external_css_hrefs.append((line, attr_map["href"]))
        if tag == "img":
            if "alt" not in attr_map:
                self.findings.append({
                    "severity": "Blocker", "rule_id": "BLK-05", "target": f"<img> at line {line}",
                    "evidence": f"src='{attr_map.get('src', '')}' has no alt attribute",
                    "message": "Missing alt attribute on <img>.",
                })
            if self.current_link is not None and attr_map.get("alt", "").strip():
                self.current_link["has_alt"] = True
        if tag in ("div", "span") and "onclick" in attr_map:
            role = attr_map.get("role", "")
            tabindex = attr_map.get("tabindex", "")
            has_key = any(k in attr_map for k in ("onkeydown", "onkeyup", "onkeypress"))
            if role not in ("button", "link") or not tabindex or not has_key:
                self.findings.append({
                    "severity": "Blocker", "rule_id": "BLK-05", "target": f"<{tag} onclick=...> at line {line}",
                    "evidence": f"role='{role}', tabindex='{tabindex}', key_handler={has_key}",
                    "message": "Clickable non-semantic element lacks full keyboard support.",
                })
        if tag == "label":
            self.in_label = True
            if attr_map.get("for"):
                self.labels_for.add(attr_map["for"])
        if tag in ("input", "textarea", "select"):
            if attr_map.get("type", "text").lower() not in ("hidden", "submit", "button", "reset"):
                attr_map["_inside_label"] = "yes" if self.in_label else "no"
                self.inputs.append((line, attr_map))
        if tag == "a":
            self.current_link = {
                "line": line, "text": [], "has_alt": False, "href": attr_map.get("href"),
                "aria_label": attr_map.get("aria-label", "").strip() or attr_map.get("aria-labelledby", "").strip(),
            }
        if tag == "style":
            self.in_style = True
        if attr_map.get("style"):
            self.inline_styles.append((line, tag, parse_declarations(attr_map["style"])))

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
                        "severity": "Blocker", "rule_id": "BLK-05", "target": f"<a> at line {ln}",
                        "evidence": "Link has no visible text, non-empty img alt, or aria-label",
                        "message": "Link lacks an accessible name.",
                    })
                elif txt.lower() in GENERIC_LINK_EXACT:
                    self.findings.append({
                        "severity": "Major", "rule_id": "CHK-W5", "target": f"<a> at line {ln}",
                        "evidence": f"link text='{txt}'",
                        "message": "Generic link text fails scannability and accessibility.",
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
        for ln, href in self.external_css_hrefs:
            if href.startswith(("http://", "https://", "//")):
                self.coverage["skipped"].append({"target": f"<link href='{href}'> at line {ln}", "reason": "remote stylesheet skipped"})
                continue
            css_path = (self.base_dir / href).resolve()
            if css_path.exists() and css_path.is_file():
                tv, rules = extract_css_rules_with_scopes(css_path.read_text(encoding="utf-8"), base_line=1)
                for sc, mp in tv.items():
                    theme_vars.setdefault(sc, {}).update(mp)
                all_css_sources.append((css_path.name, rules))
            else:
                self.coverage["skipped"].append({"target": f"<link href='{href}'> at line {ln}", "reason": "local stylesheet not found"})
        for base_line, css in self.style_blocks:
            tv, rules = extract_css_rules_with_scopes(css, base_line=base_line)
            for sc, mp in tv.items():
                theme_vars.setdefault(sc, {}).update(mp)
            all_css_sources.append(("<style>", rules))
        for ln, tag, props in self.inline_styles:
            inspect_style_props(self.findings, self.coverage, f"<{tag}> at line {ln}", props, theme_vars, tag=tag, strict_tokens=self.strict_tokens)
        for src_name, rlist in all_css_sources:
            for r in rlist:
                inspect_style_props(
                    self.findings, self.coverage, f"{src_name} '{r['selector']}' (line {r['line']})",
                    r["props"], theme_vars, rule_scope=r["scope"], selector=r["selector"], strict_tokens=self.strict_tokens,
                )
        prev_level = 0
        for idx_h, (lvl, ln, text) in enumerate(self.headings):
            if idx_h == 0 and lvl >= 3:
                self.findings.append({
                    "severity": "Blocker", "rule_id": "BLK-07", "target": f"<h{lvl}> at line {ln}",
                    "evidence": f"First heading starts at <h{lvl}> ('{text}')",
                    "message": "Document heading hierarchy starts too deep.",
                })
            elif prev_level > 0 and lvl > prev_level + 1:
                self.findings.append({
                    "severity": "Blocker", "rule_id": "BLK-07", "target": f"<h{lvl}> at line {ln}",
                    "evidence": f"Jumped from <h{prev_level}> to <h{lvl}> ('{text}')",
                    "message": "Heading hierarchy skipped a level.",
                })
            prev_level = lvl
        for ln, attrs in self.inputs:
            iid = attrs.get("id", "")
            has_label = attrs.get("_inside_label") == "yes" or (iid and iid in self.labels_for) or bool(attrs.get("aria-label")) or bool(attrs.get("aria-labelledby"))
            if not has_label:
                self.findings.append({
                    "severity": "Blocker", "rule_id": "BLK-04", "target": f"form control at line {ln}",
                    "evidence": f"id='{iid}', placeholder='{attrs.get('placeholder', '')}', no associated <label>",
                    "message": "Form input lacks an accessible label.",
                })


def check_html_file(path: Path, strict_tokens: bool = False) -> Dict[str, Any]:
    parser = UIHTMLChecker(base_dir=path.parent, strict_tokens=strict_tokens)
    parser.feed(path.read_text(encoding="utf-8"))
    parser.finalize()
    return {
        "file": str(path), "type": "html",
        "blocker_count": sum(1 for f in parser.findings if f["severity"] == "Blocker"),
        "major_count": sum(1 for f in parser.findings if f["severity"] == "Major"),
        "minor_count": sum(1 for f in parser.findings if f["severity"] == "Minor"),
        "coverage": parser.coverage, "findings": parser.findings,
        "unverified_notes": [
            "UNV-W1: Visual hierarchy, inherited backgrounds & layout overlap require rendered viewport inspection.",
            "UNV-W2: Perceived performance (100ms / 1s thresholds) requires runtime measurement.",
        ],
    }


def strip_inline_code(line: str) -> str:
    return re.sub(r"`[^`]+`", "", line)


def visible_markdown_text(text: str) -> str:
    t = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    t = re.sub(r"https?://\S+", "", t)
    return t.strip()


def is_mostly_english(text: str) -> bool:
    return bool(text) and (sum(1 for c in text if ord(c) < 128) / len(text)) > 0.75


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
        vis_text = visible_markdown_text(" ".join(t for _, t in para_lines).strip())
        if is_mostly_english(vis_text):
            words = len(vis_text.split())
            if words > en_word_limit:
                findings.append({
                    "severity": "Major", "rule_id": "CHK-D2", "target": f"Paragraph starting at line {start_ln}",
                    "evidence": f"visible_words={words} (> {en_word_limit} words)", "message": "Wall of text detected.",
                })
        else:
            compact = re.sub(r"\s+", "", vis_text)
            if len(compact) > ja_limit:
                findings.append({
                    "severity": "Major", "rule_id": "CHK-D2", "target": f"Paragraph starting at line {start_ln}",
                    "evidence": f"visible_length={len(compact)} chars (> {ja_limit} chars)", "message": "Wall of text detected.",
                })
        para_lines = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        fm = re.match(r"^(`{3,}|~{3,})", stripped)
        if fm:
            flush_paragraph()
            fc = fm.group(1)[0]
            in_fence_char = None if in_fence_char == fc else (fc if in_fence_char is None else in_fence_char)
            continue
        if in_fence_char is not None:
            continue
        if re.match(r"^(?:\*\s*){3,}$|^(?:-\s*){3,}$|^(?:_\s*){3,}$", stripped):
            flush_paragraph()
            continue
        hm = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if hm:
            flush_paragraph()
            lvl = len(hm.group(1))
            if not seen_heading and lvl >= 3:
                findings.append({
                    "severity": "Blocker", "rule_id": "BLK-07", "target": f"Heading at line {idx}",
                    "evidence": f"First heading starts at H{lvl}: '{hm.group(2)}'", "message": "Heading hierarchy starts too deep.",
                })
            elif prev_heading > 0 and lvl > prev_heading + 1:
                findings.append({
                    "severity": "Blocker", "rule_id": "BLK-07", "target": f"Heading at line {idx}",
                    "evidence": f"Jumped from H{prev_heading} to H{lvl}: '{hm.group(2)}'", "message": "Heading hierarchy skipped a level.",
                })
            prev_heading = lvl
            seen_heading = True
            continue
        if not stripped or stripped.startswith(("-", "*", ">", "|", "<!--")) or re.match(r"^\d+\.\s", stripped):
            flush_paragraph()
        else:
            para_lines.append((idx, stripped))
        line_no_code = strip_inline_code(line)
        for lm in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", line_no_code):
            if lm.group(1).strip().lower() in GENERIC_LINK_EXACT:
                findings.append({
                    "severity": "Major", "rule_id": "CHK-D3", "target": f"Link at line {idx}",
                    "evidence": f"[{lm.group(1).strip()}]({lm.group(2)})", "message": "Generic link text reduces scannability.",
                })
        if re.search(r"\*\*\*[^*]+\*\*\*", line_no_code) or "<u>" in line_no_code.lower():
            findings.append({
                "severity": "Minor", "rule_id": "CHK-D4", "target": f"Line {idx}",
                "evidence": stripped[:80], "message": "Use bold alone for key phrases and reserve underline for hyperlinks.",
            })
    flush_paragraph()
    return {
        "file": str(path), "type": "markdown", "doc_type": doc_type,
        "blocker_count": sum(1 for f in findings if f["severity"] == "Blocker"),
        "major_count": sum(1 for f in findings if f["severity"] == "Major"),
        "minor_count": sum(1 for f in findings if f["severity"] == "Minor"),
        "coverage": {"color_pairs_found": 0, "evaluated": 0, "skipped": []},
        "findings": findings,
        "unverified_notes": ["UNV-D1: Rendered line wrapping and table overflow depend on target viewer."],
    }


def sample_patch_rgb(img: Any, x: int, y: int, radius: int = 1) -> Tuple[int, int, int]:
    w, h = img.size
    rs, gs, bs = [], [], []
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            r, g, b = img.getpixel((min(max(x + dx, 0), w - 1), min(max(y + dy, 0), h - 1)))[:3]
            rs.append(r); gs.append(g); bs.append(b)
    rs.sort(); gs.sort(); bs.sort()
    mid = len(rs) // 2
    return (rs[mid], gs[mid], bs[mid])


def parse_sample_pair_spec(spec: str) -> Tuple[Tuple[int, int], Tuple[int, int], str, float]:
    parts = spec.split(":")
    if len(parts) < 2:
        raise ValueError(f"Invalid --sample-pair spec: {spec}")
    fg_xy = tuple(int(v.strip()) for v in parts[0].split(","))
    bg_xy = tuple(int(v.strip()) for v in parts[1].split(","))
    label = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else f"({fg_xy[0]},{fg_xy[1]}) vs ({bg_xy[0]},{bg_xy[1]})"
    threshold = float(parts[3].strip()) if len(parts) >= 4 and parts[3].strip() else 4.5
    return (fg_xy[0], fg_xy[1]), (bg_xy[0], bg_xy[1]), label, threshold


def parse_contrast_box_spec(spec: str) -> Tuple[Tuple[int, int, int, int], str, float]:
    parts = spec.split(":")
    coords = tuple(int(v.strip()) for v in parts[0].split(","))
    if len(coords) != 4:
        raise ValueError(f"Invalid --contrast-box spec: {spec}")
    label = parts[1].strip() if len(parts) >= 2 and parts[1].strip() else f"box({coords[0]},{coords[1]},{coords[2]},{coords[3]})"
    threshold = float(parts[2].strip()) if len(parts) >= 3 and parts[2].strip() else 4.5
    return (coords[0], coords[1], coords[2], coords[3]), label, threshold


def check_image_file(
    path: Path,
    sample_pairs: Optional[List[str]] = None,
    contrast_boxes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    unverified = [
        "UNV-I1: Semantic HTML, heading hierarchy, form labels, alt attributes & screen reader order cannot be verified from a static image.",
        "UNV-I2: Keyboard focus, modal focus trap, input preservation & dynamic UI states require code or interactive testing.",
        "UNV-I3: Physical touch target size (24x24px / 44x44px) and runtime latency require real-device verification.",
    ]
    if Image is None:
        return {
            "file": str(path), "type": "image",
            "blocker_count": 0, "major_count": 0, "minor_count": 0, "metrics": {},
            "coverage": {"color_pairs_found": 0, "evaluated": 0, "skipped": [{"target": path.name, "reason": "Pillow (PIL) not installed"}]},
            "findings": [], "unverified_notes": ["CHK-I1/I2/I3 skipped because Pillow (PIL) is unavailable.", *unverified],
        }
    findings: List[Dict[str, Any]] = []
    coverage: Dict[str, Any] = {"color_pairs_found": 0, "evaluated": 0, "skipped": []}
    with Image.open(path) as raw_img:
        img = raw_img.convert("RGB")
        w, h = img.size
        aspect = round(w / h, 3) if h else 0.0
        if w < 320 or h < 320:
            findings.append({
                "severity": "Major", "rule_id": "CHK-I1", "target": path.name,
                "evidence": f"resolution={w}x{h} (< 320px)", "message": "Image resolution is too low for UI inspection.",
            })
        thumb = img.copy()
        thumb.thumbnail((200, 200))
        quant = thumb.quantize(colors=8)
        palette_raw = quant.getpalette() or []
        color_counts = sorted(quant.getcolors() or [], key=lambda item: item[0], reverse=True)
        total_px = sum(c for c, _ in color_counts) or 1
        dominant_colors: List[Dict[str, Any]] = []
        bg_rgb: Tuple[int, int, int] = (255, 255, 255)
        for idx_c, (cnt, pal_idx) in enumerate(color_counts[:5]):
            rgb = (palette_raw[pal_idx * 3], palette_raw[pal_idx * 3 + 1], palette_raw[pal_idx * 3 + 2])
            if idx_c == 0:
                bg_rgb = rgb
            dominant_colors.append({"hex": rgb_to_hex(rgb), "ratio_pct": round((cnt / total_px) * 100.0, 1)})
        thumb_pixels = list(thumb.getdata())
        bg_like = sum(
            1 for r, g, b in thumb_pixels
            if math.sqrt((r - bg_rgb[0]) ** 2 + (g - bg_rgb[1]) ** 2 + (b - bg_rgb[2]) ** 2) <= 18.0
        )
        est_bg_ratio = round((bg_like / max(1, len(thumb_pixels))) * 100.0, 1)
        measured_pairs: List[Dict[str, Any]] = []
        for spec in (sample_pairs or []):
            coverage["color_pairs_found"] += 1
            try:
                fg_xy, bg_xy, label, threshold = parse_sample_pair_spec(spec)
                fg_rgb = sample_patch_rgb(img, fg_xy[0], fg_xy[1], radius=1)
                bg_rgb_s = sample_patch_rgb(img, bg_xy[0], bg_xy[1], radius=1)
                ratio = contrast_ratio_rgb(fg_rgb, bg_rgb_s)
                coverage["evaluated"] += 1
                measured_pairs.append({"label": label, "fg": rgb_to_hex(fg_rgb), "bg": rgb_to_hex(bg_rgb_s), "contrast": ratio, "threshold": threshold})
                if ratio < threshold:
                    findings.append({
                        "severity": "Blocker", "rule_id": "BLK-03", "target": f"{path.name} [{label}]",
                        "evidence": f"fg={rgb_to_hex(fg_rgb)}@{fg_xy}, bg={rgb_to_hex(bg_rgb_s)}@{bg_xy}, contrast={ratio}:1 (required >= {threshold}:1)",
                        "message": "Measured image contrast ratio is below WCAG 2.2 AA threshold.",
                    })
            except Exception as exc:
                coverage["skipped"].append({"target": spec, "reason": str(exc)})
        for spec in (contrast_boxes or []):
            coverage["color_pairs_found"] += 1
            try:
                (x1, y1, x2, y2), label, threshold = parse_contrast_box_spec(spec)
                box = (max(0, x1), max(0, y1), min(w, x2), min(h, y2))
                crop = img.crop(box)
                q_crop = crop.quantize(colors=6)
                p_raw = q_crop.getpalette() or []
                c_counts = sorted(q_crop.getcolors() or [], key=lambda item: item[0], reverse=True)
                if len(c_counts) < 2:
                    coverage["skipped"].append({"target": label, "reason": "single uniform color in box"})
                    continue
                bg_idx = c_counts[0][1]
                box_bg = (p_raw[bg_idx * 3], p_raw[bg_idx * 3 + 1], p_raw[bg_idx * 3 + 2])
                best_fg, best_ratio = box_bg, 1.0
                for _, pidx in c_counts[1:]:
                    cand = (p_raw[pidx * 3], p_raw[pidx * 3 + 1], p_raw[pidx * 3 + 2])
                    r = contrast_ratio_rgb(cand, box_bg)
                    if r > best_ratio:
                        best_ratio, best_fg = r, cand
                coverage["evaluated"] += 1
                measured_pairs.append({"label": label, "fg": rgb_to_hex(best_fg), "bg": rgb_to_hex(box_bg), "contrast": best_ratio, "threshold": threshold})
                if best_ratio < threshold:
                    findings.append({
                        "severity": "Blocker", "rule_id": "BLK-03", "target": f"{path.name} [{label}]",
                        "evidence": f"box={box}, fg={rgb_to_hex(best_fg)}, bg={rgb_to_hex(box_bg)}, contrast={best_ratio}:1 (required >= {threshold}:1)",
                        "message": "Measured region contrast ratio is below WCAG 2.2 AA threshold.",
                    })
            except Exception as exc:
                coverage["skipped"].append({"target": spec, "reason": str(exc)})
        if not sample_pairs and not contrast_boxes:
            coverage["skipped"].append({"target": path.name, "reason": "No --sample-pair or --contrast-box provided"})
    return {
        "file": str(path), "type": "image",
        "blocker_count": sum(1 for f in findings if f["severity"] == "Blocker"),
        "major_count": sum(1 for f in findings if f["severity"] == "Major"),
        "minor_count": sum(1 for f in findings if f["severity"] == "Minor"),
        "metrics": {
            "width": w, "height": h, "aspect_ratio": aspect,
            "estimated_background_ratio_pct": est_bg_ratio,
            "dominant_colors": dominant_colors, "measured_pairs": measured_pairs,
        },
        "coverage": coverage, "findings": findings, "unverified_notes": unverified,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="UI/UX Mechanical Checker v1.3")
    ap.add_argument("target", nargs="?", help="Path to HTML, CSS, Markdown, or JPEG/PNG image file")
    ap.add_argument("--check-tokens", help="Path to design-tokens.json")
    ap.add_argument("--strict-tokens", action="store_true")
    ap.add_argument("--doc-type", choices=("general", "spec"), default="general")
    ap.add_argument("--sample-pair", action="append", default=[])
    ap.add_argument("--contrast-box", action="append", default=[])
    ap.add_argument("--json", action="store_true")
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
        elif ext in (".jpg", ".jpeg", ".png"):
            result = check_image_file(p, sample_pairs=args.sample_pair, contrast_boxes=args.contrast_box)
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
        print(f"Blockers: {result.get('blocker_count', 0)} | Majors: {result.get('major_count', 0)} | Minors: {result.get('minor_count', 0)} | Pairs: {cov.get('evaluated', 0)}/{cov.get('color_pairs_found', 0)}")
        for f in result["findings"]:
            print(f"  [{f['severity']}] {f['rule_id']} @ {f['target']}: {f['evidence']}")
    return 1 if result.get("blocker_count", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
