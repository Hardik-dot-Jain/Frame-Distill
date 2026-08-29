#!/usr/bin/env python3
"""
Frame-Distill Report Module - Report Generator
Role 3: Isolated report generator that reads distilled video frame JSON data
and renders an interactive, presentation-ready HTML report.
"""

import argparse
import json
import os
import sys
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False

MODULE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = MODULE_DIR / "templates"
STATIC_DIR = MODULE_DIR / "static"
DEFAULT_INPUT = MODULE_DIR / "mock_data" / "fake_frames.json"
DEFAULT_OUTPUT = MODULE_DIR / "output" / "report.html"


def load_frame_data(json_path: Path) -> dict:
    """Load and validate JSON frame distillation data."""
    if not json_path.exists():
        raise FileNotFoundError(f"Input frame data not found: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)


def render_report(data: dict, output_path: Path, inline_assets: bool = False) -> Path:
    """Render report.html using Jinja2 template and write to output_path."""
    if not HAS_JINJA2:
        print("[WARNING] Jinja2 is not installed. Run 'pip install jinja2' to enable full template rendering.", file=sys.stderr)
        raise ImportError("Jinja2 package is required. Install it using: pip install jinja2")

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        autoescape=True
    )
    template = env.get_template("report.html")

    css_content = ""
    js_content = ""
    if inline_assets:
        css_file = STATIC_DIR / "css" / "style.css"
        js_file = STATIC_DIR / "js" / "script.js"
        if css_file.exists():
            css_content = css_file.read_text(encoding="utf-8")
        if js_file.exists():
            js_content = js_file.read_text(encoding="utf-8")

    html_out = template.render(
        data=data,
        inline_assets=inline_assets,
        css_content=css_content,
        js_content=js_content
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    return output_path


def main():
    parser = argparse.ArgumentParser(description="Frame-Distill HTML Report Generator (Role 3)")
    parser.add_argument(
        "--input", "-i",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to frame JSON data (default: mock_data/fake_frames.json)"
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Destination path for generated report.html (default: output/report.html)"
    )
    parser.add_argument(
        "--inline",
        action="store_true",
        help="Inline CSS and JS directly into the output HTML file for a single-file portable report"
    )

    args = parser.parse_args()

    print(f"[*] Loading data from: {args.input}")
    data = load_frame_data(args.input)

    print(f"[*] Rendering HTML report...")
    out_file = render_report(data, args.output, inline_assets=args.inline)
    print(f"[OK] Report generated successfully: {out_file.resolve()}")


if __name__ == "__main__":
    main()
