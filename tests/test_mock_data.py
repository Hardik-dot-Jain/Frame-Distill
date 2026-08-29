"""
tests/test_mock_data.py
------------------------
Unit tests for src/core/mock_data.py.

All tests that need a file-backed database inherit from _TmpDbTestCase (the
same base class pattern used in test_database.py) so Windows WAL-sidecar
cleanup is handled consistently across the whole suite.

Run with:
    python -m unittest discover tests -v
or:
    pytest tests/test_mock_data.py -v
"""

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.mock_data import (
    export_mock_summary_json,
    generate_mock_frames,
    seed_mock_database,
)


# ---------------------------------------------------------------------------
# Base class — temp-dir lifecycle with Windows-safe WAL cleanup
# ---------------------------------------------------------------------------


class _TmpDbTestCase(unittest.TestCase):
    """Provides self.db_path backed by a fresh TemporaryDirectory per test."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmpdir.name) / "mock.db"

    def tearDown(self) -> None:
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        except Exception:
            pass
        self._tmpdir.cleanup()


# ---------------------------------------------------------------------------
# Tests: generate_mock_frames
# ---------------------------------------------------------------------------


class TestGenerateMockFrames(unittest.TestCase):
    """Pure-function tests — no database, no filesystem."""

    # ---------------------------------------------------------------- basics
    def test_returns_correct_count(self) -> None:
        frames = generate_mock_frames(count=50)
        self.assertEqual(len(frames), 50)

    def test_default_count_is_100(self) -> None:
        frames = generate_mock_frames()
        self.assertEqual(len(frames), 100)

    def test_count_zero_returns_empty_list(self) -> None:
        frames = generate_mock_frames(count=0)
        self.assertEqual(frames, [])

    # ------------------------------------------------------------ schema keys
    def test_each_dict_has_required_keys(self) -> None:
        required = {
            "frame_filename", "timestamp_sec",
            "laplacian_score", "ssim_score", "is_kept",
        }
        for frame in generate_mock_frames(count=10):
            with self.subTest(f=frame["frame_filename"]):
                self.assertEqual(set(frame.keys()), required)

    # ----------------------------------------------------------- determinism
    def test_same_seed_produces_identical_output(self) -> None:
        a = generate_mock_frames(count=100, seed=42)
        b = generate_mock_frames(count=100, seed=42)
        self.assertEqual(a, b)

    def test_different_seeds_produce_different_output(self) -> None:
        a = generate_mock_frames(count=50, seed=1)
        b = generate_mock_frames(count=50, seed=2)
        # At least some laplacian scores must differ.
        scores_a = [f["laplacian_score"] for f in a]
        scores_b = [f["laplacian_score"] for f in b]
        self.assertNotEqual(scores_a, scores_b)

    def test_none_seed_produces_non_deterministic_output(self) -> None:
        """Two calls with seed=None are very unlikely to be identical."""
        a = generate_mock_frames(count=50, seed=None)
        b = generate_mock_frames(count=50, seed=None)
        # This assertion may theoretically flake, but the probability is
        # astronomically small for 50 random floats.
        scores_a = [f["laplacian_score"] for f in a]
        scores_b = [f["laplacian_score"] for f in b]
        self.assertNotEqual(scores_a, scores_b)

    # ---------------------------------------------------------- filename format
    def test_filenames_are_zero_padded(self) -> None:
        frames = generate_mock_frames(count=5)
        expected = [f"frame_{i:04d}.jpg" for i in range(1, 6)]
        actual = [f["frame_filename"] for f in frames]
        self.assertEqual(actual, expected)

    def test_filenames_are_unique(self) -> None:
        frames = generate_mock_frames(count=200)
        names = [f["frame_filename"] for f in frames]
        self.assertEqual(len(names), len(set(names)))

    # ---------------------------------------------------------- timestamp
    def test_timestamps_are_30fps(self) -> None:
        frames = generate_mock_frames(count=5)
        for i, frame in enumerate(frames):
            expected = round(i / 30.0, 6)
            self.assertAlmostEqual(frame["timestamp_sec"], expected, places=5)

    def test_timestamps_are_strictly_increasing(self) -> None:
        frames = generate_mock_frames(count=10)
        ts = [f["timestamp_sec"] for f in frames]
        self.assertEqual(ts, sorted(ts))

    # ---------------------------------------------------------- score ranges
    def test_laplacian_scores_within_range(self) -> None:
        for frame in generate_mock_frames(count=200):
            with self.subTest(f=frame["frame_filename"]):
                self.assertGreaterEqual(frame["laplacian_score"], 10.0)
                self.assertLessEqual(frame["laplacian_score"], 350.0)

    def test_ssim_scores_within_range(self) -> None:
        for frame in generate_mock_frames(count=200)[1:]:  # skip frame 0
            with self.subTest(f=frame["frame_filename"]):
                self.assertGreaterEqual(frame["ssim_score"], 0.40)
                self.assertLessEqual(frame["ssim_score"], 1.00)

    def test_first_frame_ssim_is_zero(self) -> None:
        frames = generate_mock_frames(count=10)
        self.assertEqual(frames[0]["ssim_score"], 0.0)

    def test_subsequent_frames_ssim_nonzero(self) -> None:
        frames = generate_mock_frames(count=10)
        for frame in frames[1:]:
            self.assertGreater(frame["ssim_score"], 0.0)

    # --------------------------------------------------------- is_kept logic
    def test_filtration_logic_for_all_frames(self) -> None:
        """Every is_kept value must exactly match the threshold formula."""
        blur_threshold = 100.0
        ssim_threshold = 0.95
        frames = generate_mock_frames(
            count=200,
            blur_threshold=blur_threshold,
            ssim_threshold=ssim_threshold,
        )
        for frame in frames:
            sharp = frame["laplacian_score"] >= blur_threshold
            not_dup = frame["ssim_score"] < ssim_threshold
            expected = int(sharp and not_dup)
            with self.subTest(f=frame["frame_filename"]):
                self.assertEqual(frame["is_kept"], expected)

    def test_custom_thresholds_change_filtration(self) -> None:
        """A very high blur threshold should keep fewer frames than a low one."""
        strict = generate_mock_frames(count=200, blur_threshold=300.0, seed=7)
        lenient = generate_mock_frames(count=200, blur_threshold=10.0, seed=7)
        kept_strict = sum(f["is_kept"] for f in strict)
        kept_lenient = sum(f["is_kept"] for f in lenient)
        self.assertLessEqual(kept_strict, kept_lenient)

    def test_is_kept_is_integer_not_bool(self) -> None:
        """is_kept must be 0 or 1 (int), not a Python bool, for SQLite compat."""
        for frame in generate_mock_frames(count=20):
            self.assertIn(frame["is_kept"], (0, 1))
            # int is a supertype of bool in Python, so check it's actually int
            self.assertIsInstance(frame["is_kept"], int)


# ---------------------------------------------------------------------------
# Tests: seed_mock_database
# ---------------------------------------------------------------------------


class TestSeedMockDatabase(_TmpDbTestCase):
    """Integration tests — exercises the full init → generate → insert → stats pipeline."""

    def test_returns_dict_with_required_keys(self) -> None:
        stats = seed_mock_database(self.db_path, count=50)
        self.assertIn("total_extracted", stats)
        self.assertIn("total_kept", stats)
        self.assertIn("kept_frames", stats)

    def test_total_extracted_matches_count(self) -> None:
        stats = seed_mock_database(self.db_path, count=75)
        self.assertEqual(stats["total_extracted"], 75)

    def test_total_kept_is_non_negative(self) -> None:
        stats = seed_mock_database(self.db_path, count=100)
        self.assertGreaterEqual(stats["total_kept"], 0)
        self.assertLessEqual(stats["total_kept"], 100)

    def test_total_kept_consistent_with_generate(self) -> None:
        """Stats returned must agree with what generate_mock_frames computed."""
        frames = generate_mock_frames(count=100, seed=42)
        expected_kept = sum(f["is_kept"] for f in frames)
        stats = seed_mock_database(self.db_path, count=100, seed=42)
        self.assertEqual(stats["total_kept"], expected_kept)

    def test_database_contains_correct_rows(self) -> None:
        seed_mock_database(self.db_path, count=30)
        with sqlite3.connect(str(self.db_path)) as conn:
            count = conn.execute("SELECT COUNT(*) FROM frames;").fetchone()[0]
        self.assertEqual(count, 30)

    def test_calling_twice_resets_database(self) -> None:
        """Second call to seed_mock_database must not double-insert rows."""
        seed_mock_database(self.db_path, count=20)
        stats = seed_mock_database(self.db_path, count=20)
        self.assertEqual(stats["total_extracted"], 20)

    def test_count_zero_produces_empty_db(self) -> None:
        stats = seed_mock_database(self.db_path, count=0)
        self.assertEqual(stats["total_extracted"], 0)
        self.assertEqual(stats["total_kept"], 0)
        self.assertEqual(stats["kept_frames"], [])


# ---------------------------------------------------------------------------
# Tests: export_mock_summary_json
# ---------------------------------------------------------------------------


class TestExportMockSummaryJson(_TmpDbTestCase):
    """Filesystem + JSON-shape tests for the export helper."""

    def setUp(self) -> None:
        super().setUp()
        # Pre-seed the database so export has data to read.
        seed_mock_database(self.db_path, count=50, seed=42)
        self.json_path = Path(self._tmpdir.name) / "reports" / "summary.json"

    def test_file_is_created(self) -> None:
        export_mock_summary_json(self.db_path, self.json_path)
        self.assertTrue(self.json_path.exists())

    def test_parent_directories_created(self) -> None:
        """export should create missing parent dirs automatically."""
        deep_path = Path(self._tmpdir.name) / "a" / "b" / "c" / "out.json"
        export_mock_summary_json(self.db_path, deep_path)
        self.assertTrue(deep_path.exists())

    def test_output_is_valid_json(self) -> None:
        export_mock_summary_json(self.db_path, self.json_path)
        raw = self.json_path.read_text(encoding="utf-8")
        parsed = json.loads(raw)  # raises if invalid
        self.assertIsInstance(parsed, dict)

    def test_json_contains_required_keys(self) -> None:
        export_mock_summary_json(self.db_path, self.json_path)
        parsed = json.loads(self.json_path.read_text(encoding="utf-8"))
        self.assertIn("total_extracted", parsed)
        self.assertIn("total_kept", parsed)
        self.assertIn("kept_frames", parsed)

    def test_json_total_extracted_matches_count(self) -> None:
        export_mock_summary_json(self.db_path, self.json_path)
        parsed = json.loads(self.json_path.read_text(encoding="utf-8"))
        self.assertEqual(parsed["total_extracted"], 50)

    def test_json_is_pretty_printed(self) -> None:
        """The file must use indent=2 (multi-line), not a single-line dump."""
        export_mock_summary_json(self.db_path, self.json_path)
        raw = self.json_path.read_text(encoding="utf-8")
        self.assertIn("\n", raw)

    def test_overwrite_existing_file(self) -> None:
        """Calling export twice should overwrite, not append."""
        export_mock_summary_json(self.db_path, self.json_path)
        first_size = self.json_path.stat().st_size
        export_mock_summary_json(self.db_path, self.json_path)
        second_size = self.json_path.stat().st_size
        self.assertEqual(first_size, second_size)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
