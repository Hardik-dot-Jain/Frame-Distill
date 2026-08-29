"""
src/core/database.py
---------------------
Isolated SQLite controller for Frame-Distill.

Responsibilities
----------------
* Schema lifecycle  – drop-and-recreate the `frames` table on each new run.
* Batch insertion   – fast, parameterised `executemany()` writes.
* Summary queries   – aggregated stats consumed by the HTML report.

All public functions accept a `db_path` argument so they remain pure and
testable in isolation (callers can pass `:memory:` or a tmp-dir path).
The `with sqlite3.connect(...) as conn:` pattern is used throughout;
SQLite's context manager commits on clean exit and rolls back on exception,
guaranteeing no partial writes escape.
"""

import sqlite3
from pathlib import Path

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS frames (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    frame_filename   TEXT    NOT NULL,
    timestamp_sec    REAL    NOT NULL,
    laplacian_score  REAL    NOT NULL,
    ssim_score       REAL    NOT NULL,
    is_kept          BOOLEAN NOT NULL
);
"""

_DROP_TABLE_SQL = "DROP TABLE IF EXISTS frames;"

_INSERT_SQL = """
INSERT INTO frames
    (frame_filename, timestamp_sec, laplacian_score, ssim_score, is_kept)
VALUES
    (:frame_filename, :timestamp_sec, :laplacian_score, :ssim_score, :is_kept);
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init_db(db_path: Path) -> None:
    """Initialise (or reset) the database at *db_path*.

    Drops any existing ``frames`` table and recreates it with the canonical
    schema.  This guarantees a clean slate for every new pipeline run without
    requiring the caller to delete the file.

    Args:
        db_path: Filesystem path to the SQLite database file, or the special
                 string ``":memory:"`` wrapped in a :class:`pathlib.Path` for
                 in-process testing.
    """
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(_DROP_TABLE_SQL)
        conn.execute(_CREATE_TABLE_SQL)
        conn.execute("PRAGMA journal_mode=WAL;")  # better concurrent reads
        conn.execute("PRAGMA synchronous=NORMAL;")  # safe + faster than FULL


def insert_frame_batch(db_path: Path, frames_data: list[dict]) -> None:
    """Persist a batch of frame records to the database.

    Uses :meth:`sqlite3.Cursor.executemany` for a single round-trip to the
    database engine, which is significantly faster than looping
    ``execute()`` calls when ingesting hundreds or thousands of frames.

    Named placeholders (``:``) are used rather than positional ``?`` so that
    callers do not need to maintain tuple ordering — they simply pass the
    same dictionaries produced by the processing pipeline.

    Args:
        db_path: Path to the SQLite database (must already be initialised
                 via :func:`init_db`).
        frames_data: A list of dicts, each containing the keys:

                     * ``frame_filename``  (str)
                     * ``timestamp_sec``   (float)
                     * ``laplacian_score`` (float)
                     * ``ssim_score``      (float)
                     * ``is_kept``         (bool | int)

    Raises:
        sqlite3.IntegrityError: If a required column is missing from a dict.
    """
    if not frames_data:
        return  # nothing to write — short-circuit cleanly

    with sqlite3.connect(str(db_path)) as conn:
        conn.executemany(_INSERT_SQL, frames_data)


def get_summary_stats(db_path: Path) -> dict:
    """Query aggregate statistics for the pipeline's HTML report.

    Args:
        db_path: Path to the SQLite database (must already be populated via
                 :func:`insert_frame_batch`).

    Returns:
        A dictionary with the following keys:

        ``total_extracted`` (:class:`int`)
            Total number of rows in the ``frames`` table.

        ``total_kept`` (:class:`int`)
            Number of rows where ``is_kept = 1``.

        ``kept_frames`` (:class:`list` of :class:`dict`)
            Up to 50 kept frames ordered by ``id ASC``, each dict containing:

            * ``frame_filename``  (str)
            * ``laplacian_score`` (float)
            * ``ssim_score``      (float)
    """
    with sqlite3.connect(str(db_path)) as conn:
        # sqlite3.Row lets us access columns by name like a dict/namedtuple.
        conn.row_factory = sqlite3.Row

        cur = conn.cursor()

        # --- aggregate counts -----------------------------------------------
        cur.execute("SELECT COUNT(*) AS n FROM frames;")
        total_extracted: int = cur.fetchone()["n"]

        cur.execute("SELECT COUNT(*) AS n FROM frames WHERE is_kept = 1;")
        total_kept: int = cur.fetchone()["n"]

        # --- kept frame details (capped at 50 for report rendering) ----------
        cur.execute(
            """
            SELECT frame_filename, laplacian_score, ssim_score
            FROM   frames
            WHERE  is_kept = 1
            ORDER  BY id ASC
            LIMIT  50;
            """
        )
        kept_frames: list[dict] = [dict(row) for row in cur.fetchall()]

    return {
        "total_extracted": total_extracted,
        "total_kept": total_kept,
        "kept_frames": kept_frames,
    }
