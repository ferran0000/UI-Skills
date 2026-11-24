#!/usr/bin/env python3
"""
UI/UX Mechanical Checker (Zero-dependency Python 3.9+ stdlib only)
Evaluates HTML, CSS, Markdown, and Design Token JSON files deterministically.
"""

import argparse
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
    "white": "#FFFFFF",
    "black": "#000000",
    "red": "#FF0000",
    "gray": "#808080",
    "grey": "#808080",
    "lightgray": "#D3D3D3",
    "lightgrey": "#D3D3D3",
    "silver": "#C0C0C0",
    "blue": "#0000FF",
    "green": "#008000",
    "yellow": "#FFFF00",
}


def parse_hex_color(color_str: str) -> Optional[Tuple[int, int, int]]:
    s = color_str.strip().lower()
    if s in NAMED_COLORS:
        s = NAMED_COLORS[s]
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3 and all(c in "0123456789abcdef" for c in h):
            return tuple(int(c * 2, 16) for c in h)
        if len(h) == 6 and all(c in "0123456789abcdef" for c in h):
            return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    m = re.match(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", s)
    if m:
        return (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return None


def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    def channel(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(c1: str, c2: str) -> Optional[float]:
    rgb1 = parse_hex_color(c1)
    rgb2 = parse_hex_color(c2)
    if not rgb1 or not rgb2:
        return None
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return round((lighter + 0.05) / (darker + 0.05), 2)


# -----------------------------
# Token Verification
# -----------------------------
def check_tokens_file(token_path: Path) -> Dict[str, Any]:
    data = json.loads(token_path.read_text(encoding="utf-8"))
    findings = []
    colors = data.get("colors", {})
    for pair in colors.get("verified_pairs", []):
        theme = pair["theme"]
        fg_key = pair["fg"]
        bg_key = pair["bg"]
        min_ratio = pair["min_ratio"]
        palette = colors.get(theme, {})
        fg_val = palette.get(fg_key)
        bg_val = palette.get(bg_key)
        ratio = contrast_ratio(fg_val, bg_val) if (fg_val and bg_val) else None
        if ratio is None or ratio < min_ratio:
            findings.append({
                "severity": "Blocker",
                "rule_id": "B-03",
                "target": f"tokens:{theme}:{fg_key} on {bg_key}",
                "evidence": f"fg={fg_val}, bg={bg_val}, ratio={ratio} (required >= {min_ratio})",
                "message": f"Design token pair fails WCAG 2.2 AA contrast requirement.",
            })
    return {
        "file": str(token_path),
        "type": "design-tokens",
        "blocker_count": sum(1 for f in findings if f["severity"] == "Blocker"),
        "findings": findings,
    }


# -----------------------------
# HTML / Inline CSS Checker
# -----------------------------
GENERIC_LINK_TEXTS = {
    "こちら", "ここ", "詳細", "詳しくはこちら", "もっと見る", "クリック", "リンク",
    "click here", "here", "more", "read more", "details", "link"
}


def parse_inline_style(style_str: str) -> Dict[str, str]:
    props = {}
    for decl in style_str.split(";"):
        if ":" in decl:
            k, v = decl.split(":", 1)
            props[k.strip().lower()] = v.strip()
    return props


def parse_px(val: str) -> Optional[float]:
    m = re.match(r"^(\d+(?:\.\d+)?)px$", val.strip().lower())
    return float(m.group(1)) if m else None


class UIHTMLChecker(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.findings: List[Dict[str, Any]] = []
        self.headings: List[Tuple[int, int, str]] = []
        self.labels_for: set = set()
        self.inputs: List[Tuple[int, Dict[str, str]]] = []
        self.in_label = False
        self.in_style = False
        self.style_blocks: List[Tuple[int, str]] = []
        self.current_link_text: Optional[List[str]] = None
        self.current_link_line: int = 0
        self.current_heading: Optional[Tuple[int, int, List[str]]] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        line = self.getpos()[0]
        attr_map = {k.lower(): (v or "") for k, v in attrs}

        # Heading tracking
        if re.match(r"^h[1-6]$", tag):
            level = int(tag[1])
            self.current_heading = (level, line, [])

        # Image alt check (B-05)
        if tag == "img" and "alt" not in attr_map:
            self.findings.append({
                "severity": "Blocker",
                "rule_id": "B-05",
                "target": f"<img> at line {line}",
                "evidence": f"src='{attr_map.get('src', '')}' has no alt attribute",
                "message": "Missing alt attribute on <img>. Use descriptive text or alt="" for decorative images.",
            })

        # Non-semantic clickable div/span (B-05)
        if tag in ("div", "span") and "onclick" in attr_map:
            role = attr_map.get("role", "")
            tabindex = attr_map.get("tabindex", "")
            if role not in ("button", "link") or not tabindex:
                self.findings.append({
                    "severity": "Blocker",
                    "rule_id": "B-05",
                    "target": f"<{tag} onclick=...> at line {line}",
                    "evidence": f"role='{role}', tabindex='{tabindex}'",
                    "message": "Clickable non-semantic element without keyboard accessibility. Use <button> or <a href>.",
                })

        # Label tracking
        if tag == "label":
            self.in_label = True
            if attr_map.get("for"):
                self.labels_for.add(attr_map["for"])

        # Form inputs (B-04)
        if tag in ("input", "textarea", "select"):
            itype = attr_map.get("type", "text").lower()
            if itype not in ("hidden", "submit", "button", "reset"):
                attr_map["_inside_label"] = "yes" if self.in_label else "no"
                self.inputs.append((line, attr_map))

        # Links (M-W5)
        if tag == "a":
            self.current_link_text = []
            self.current_link_line = line

        # Style tag
        if tag == "style":
            self.in_style = True

        # Inline style checks (contrast & target size)
        style_str = attr_map.get("style", "")
        if style_str:
            props = parse_inline_style(style_str)
            self._check_style_props(f"<{tag}> at line {line}", props, tag)

    def handle_endtag(self, tag: str) -> None:
        if tag == "label":
            self.in_label = False
        if tag == "style":
            self.in_style = False
        if tag == "a" and self.current_link_text is not None:
            txt = "".join(self.current_link_text).strip()
            if txt.lower() in GENERIC_LINK_TEXTS:
                self.findings.append({
                    "severity": "Major",
                    "rule_id": "M-W5",
                    "target": f"<a> at line {self.current_link_line}",
                    "evidence": f"link text='{txt}'",
                    "message": "Generic link text fails scannability and accessibility. Describe the destination.",
                })
            self.current_link_text = None
        if re.match(r"^h[1-6]$", tag) and self.current_heading is not None:
            lvl, ln, parts = self.current_heading
            self.headings.append((lvl, ln, "".join(parts).strip()))
            self.current_heading = None

    def handle_data(self, data: str) -> None:
        if self.in_style:
            self.style_blocks.append((self.getpos()[0], data))
        if self.current_link_text is not None:
            self.current_link_text.append(data)
        if self.current_heading is not None:
            self.current_heading[2].append(data)

    def _check_style_props(self, target: str, props: Dict[str, str], tag: str = "") -> None:
        fg = props.get("color")
        bg = props.get("background-color") or props.get("background")
        if fg and bg:
            # Handle simple color token in background shorthand
            bg_first = bg.split()[0]
            ratio = contrast_ratio(fg, bg_first)
            if ratio is not None:
                font_size = parse_px(props.get("font-size", ""))
                is_bold = props.get("font-weight", "") in ("bold", "600", "700", "800", "900")
                is_large = (font_size is not None and font_size >= 24) or (
                    font_size is not None and font_size >= 18.66 and is_bold
                )
                threshold = 3.0 if is_large else 4.5
                if ratio < threshold:
                    self.findings.append({
                        "severity": "Blocker",
                        "rule_id": "B-03",
                        "target": target,
                        "evidence": f"color={fg}, background={bg_first}, contrast={ratio}:1 (required >= {threshold}:1)",
                        "message": "Text contrast ratio is below WCAG 2.2 AA threshold.",
                    })

        # Focus outline suppression (B-05)
        if props.get("outline") in ("none", "0") and "box-shadow" not in props:
            self.findings.append({
                "severity": "Blocker",
                "rule_id": "B-05",
                "target": target,
                "evidence": f"outline: {props.get('outline')} without fallback focus indicator",
                "message": "Removing focus outline breaks keyboard accessibility.",
            })

        # Target size check for interactive tags (M-W2)
        if tag in ("button", "a", "input"):
            w = parse_px(props.get("width", ""))
            h = parse_px(props.get("height", ""))
            if (w is not None and w < 24) or (h is not None and h < 24):
                self.findings.append({
                    "severity": "Major",
                    "rule_id": "M-W2",
                    "target": target,
                    "evidence": f"width={props.get('width')}, height={props.get('height')} (WCAG 2.2 AA min 24x24px)",
                    "message": "Interactive target size is smaller than 24x24px.",
                })

    def finalize(self) -> None:
        # Check heading hierarchy skips (B-07)
        prev_level = 0
        for lvl, ln, text in self.headings:
            if prev_level > 0 and lvl > prev_level + 1:
                self.findings.append({
                    "severity": "Blocker",
                    "rule_id": "B-07",
                    "target": f"<h{lvl}> at line {ln}",
                    "evidence": f"Jumped from <h{prev_level}> to <h{lvl}> ('{text}')",
                    "message": "Heading hierarchy skipped a level.",
                })
            prev_level = lvl

        # Check form inputs without labels (B-04)
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
                    "rule_id": "B-04",
                    "target": f"form control at line {ln}",
                    "evidence": f"id='{iid}', placeholder='{placeholder}', no associated <label> or aria-label",
                    "message": "Form input lacks an accessible label (placeholder alone is insufficient).",
                })

        # Check embedded <style> blocks
        for base_line, css in self.style_blocks:
            for m in re.finditer(r"([^{]+)\{([^}]+)\}", css):
                selector = m.group(1).strip()
                body = m.group(2).strip()
                props = parse_inline_style(body)
                if ":focus" in selector and props.get("outline") in ("none", "0") and "box-shadow" not in props:
                    self.findings.append({
                        "severity": "Blocker",
                        "rule_id": "B-05",
                        "target": f"CSS selector '{selector}' (near line {base_line})",
                        "evidence": f"outline: {props.get('outline')} without box-shadow/border fallback",
                        "message": "Focus ring removed without visible replacement.",
                    })
                self._check_style_props(f"CSS selector '{selector}' (near line {base_line})", props)


def check_html_file(path: Path) -> Dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    parser = UIHTMLChecker()
    parser.feed(content)
    parser.finalize()
    return {
        "file": str(path),
        "type": "html",
        "blocker_count": sum(1 for f in parser.findings if f["severity"] == "Blocker"),
        "major_count": sum(1 for f in parser.findings if f["severity"] == "Major"),
        "findings": parser.findings,
        "unverified_notes": [
            "U-W1: Visual hierarchy & layout overlap require rendered viewport inspection.",
            "U-W2: Perceived performance (100ms / 1s thresholds) requires runtime measurement.",
        ],
    }


# -----------------------------
# Markdown Checker
# -----------------------------
def check_markdown_file(path: Path) -> Dict[str, Any]:
    lines = path.read_text(encoding="utf-8").splitlines()
    findings: List[Dict[str, Any]] = []
    in_code_block = False
    prev_heading = 0
    para_lines: List[Tuple[int, str]] = []

    def flush_paragraph() -> None:
        nonlocal para_lines
        if not para_lines:
            return
        start_ln = para_lines[0][0]
        full_text = "".join(t for _, t in para_lines).strip()
        # Wall of text threshold: > 400 chars in a single uninterrupted paragraph
        if len(full_text) > 400:
            findings.append({
                "severity": "Blocker",
                "rule_id": "B-07",
                "target": f"Paragraph starting at line {start_ln}",
                "evidence": f"length={len(full_text)} chars (> 400 chars uninterrupted)",
                "message": "Wall of text detected. Split into shorter paragraphs, bullets, or add subheadings.",
            })
        para_lines = []

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            flush_paragraph()
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # Headings
        hm = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if hm:
            flush_paragraph()
            lvl = len(hm.group(1))
            if prev_heading > 0 and lvl > prev_heading + 1:
                findings.append({
                    "severity": "Blocker",
                    "rule_id": "B-07",
                    "target": f"Heading at line {idx}",
                    "evidence": f"Jumped from H{prev_heading} to H{lvl}: '{hm.group(2)}'",
                    "message": "Markdown heading hierarchy skipped a level.",
                })
            prev_heading = lvl
            continue

        # Non-paragraph structural lines
        if not stripped or stripped.startswith(("-", "*", ">", "|")) or re.match(r"^\d+\.\s", stripped):
            flush_paragraph()
        else:
            para_lines.append((idx, stripped))

        # Generic link text (M-D3)
        for lm in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", line):
            ltxt = lm.group(1).strip()
            if ltxt.lower() in GENERIC_LINK_TEXTS:
                findings.append({
                    "severity": "Major",
                    "rule_id": "M-D3",
                    "target": f"Link at line {idx}",
                    "evidence": f"[{ltxt}]({lm.group(2)})",
                    "message": "Generic link text reduces scannability. Use descriptive link text.",
                })

        # Combined bold+italic or underline tag (M-D4)
        if "***" in line or "<u>" in line.lower():
            findings.append({
                "severity": "Minor",
                "rule_id": "M-D4",
                "target": f"Line {idx}",
                "evidence": stripped[:80],
                "message": "Avoid combining bold+italic (***) or using non-link underline (<u>).",
            })

    flush_paragraph()

    return {
        "file": str(path),
        "type": "markdown",
        "blocker_count": sum(1 for f in findings if f["severity"] == "Blocker"),
        "major_count": sum(1 for f in findings if f["severity"] == "Major"),
        "findings": findings,
        "unverified_notes": [
            "U-D1: Rendered line wrapping and table overflow depend on target viewer.",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="UI/UX Mechanical Checker")
    ap.add_argument("target", nargs="?", help="Path to HTML or Markdown file")
    ap.add_argument("--check-tokens", help="Path to design-tokens.json to verify color pairs")
    ap.add_argument("--json", action="store_true", help="Output JSON format")
    args = ap.parse_args()

    if args.check_tokens:
        result = check_tokens_file(Path(args.check_tokens))
    elif args.target:
        p = Path(args.target)
        if not p.exists():
            print(f"Error: File not found: {p}", file=sys.stderr)
            return 2
        if p.suffix.lower() in (".html", ".htm"):
            result = check_html_file(p)
        elif p.suffix.lower() in (".md", ".markdown"):
            result = check_markdown_file(p)
        else:
            print(f"Error: Unsupported file extension: {p.suffix}", file=sys.stderr)
            return 2
    else:
        ap.print_help()
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"=== UI/UX Check Report: {result['file']} ===")
        print(f"Blockers: {result.get('blocker_count', 0)} | Majors: {result.get('major_count', 0)}")
        for f in result["findings"]:
            print(f"  [{f['severity']}] {f['rule_id']} @ {f['target']}")
            print(f"    Evidence: {f['evidence']}")
            print(f"    Message : {f['message']}")
        if not result["findings"]:
            print("  No mechanical defects detected.")
        for note in result.get("unverified_notes", []):
            print(f"  [Unverified] {note}")

    return 1 if result.get("blocker_count", 0) > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
