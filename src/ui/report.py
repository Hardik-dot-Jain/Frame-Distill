"""
Frame-Distill · Role 3 · src/ui/report.py
==========================================
Public interface for the report generation module.

This module is imported by src/main.py (Role 2's orchestrator).
It is intentionally data-agnostic: it only accepts plain Python lists and dicts,
and never imports from src/core/database.py or src/core/storage.py.

────────────────────────────────────────────────────────────────
PUBLIC FUNCTION
────────────────────────────────────────────────────────────────

  generate_report(frames, stats, output_dir="data/output") -> str

  Parameters
  ----------
  frames : list[dict]
      One dict per distilled frame.  Exact keys (matching database.py schema):

        id               : int    – primary key / row number
        frame_filename   : str    – e.g. "frame_0042.png"
        timestamp_sec    : float  – position in the source video (seconds)
        laplacian_score  : float  – OpenCV Laplacian variance; higher = sharper
        ssim_score       : float  – SSIM similarity to previous frame (0.0–1.0)
        is_kept          : bool   – True if the frame survived quality filtering

  stats : dict
      Aggregate pipeline statistics.  Exact keys:

        total_frames_scanned   : int   – every frame extracted from the video
        frames_kept            : int   – frames that passed quality thresholds
        frames_discarded       : int   – frames filtered out (blurry / duplicate)
        original_folder_size_mb: float – total size of raw extracted frames (MB)
        output_folder_size_mb  : float – total size of kept frames on disk (MB)
        storage_saved_percent  : float – ((orig - out) / orig) * 100
        processing_time_seconds: float – wall-clock seconds for the full run

  output_dir : str, optional
      Directory where summary_report.html is written.
      Defaults to "data/output".  Created automatically if absent.

  Returns
  -------
  str
      Absolute path to the generated summary_report.html.

────────────────────────────────────────────────────────────────
STANDALONE / DEV MODE
────────────────────────────────────────────────────────────────

Run this file directly to render a report from mock data and open it
in the default browser:

  python src/ui/report.py

Mock data files consumed:
  data/dev_mock/mock_frames.json
  data/dev_mock/mock_summary_stats.json
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import webbrowser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

# ── Paths ──────────────────────────────────────────────────────────────────
# All paths are resolved relative to the project root (the directory that
# contains src/, templates/, data/, etc.), NOT relative to this file.
_HERE        = Path(__file__).resolve()          # …/src/ui/report.py
_PROJECT_ROOT = _HERE.parent.parent.parent        # …/Frame-Distill/
_TEMPLATES_DIR = _PROJECT_ROOT / "templates"
_TEMPLATE_NAME = "report_template.html"

# ── Jinja2 Environment ──────────────────────────────────────────────────────
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def generate_report(
    frames: list[dict],
    stats: dict,
    output_dir: str = "data/output",
) -> str:
    """Render the HTML summary report and write it to *output_dir*.

    See the module docstring for the complete description of expected
    dict shapes for *frames* and *stats*.

    Parameters
    ----------
    frames:
        List of frame-metadata dicts from the pipeline database.
    stats:
        Aggregate statistics dict produced by the pipeline.
    output_dir:
        Destination folder.  ``summary_report.html`` is written here.
        Resolved relative to the current working directory (project root).

    Returns
    -------
    str
        Absolute path of the generated ``summary_report.html``.

    Raises
    ------
    jinja2.TemplateNotFound
        If ``templates/report_template.html`` cannot be found.
    OSError
        If *output_dir* cannot be created or the file cannot be written.
    """
    template = _env.get_template(_TEMPLATE_NAME)

    generated_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html_content = template.render(
        frames=frames, 
        stats=stats, 
        generated_timestamp=generated_timestamp
    )

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Copy static assets (CSS, JS)
    static_src = _TEMPLATES_DIR / "static"
    static_dst = out_path / "static"
    if static_src.exists():
        shutil.copytree(static_src, static_dst, dirs_exist_ok=True)

    report_file = out_path / "summary_report.html"
    report_file.write_text(html_content, encoding="utf-8")

    return str(report_file.resolve())


# ══════════════════════════════════════════════════════════════════════════════
# PRIVATE HELPERS  (only used under __main__)
# ══════════════════════════════════════════════════════════════════════════════

def _load_mock_data() -> tuple[list[dict], dict]:
    """Load frames and stats from the dev_mock JSON fixtures.

    Reads:
        data/dev_mock/mock_frames.json
        data/dev_mock/mock_summary_stats.json

    Returns
    -------
    (frames, stats)
        A tuple of (list-of-frame-dicts, stats-dict) ready to pass
        directly to :func:`generate_report`.
    """
    mock_dir = _PROJECT_ROOT / "data" / "dev_mock"

    frames_path = mock_dir / "mock_frames.json"
    stats_path  = mock_dir / "mock_summary_stats.json"

    if not frames_path.exists():
        raise FileNotFoundError(f"Mock frames file not found: {frames_path}")
    if not stats_path.exists():
        raise FileNotFoundError(f"Mock stats file not found: {stats_path}")

    with open(frames_path,  encoding="utf-8") as f:
        frames = json.load(f)
    with open(stats_path,   encoding="utf-8") as f:
        stats  = json.load(f)

    return frames, stats


# ══════════════════════════════════════════════════════════════════════════════
# STANDALONE ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    print("[*] Loading mock data …")
    try:
        frames, stats = _load_mock_data()
    except FileNotFoundError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Loaded {len(frames)} frames from mock data.")
    print("[*] Rendering report …")

    output_path = generate_report(frames, stats, output_dir="data/output")

    print(f"[OK] Report written to: {output_path}")
    print("[*] Opening in default browser …")
    webbrowser.open(Path(output_path).as_uri())
