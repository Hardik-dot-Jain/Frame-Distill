"""
tests/test_storage.py
----------------------
Unit tests for src/core/storage.py.

All tests use `tempfile.TemporaryDirectory(ignore_cleanup_errors=True)` via
the shared `_TmpTestCase` base so they leave no artefacts on disk and work
correctly on Windows (where open file handles can delay directory removal).

Run with:
    python -m unittest discover tests -v
or:
    pytest tests/test_storage.py -v
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.storage import (
    calculate_storage_savings,
    ensure_directories,
    get_directory_size_mb,
    get_file_size_mb,
)

_1_MB: int = 1024 * 1024  # 1 048 576 bytes


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------


class _TmpTestCase(unittest.TestCase):
    """Provides self.tmp (Path) backed by a fresh TemporaryDirectory per test."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    # ---------------------------------------------------------------- helpers
    def _write_file(self, name: str, size_bytes: int) -> Path:
        """Write a file of exactly *size_bytes* bytes and return its path."""
        path = self.tmp / name
        path.write_bytes(b"0" * size_bytes)
        return path


# ---------------------------------------------------------------------------
# Tests: ensure_directories
# ---------------------------------------------------------------------------


class TestEnsureDirectories(_TmpTestCase):
    """Physical directory creation tests."""

    def test_base_directory_created(self) -> None:
        output_dir = self.tmp / "run_001"
        ensure_directories(output_dir)
        self.assertTrue(output_dir.is_dir())

    def test_frames_subdirectory_created(self) -> None:
        output_dir = self.tmp / "run_001"
        ensure_directories(output_dir)
        self.assertTrue((output_dir / "frames").is_dir())

    def test_returns_correct_paths(self) -> None:
        output_dir = self.tmp / "run_001"
        result = ensure_directories(output_dir)
        self.assertEqual(result["base"], output_dir)
        self.assertEqual(result["frames"], output_dir / "frames")

    def test_returns_dict_with_two_keys(self) -> None:
        output_dir = self.tmp / "run_002"
        result = ensure_directories(output_dir)
        self.assertEqual(set(result.keys()), {"base", "frames"})

    def test_idempotent_on_existing_dirs(self) -> None:
        """Calling twice should not raise."""
        output_dir = self.tmp / "run_003"
        ensure_directories(output_dir)
        ensure_directories(output_dir)  # must not raise
        self.assertTrue(output_dir.is_dir())

    def test_creates_deep_nested_parents(self) -> None:
        output_dir = self.tmp / "a" / "b" / "c" / "run"
        ensure_directories(output_dir)
        self.assertTrue(output_dir.is_dir())
        self.assertTrue((output_dir / "frames").is_dir())

    def test_returned_paths_are_path_instances(self) -> None:
        output_dir = self.tmp / "run_004"
        result = ensure_directories(output_dir)
        self.assertIsInstance(result["base"], Path)
        self.assertIsInstance(result["frames"], Path)


# ---------------------------------------------------------------------------
# Tests: get_file_size_mb
# ---------------------------------------------------------------------------


class TestGetFileSizeMb(_TmpTestCase):
    """Single-file size tests."""

    def test_exactly_one_mb(self) -> None:
        """A 1 048 576-byte file must return exactly 1.0 MB."""
        path = self._write_file("one_mb.bin", _1_MB)
        self.assertAlmostEqual(get_file_size_mb(path), 1.0, places=2)

    def test_half_mb(self) -> None:
        path = self._write_file("half_mb.bin", _1_MB // 2)
        self.assertAlmostEqual(get_file_size_mb(path), 0.5, places=2)

    def test_exactly_two_mb(self) -> None:
        path = self._write_file("two_mb.bin", 2 * _1_MB)
        self.assertAlmostEqual(get_file_size_mb(path), 2.0, places=2)

    def test_zero_byte_file(self) -> None:
        path = self._write_file("empty.bin", 0)
        self.assertAlmostEqual(get_file_size_mb(path), 0.0, places=2)

    def test_sub_mb_file_rounds_to_two_dp(self) -> None:
        """A 1 000-byte file should round correctly to 2 dp."""
        path = self._write_file("small.bin", 1000)
        result = get_file_size_mb(path)
        # 1000 / 1_048_576 ≈ 0.000953... → rounds to 0.0
        self.assertEqual(round(result, 2), result)  # already rounded

    def test_returns_float(self) -> None:
        path = self._write_file("t.bin", _1_MB)
        self.assertIsInstance(get_file_size_mb(path), float)

    def test_nonexistent_file_raises_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            get_file_size_mb(self.tmp / "ghost.bin")

    def test_error_message_contains_path(self) -> None:
        ghost = self.tmp / "ghost.bin"
        with self.assertRaises(FileNotFoundError) as ctx:
            get_file_size_mb(ghost)
        self.assertIn("ghost.bin", str(ctx.exception))


# ---------------------------------------------------------------------------
# Tests: get_directory_size_mb
# ---------------------------------------------------------------------------


class TestGetDirectorySizeMb(_TmpTestCase):
    """Recursive directory size tests."""

    def test_empty_directory_returns_zero(self) -> None:
        empty = self.tmp / "empty_dir"
        empty.mkdir()
        self.assertAlmostEqual(get_directory_size_mb(empty), 0.0, places=2)

    def test_nonexistent_directory_returns_zero(self) -> None:
        self.assertAlmostEqual(
            get_directory_size_mb(self.tmp / "no_such_dir"), 0.0, places=2
        )

    def test_single_file_in_dir(self) -> None:
        sub = self.tmp / "sub"
        sub.mkdir()
        (sub / "file.bin").write_bytes(b"0" * _1_MB)
        self.assertAlmostEqual(get_directory_size_mb(sub), 1.0, places=2)

    def test_multiple_files_summed(self) -> None:
        """Three files of 1 MB each → 3.0 MB total."""
        sub = self.tmp / "multi"
        sub.mkdir()
        for i in range(3):
            (sub / f"f{i}.bin").write_bytes(b"0" * _1_MB)
        self.assertAlmostEqual(get_directory_size_mb(sub), 3.0, places=2)

    def test_recursive_nested_files_summed(self) -> None:
        """Files in subdirectories are included in the total."""
        sub = self.tmp / "nested"
        deep = sub / "a" / "b"
        deep.mkdir(parents=True)
        (sub / "root.bin").write_bytes(b"0" * _1_MB)
        (deep / "leaf.bin").write_bytes(b"0" * _1_MB)
        self.assertAlmostEqual(get_directory_size_mb(sub), 2.0, places=2)

    def test_returns_float(self) -> None:
        sub = self.tmp / "type_check"
        sub.mkdir()
        self.assertIsInstance(get_directory_size_mb(sub), float)

    def test_known_byte_count_rounds_to_two_dp(self) -> None:
        """Two files of 512 KiB each should sum to exactly 1.0 MB."""
        sub = self.tmp / "half_half"
        sub.mkdir()
        (sub / "a.bin").write_bytes(b"0" * (_1_MB // 2))
        (sub / "b.bin").write_bytes(b"0" * (_1_MB // 2))
        self.assertAlmostEqual(get_directory_size_mb(sub), 1.0, places=2)


# ---------------------------------------------------------------------------
# Tests: calculate_storage_savings
# ---------------------------------------------------------------------------


class TestCalculateStorageSavings(_TmpTestCase):
    """ROI calculation tests."""

    def _make_video(self, size_bytes: int) -> Path:
        return self._write_file("video.mp4", size_bytes)

    def _make_frames_dir(self, total_bytes: int, n_files: int = 1) -> Path:
        frames = self.tmp / "frames"
        frames.mkdir(exist_ok=True)
        per_file = total_bytes // n_files if n_files else 0
        for i in range(n_files):
            (frames / f"frame_{i:04d}.jpg").write_bytes(b"0" * per_file)
        return frames

    # ---------------------------------------------------------------- happy path
    def test_standard_90_percent_saving(self) -> None:
        """100 MB video, 10 MB frames → 90 MB saved, 90.0%."""
        video = self._make_video(100 * _1_MB)
        frames = self._make_frames_dir(10 * _1_MB)
        result = calculate_storage_savings(video, frames)
        self.assertAlmostEqual(result["original_mb"], 100.0, places=1)
        self.assertAlmostEqual(result["final_mb"], 10.0, places=1)
        self.assertAlmostEqual(result["saved_mb"], 90.0, places=1)
        self.assertAlmostEqual(result["saved_percentage"], 90.0, places=0)

    def test_50_percent_saving(self) -> None:
        video = self._make_video(2 * _1_MB)
        frames = self._make_frames_dir(_1_MB)
        result = calculate_storage_savings(video, frames)
        self.assertAlmostEqual(result["saved_percentage"], 50.0, delta=1.0)

    def test_all_frames_kept_zero_saving(self) -> None:
        """If final equals original, saved = 0.0 MB and 0.0%."""
        video = self._make_video(_1_MB)
        frames = self._make_frames_dir(_1_MB)
        result = calculate_storage_savings(video, frames)
        self.assertAlmostEqual(result["saved_mb"], 0.0, places=1)
        self.assertAlmostEqual(result["saved_percentage"], 0.0, places=0)

    def test_empty_frames_dir_100_percent_saving(self) -> None:
        """No kept frames at all → 100% savings."""
        video = self._make_video(_1_MB)
        frames = self.tmp / "empty_frames"
        frames.mkdir()
        result = calculate_storage_savings(video, frames)
        self.assertAlmostEqual(result["final_mb"], 0.0, places=2)
        self.assertAlmostEqual(result["saved_percentage"], 100.0, places=0)

    # ----------------------------------------------------------- edge cases
    def test_negative_saving_frames_exceed_original(self) -> None:
        """Frames larger than video → saved_mb is negative."""
        video = self._make_video(_1_MB)
        frames = self._make_frames_dir(2 * _1_MB)
        result = calculate_storage_savings(video, frames)
        self.assertLess(result["saved_mb"], 0.0)
        self.assertLess(result["saved_percentage"], 0.0)

    def test_zero_byte_video_avoids_division_by_zero(self) -> None:
        """A 0-byte video should return saved_percentage = 0.0, not raise."""
        video = self._make_video(0)
        frames = self._make_frames_dir(0)
        result = calculate_storage_savings(video, frames)
        self.assertAlmostEqual(result["saved_percentage"], 0.0, places=1)
        self.assertAlmostEqual(result["original_mb"], 0.0, places=2)

    def test_nonexistent_video_raises_file_not_found(self) -> None:
        frames = self._make_frames_dir(0)
        with self.assertRaises(FileNotFoundError):
            calculate_storage_savings(self.tmp / "ghost.mp4", frames)

    def test_nonexistent_frames_dir_treated_as_zero(self) -> None:
        """Missing frames dir → final_mb = 0.0, 100% savings."""
        video = self._make_video(_1_MB)
        result = calculate_storage_savings(video, self.tmp / "no_frames")
        self.assertAlmostEqual(result["final_mb"], 0.0, places=2)

    # --------------------------------------------------------- return shape
    def test_return_keys(self) -> None:
        video = self._make_video(_1_MB)
        frames = self._make_frames_dir(_1_MB // 2)
        result = calculate_storage_savings(video, frames)
        self.assertEqual(
            set(result.keys()),
            {"original_mb", "final_mb", "saved_mb", "saved_percentage"},
        )

    def test_saved_percentage_rounded_to_one_dp(self) -> None:
        video = self._make_video(3 * _1_MB)
        frames = self._make_frames_dir(_1_MB)  # saves 2/3 ≈ 66.7%
        result = calculate_storage_savings(video, frames)
        # Verify it's already at 1 dp precision (not more).
        pct = result["saved_percentage"]
        self.assertEqual(round(pct, 1), pct)

    def test_all_values_are_floats(self) -> None:
        video = self._make_video(_1_MB)
        frames = self._make_frames_dir(_1_MB // 2)
        result = calculate_storage_savings(video, frames)
        for key, val in result.items():
            with self.subTest(key=key):
                self.assertIsInstance(val, float)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
