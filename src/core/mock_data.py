"""
src/core/mock_data.py
----------------------
Deterministic synthetic frame-data generator for Frame-Distill.

Responsibilities
----------------
* generate_mock_frames  – produce a list of frame dicts that mirrors the
                          database schema, using a seeded RNG so results are
                          reproducible across machines and runs.
* seed_mock_database    – orchestrate init → generate → insert → summarise
                          in a single call, useful for integration smoke-tests
                          and report-pipeline development.
* export_mock_summary_json – dump get_summary_stats() as formatted JSON so the
                             frontend / HTML-report developer can work without
                             a real video.

Design notes
------------
* Python's built-in `random.Random(seed)` is used instead of numpy.random so
  this module stays dependency-free (no numpy import needed here).
* The `is_kept` logic is the single source of truth — identical to what the
  real CV pipeline will apply — so mock data exercises the same branching that
  the report renderer will encounter in production.
"""

import json
import random
from pathlib import Path
from typing import Optional

from .database import get_summary_stats, init_db, insert_frame_batch


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_mock_frames(
    count: int = 100,
    blur_threshold: float = 100.0,
    ssim_threshold: float = 0.95,
    seed: Optional[int] = 42,
) -> list[dict]:
    """Generate *count* synthetic frame records with deterministic randomness.

    The output list matches the ``frames`` table schema (excluding ``id``) so
    it can be passed directly to :func:`~src.core.database.insert_frame_batch`.

    Simulation model
    ~~~~~~~~~~~~~~~~
    * **Filename** – zero-padded 4-digit counter: ``frame_0001.jpg``, …
    * **Timestamp** – ``i / 30.0`` seconds (simulated 30 FPS source video).
    * **Laplacian score** – uniform float in ``[10.0, 350.0]``.
    * **SSIM score** – uniform float in ``[0.40, 1.00]``; forced to ``0.0``
      for the very first frame (no predecessor to compare against).
    * **is_kept** – ``1`` iff ``laplacian_score >= blur_threshold`` **and**
      ``ssim_score < ssim_threshold``.  For frame 0 the SSIM condition is
      satisfied by definition (score is 0.0 < any sane threshold).

    Args:
        count:           Number of frame records to generate.  ``0`` returns
                         an empty list without error.
        blur_threshold:  Laplacian variance threshold (frames below are blurry).
        ssim_threshold:  SSIM threshold (frames at-or-above are duplicates).
        seed:            RNG seed for full reproducibility.  Pass ``None`` for
                         non-deterministic output.

    Returns:
        A list of ``count`` dicts, each with keys:
        ``frame_filename``, ``timestamp_sec``, ``laplacian_score``,
        ``ssim_score``, ``is_kept``.
    """
    if count == 0:
        return []

    rng = random.Random(seed)
    frames: list[dict] = []

    for i in range(count):
        filename = f"frame_{i + 1:04d}.jpg"
        timestamp_sec = round(i / 30.0, 6)

        laplacian_score = round(rng.uniform(10.0, 350.0), 4)

        # Frame 0 has no predecessor → SSIM is undefined; use 0.0.
        ssim_score = 0.0 if i == 0 else round(rng.uniform(0.40, 1.00), 4)

        sharp_enough = laplacian_score >= blur_threshold
        not_duplicate = ssim_score < ssim_threshold
        is_kept = int(sharp_enough and not_duplicate)

        frames.append(
            {
                "frame_filename": filename,
                "timestamp_sec": timestamp_sec,
                "laplacian_score": laplacian_score,
                "ssim_score": ssim_score,
                "is_kept": is_kept,
            }
        )

    return frames


def seed_mock_database(
    db_path: Path,
    count: int = 100,
    blur_threshold: float = 100.0,
    ssim_threshold: float = 0.95,
    seed: int = 42,
) -> dict:
    """Initialise *db_path*, populate it with mock frames, and return stats.

    This is the one-shot orchestrator used by integration tests and by the
    report-pipeline developer to get a fully populated database without
    needing a real video file.

    Args:
        db_path:         Filesystem path for the SQLite database.
        count:           Number of synthetic frames to generate.
        blur_threshold:  Passed through to :func:`generate_mock_frames`.
        ssim_threshold:  Passed through to :func:`generate_mock_frames`.
        seed:            RNG seed for reproducibility.

    Returns:
        The dict returned by :func:`~src.core.database.get_summary_stats`,
        containing ``total_extracted``, ``total_kept``, and ``kept_frames``.
    """
    init_db(db_path)
    frames = generate_mock_frames(
        count=count,
        blur_threshold=blur_threshold,
        ssim_threshold=ssim_threshold,
        seed=seed,
    )
    insert_frame_batch(db_path, frames)
    return get_summary_stats(db_path)


def export_mock_summary_json(db_path: Path, json_out_path: Path) -> None:
    """Write the summary statistics for *db_path* as formatted JSON.

    Creates any missing parent directories before writing.  The output file
    is human-readable (``indent=2``) and can be consumed directly by the
    HTML-report Jinja2 template or an external data-viz tool.

    Args:
        db_path:       Path to an already-seeded SQLite database.
        json_out_path: Destination path for the JSON file (e.g.
                       ``data/output/summary.json``).
    """
    stats = get_summary_stats(db_path)
    json_out_path.parent.mkdir(parents=True, exist_ok=True)
    json_out_path.write_text(json.dumps(stats, indent=2), encoding="utf-8")
