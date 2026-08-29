"""
tests/test_database.py
-----------------------
Unit tests for src/core/database.py.

Strategy
--------
* A class-level `setUp` / `tearDown` pair manages one `TemporaryDirectory`
  per test method, using `ignore_cleanup_errors=True` (Python 3.10+) to
  prevent Windows WAL-sidecar files from raising PermissionError during
  cleanup — the OS will reclaim those files on its own after the process
  releases them.
* All SQLite connections are opened with the `with` statement so they commit
  and close before the temp-dir teardown runs.
* No test touches the real `data/` directory.

Run with:
    python -m unittest discover tests -v
or:
    pytest tests/test_database.py -v
"""

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

# Make src importable when running from the project root.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.database import get_summary_stats, init_db, insert_frame_batch


# ---------------------------------------------------------------------------
# Base test case — handles temp-dir lifecycle for every subclass
# ---------------------------------------------------------------------------


class _TmpDbTestCase(unittest.TestCase):
    """Mixin that provides a fresh temporary directory + DB for each test."""

    def setUp(self) -> None:
        # ignore_cleanup_errors=True avoids Windows WinError 32 on WAL files.
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path: Path = Path(self._tmpdir.name) / "test.db"
        init_db(self.db_path)

    def tearDown(self) -> None:
        # Explicitly checkpoint + close any lingering WAL before rmdir.
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except Exception:
            pass
        self._tmpdir.cleanup()

    # ---------------------------------------------------------------- helpers
    def _make_frames(
        self,
        n: int,
        *,
        is_kept: bool = True,
        base_filename: str = "frame",
    ) -> list[dict]:
        """Generate *n* synthetic frame dicts for insertion."""
        return [
            {
                "frame_filename": f"{base_filename}_{i:04d}.png",
                "timestamp_sec": round(i * 0.033, 4),
                "laplacian_score": 120.0 + i,
                "ssim_score": 0.42,
                "is_kept": int(is_kept),
            }
            for i in range(n)
        ]

    def _populate(self, *, kept: int, discarded: int) -> None:
        """Insert *kept* kept frames and *discarded* discarded frames."""
        rows = self._make_frames(kept, is_kept=True, base_filename="kept")
        rows += self._make_frames(discarded, is_kept=False, base_filename="disc")
        insert_frame_batch(self.db_path, rows)

    def _row_count(self) -> int:
        with sqlite3.connect(str(self.db_path)) as conn:
            return conn.execute("SELECT COUNT(*) FROM frames;").fetchone()[0]


# ---------------------------------------------------------------------------
# Tests: init_db
# ---------------------------------------------------------------------------


class TestInitDb(_TmpDbTestCase):
    """Schema lifecycle tests."""

    def test_creates_frames_table(self) -> None:
        """init_db should create the frames table."""
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type='table' AND name='frames';"
            )
            self.assertIsNotNone(cur.fetchone(), "frames table should exist")

    def test_schema_has_correct_columns(self) -> None:
        """The frames table must expose the six expected columns."""
        expected_cols = {
            "id", "frame_filename", "timestamp_sec",
            "laplacian_score", "ssim_score", "is_kept",
        }
        with sqlite3.connect(str(self.db_path)) as conn:
            cur = conn.execute("PRAGMA table_info(frames);")
            actual_cols = {row[1] for row in cur.fetchall()}
        self.assertEqual(actual_cols, expected_cols)

    def test_init_is_idempotent_drops_existing_data(self) -> None:
        """Calling init_db twice on the same file should reset the table."""
        insert_frame_batch(self.db_path, self._make_frames(5))
        init_db(self.db_path)  # second call must wipe inserted rows
        stats = get_summary_stats(self.db_path)
        self.assertEqual(stats["total_extracted"], 0)

    def test_wal_journal_mode_set(self) -> None:
        """init_db should enable WAL mode for better read concurrency."""
        with sqlite3.connect(str(self.db_path)) as conn:
            mode = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        self.assertEqual(mode, "wal")


# ---------------------------------------------------------------------------
# Tests: insert_frame_batch
# ---------------------------------------------------------------------------


class TestInsertFrameBatch(_TmpDbTestCase):
    """High-performance write tests."""

    def test_inserts_correct_row_count(self) -> None:
        """Batch-inserting N dicts should produce exactly N rows."""
        insert_frame_batch(self.db_path, self._make_frames(10))
        self.assertEqual(self._row_count(), 10)

    def test_inserted_data_matches_input(self) -> None:
        """The values stored must exactly match what was passed in."""
        frame = {
            "frame_filename": "test_frame_0001.png",
            "timestamp_sec": 1.234,
            "laplacian_score": 250.75,
            "ssim_score": 0.88,
            "is_kept": 1,
        }
        insert_frame_batch(self.db_path, [frame])
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.row_factory = sqlite3.Row
            row = dict(
                conn.execute(
                    "SELECT * FROM frames WHERE frame_filename = ?;",
                    (frame["frame_filename"],),
                ).fetchone()
            )
        self.assertEqual(row["frame_filename"], frame["frame_filename"])
        self.assertAlmostEqual(row["timestamp_sec"], frame["timestamp_sec"])
        self.assertAlmostEqual(row["laplacian_score"], frame["laplacian_score"])
        self.assertAlmostEqual(row["ssim_score"], frame["ssim_score"])
        self.assertEqual(bool(row["is_kept"]), bool(frame["is_kept"]))

    def test_empty_batch_is_a_no_op(self) -> None:
        """Calling insert_frame_batch with [] should not raise or insert rows."""
        insert_frame_batch(self.db_path, [])
        self.assertEqual(self._row_count(), 0)

    def test_multiple_batches_accumulate(self) -> None:
        """Successive insert_frame_batch calls should append, not overwrite."""
        insert_frame_batch(self.db_path, self._make_frames(5, base_filename="a"))
        insert_frame_batch(self.db_path, self._make_frames(3, base_filename="b"))
        self.assertEqual(self._row_count(), 8)

    def test_autoincrement_ids_are_unique(self) -> None:
        """Every row inserted should receive a unique auto-incremented id."""
        insert_frame_batch(self.db_path, self._make_frames(20))
        with sqlite3.connect(str(self.db_path)) as conn:
            ids = [r[0] for r in conn.execute("SELECT id FROM frames ORDER BY id;")]
        self.assertEqual(ids, list(range(1, 21)))

    def test_large_batch_performance(self) -> None:
        """Inserting 1 000 rows should complete without error (smoke test)."""
        insert_frame_batch(self.db_path, self._make_frames(1_000))
        self.assertEqual(self._row_count(), 1_000)


# ---------------------------------------------------------------------------
# Tests: get_summary_stats
# ---------------------------------------------------------------------------


class TestGetSummaryStats(_TmpDbTestCase):
    """Report aggregation tests."""

    # ---------------------------------------------------------------- counts
    def test_total_extracted_counts_all_rows(self) -> None:
        self._populate(kept=4, discarded=6)
        stats = get_summary_stats(self.db_path)
        self.assertEqual(stats["total_extracted"], 10)

    def test_total_kept_counts_only_kept_rows(self) -> None:
        self._populate(kept=4, discarded=6)
        stats = get_summary_stats(self.db_path)
        self.assertEqual(stats["total_kept"], 4)

    def test_zero_rows_returns_zero_counts(self) -> None:
        stats = get_summary_stats(self.db_path)
        self.assertEqual(stats["total_extracted"], 0)
        self.assertEqual(stats["total_kept"], 0)
        self.assertEqual(stats["kept_frames"], [])

    def test_all_discarded_kept_count_is_zero(self) -> None:
        self._populate(kept=0, discarded=10)
        stats = get_summary_stats(self.db_path)
        self.assertEqual(stats["total_kept"], 0)
        self.assertEqual(stats["kept_frames"], [])

    # ---------------------------------------------------------- kept_frames
    def test_kept_frames_contains_correct_keys(self) -> None:
        """Each dict in kept_frames must have exactly the three report keys."""
        expected_keys = {"frame_filename", "laplacian_score", "ssim_score"}
        self._populate(kept=3, discarded=2)
        stats = get_summary_stats(self.db_path)
        for frame in stats["kept_frames"]:
            with self.subTest(frame=frame["frame_filename"]):
                self.assertEqual(set(frame.keys()), expected_keys)

    def test_kept_frames_limited_to_50(self) -> None:
        """Even with 100 kept frames, kept_frames must contain at most 50."""
        self._populate(kept=100, discarded=0)
        stats = get_summary_stats(self.db_path)
        self.assertLessEqual(len(stats["kept_frames"]), 50)

    def test_kept_frames_ordered_by_id_asc(self) -> None:
        """Kept frames must be returned in ascending insertion order."""
        self._populate(kept=5, discarded=0)
        stats = get_summary_stats(self.db_path)
        filenames = [f["frame_filename"] for f in stats["kept_frames"]]
        self.assertEqual(filenames, sorted(filenames))

    def test_kept_frames_excludes_discarded_rows(self) -> None:
        """Frames with is_kept=False must not appear in kept_frames."""
        self._populate(kept=3, discarded=7)
        stats = get_summary_stats(self.db_path)
        for frame in stats["kept_frames"]:
            self.assertTrue(
                frame["frame_filename"].startswith("kept_"),
                f"Unexpected filename: {frame['frame_filename']}",
            )

    def test_return_type_is_dict_with_correct_keys(self) -> None:
        stats = get_summary_stats(self.db_path)
        self.assertIsInstance(stats, dict)
        self.assertIn("total_extracted", stats)
        self.assertIn("total_kept", stats)
        self.assertIn("kept_frames", stats)
        self.assertIsInstance(stats["kept_frames"], list)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
