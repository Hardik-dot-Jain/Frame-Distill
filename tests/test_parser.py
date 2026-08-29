"""
tests/test_parser.py
---------------------
Unit tests for src/cli/parser.py using the standard `unittest` module
(no extra dependencies beyond what's already in requirements.txt).

Run with:
    python -m unittest discover tests
or with pytest (if installed):
    pytest tests/test_parser.py -v
"""

import argparse
import sys
import tempfile
import unittest
from pathlib import Path

# Make the src package importable when running from the project root.
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cli.parser import (
    build_parser,
    validate_blur_threshold,
    validate_sample_rate,
    validate_ssim_threshold,
    validate_video_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_temp_video(suffix: str = ".mp4") -> Path:
    """Create an empty temporary file with the given extension and return its path.

    The caller is responsible for cleanup (use tmp_path or manual unlink).
    We use NamedTemporaryFile with delete=False so the path exists on disk
    for the duration of the test.
    """
    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    tmp.close()
    return Path(tmp.name)


# ---------------------------------------------------------------------------
# Tests: validate_video_path
# ---------------------------------------------------------------------------


class TestValidateVideoPath(unittest.TestCase):
    """Unit tests for the validate_video_path() helper."""

    def setUp(self) -> None:
        # Create a real temporary .mp4 file for "happy path" tests.
        self.valid_video = _make_temp_video(".mp4")

    def tearDown(self) -> None:
        self.valid_video.unlink(missing_ok=True)

    def test_valid_mp4_returns_resolved_path(self) -> None:
        result = validate_video_path(str(self.valid_video))
        self.assertIsInstance(result, Path)
        self.assertTrue(result.is_absolute())

    def test_all_supported_extensions_accepted(self) -> None:
        for ext in (".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"):
            with self.subTest(ext=ext):
                tmp = _make_temp_video(ext)
                try:
                    result = validate_video_path(str(tmp))
                    self.assertEqual(result.suffix.lower(), ext)
                finally:
                    tmp.unlink(missing_ok=True)

    def test_nonexistent_path_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError) as ctx:
            validate_video_path("/nonexistent/path/to/video.mp4")
        self.assertIn("does not exist", str(ctx.exception))

    def test_unsupported_extension_raises(self) -> None:
        tmp = _make_temp_video(".txt")
        try:
            with self.assertRaises(argparse.ArgumentTypeError) as ctx:
                validate_video_path(str(tmp))
            self.assertIn("Unsupported video extension", str(ctx.exception))
        finally:
            tmp.unlink(missing_ok=True)

    def test_unsupported_extension_pdf_raises(self) -> None:
        tmp = _make_temp_video(".pdf")
        try:
            with self.assertRaises(argparse.ArgumentTypeError):
                validate_video_path(str(tmp))
        finally:
            tmp.unlink(missing_ok=True)

    def test_extension_check_is_case_insensitive(self) -> None:
        """Uppercase extensions like .MP4 should still be accepted."""
        tmp = _make_temp_video(".MP4")
        try:
            result = validate_video_path(str(tmp))
            self.assertIsInstance(result, Path)
        finally:
            tmp.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Tests: validate_blur_threshold
# ---------------------------------------------------------------------------


class TestValidateBlurThreshold(unittest.TestCase):
    """Unit tests for the validate_blur_threshold() helper."""

    def test_positive_float_accepted(self) -> None:
        self.assertAlmostEqual(validate_blur_threshold("100.0"), 100.0)
        self.assertAlmostEqual(validate_blur_threshold("0.001"), 0.001)
        self.assertAlmostEqual(validate_blur_threshold("9999"), 9999.0)

    def test_zero_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError) as ctx:
            validate_blur_threshold("0.0")
        self.assertIn("> 0.0", str(ctx.exception))

    def test_negative_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            validate_blur_threshold("-50")

    def test_non_numeric_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError) as ctx:
            validate_blur_threshold("abc")
        self.assertIn("must be a number", str(ctx.exception))


# ---------------------------------------------------------------------------
# Tests: validate_ssim_threshold
# ---------------------------------------------------------------------------


class TestValidateSsimThreshold(unittest.TestCase):
    """Unit tests for the validate_ssim_threshold() helper."""

    def test_boundary_zero_accepted(self) -> None:
        self.assertAlmostEqual(validate_ssim_threshold("0.0"), 0.0)

    def test_boundary_one_accepted(self) -> None:
        self.assertAlmostEqual(validate_ssim_threshold("1.0"), 1.0)

    def test_midpoint_accepted(self) -> None:
        self.assertAlmostEqual(validate_ssim_threshold("0.95"), 0.95)

    def test_above_one_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError) as ctx:
            validate_ssim_threshold("1.5")
        self.assertIn("[0.0, 1.0]", str(ctx.exception))

    def test_negative_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError) as ctx:
            validate_ssim_threshold("-0.2")
        self.assertIn("[0.0, 1.0]", str(ctx.exception))

    def test_non_numeric_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            validate_ssim_threshold("bad")


# ---------------------------------------------------------------------------
# Tests: validate_sample_rate
# ---------------------------------------------------------------------------


class TestValidateSampleRate(unittest.TestCase):
    """Unit tests for the validate_sample_rate() helper."""

    def test_one_accepted(self) -> None:
        self.assertEqual(validate_sample_rate("1"), 1)

    def test_large_value_accepted(self) -> None:
        self.assertEqual(validate_sample_rate("30"), 30)

    def test_zero_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError) as ctx:
            validate_sample_rate("0")
        self.assertIn(">= 1", str(ctx.exception))

    def test_negative_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            validate_sample_rate("-5")

    def test_float_string_raises(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            validate_sample_rate("2.5")


# ---------------------------------------------------------------------------
# Tests: parse_args (integration — uses build_parser())
# ---------------------------------------------------------------------------


class TestParseArgs(unittest.TestCase):
    """Integration tests that exercise the full parser end-to-end."""

    def setUp(self) -> None:
        self.valid_video = _make_temp_video(".mp4")
        self.parser = build_parser()

    def tearDown(self) -> None:
        self.valid_video.unlink(missing_ok=True)

    # ---------------------------------------------------------------- happy
    def test_defaults_applied_when_only_input_given(self) -> None:
        ns = self.parser.parse_args(["--input", str(self.valid_video)])
        self.assertAlmostEqual(ns.blur_threshold, 100.0)
        self.assertAlmostEqual(ns.ssim_threshold, 0.95)
        self.assertEqual(ns.sample_rate, 1)
        self.assertEqual(ns.output_dir, Path("data/output"))
        self.assertFalse(ns.no_report)

    def test_short_flags_parsed_correctly(self) -> None:
        ns = self.parser.parse_args(
            ["-i", str(self.valid_video), "-b", "80", "-s", "0.90", "-r", "2"]
        )
        self.assertAlmostEqual(ns.blur_threshold, 80.0)
        self.assertAlmostEqual(ns.ssim_threshold, 0.90)
        self.assertEqual(ns.sample_rate, 2)

    def test_no_report_flag_sets_true(self) -> None:
        ns = self.parser.parse_args(
            ["--input", str(self.valid_video), "--no-report"]
        )
        self.assertTrue(ns.no_report)

    def test_custom_output_dir(self) -> None:
        ns = self.parser.parse_args(
            ["--input", str(self.valid_video), "--output-dir", "results/run1"]
        )
        self.assertEqual(ns.output_dir, Path("results/run1"))

    def test_input_is_resolved_path(self) -> None:
        ns = self.parser.parse_args(["--input", str(self.valid_video)])
        self.assertIsInstance(ns.input, Path)
        self.assertTrue(ns.input.is_absolute())

    # -------------------------------------------------------------- errors
    def test_missing_input_causes_system_exit(self) -> None:
        """argparse calls sys.exit(2) when a required argument is omitted."""
        with self.assertRaises(SystemExit) as ctx:
            self.parser.parse_args([])
        self.assertEqual(ctx.exception.code, 2)

    def test_nonexistent_input_causes_system_exit(self) -> None:
        with self.assertRaises(SystemExit):
            self.parser.parse_args(["--input", "/fake/path/video.mp4"])

    def test_unsupported_extension_causes_system_exit(self) -> None:
        tmp = _make_temp_video(".txt")
        try:
            with self.assertRaises(SystemExit):
                self.parser.parse_args(["--input", str(tmp)])
        finally:
            tmp.unlink(missing_ok=True)

    def test_ssim_above_one_causes_system_exit(self) -> None:
        with self.assertRaises(SystemExit):
            self.parser.parse_args(
                ["--input", str(self.valid_video), "--ssim-threshold", "1.5"]
            )

    def test_ssim_negative_causes_system_exit(self) -> None:
        with self.assertRaises(SystemExit):
            self.parser.parse_args(
                ["--input", str(self.valid_video), "--ssim-threshold", "-0.2"]
            )

    def test_blur_zero_causes_system_exit(self) -> None:
        with self.assertRaises(SystemExit):
            self.parser.parse_args(
                ["--input", str(self.valid_video), "--blur-threshold", "0"]
            )

    def test_sample_rate_zero_causes_system_exit(self) -> None:
        with self.assertRaises(SystemExit):
            self.parser.parse_args(
                ["--input", str(self.valid_video), "--sample-rate", "0"]
            )


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    unittest.main(verbosity=2)
