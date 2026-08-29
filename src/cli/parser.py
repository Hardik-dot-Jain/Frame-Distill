"""
src/cli/parser.py
-----------------
Argument parser for Frame-Distill.

Entry point:  parse_args(args=None) -> argparse.Namespace

Validation helpers are defined as standalone functions so they can be
referenced as `type=` callables by argparse, which means they raise
argparse.ArgumentTypeError on bad input — letting argparse produce
standard, consistent error messages without us ever calling sys.exit().
"""

import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(
    {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}
)


# ---------------------------------------------------------------------------
# Custom type / validation helpers
# ---------------------------------------------------------------------------


def validate_video_path(raw: str) -> Path:
    """Validate that *raw* is an existing file with a supported video extension.

    Args:
        raw: The raw string value supplied by the user on the command line.

    Returns:
        A resolved :class:`pathlib.Path` pointing to the video file.

    Raises:
        argparse.ArgumentTypeError: If the path does not exist or has an
            unsupported extension.
    """
    path = Path(raw)

    if not path.exists():
        raise argparse.ArgumentTypeError(
            f"Input path does not exist: '{path}'"
        )

    if not path.is_file():
        raise argparse.ArgumentTypeError(
            f"Input path is not a file: '{path}'"
        )

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
        raise argparse.ArgumentTypeError(
            f"Unsupported video extension '{suffix}'. "
            f"Allowed extensions: {supported}"
        )

    return path.resolve()


def validate_output_dir(raw: str) -> Path:
    """Convert *raw* to a :class:`pathlib.Path` (directory need not exist yet).

    The directory will be created at runtime by the storage module.

    Args:
        raw: The raw string value supplied by the user.

    Returns:
        A :class:`pathlib.Path` for the output directory.
    """
    return Path(raw)


def validate_blur_threshold(raw: str) -> float:
    """Validate that *raw* is a positive float (> 0.0).

    Args:
        raw: The raw string value supplied by the user.

    Returns:
        The validated blur threshold as a :class:`float`.

    Raises:
        argparse.ArgumentTypeError: If the value is not a positive float.
    """
    try:
        value = float(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Blur threshold must be a number, got: '{raw}'"
        )

    if value <= 0.0:
        raise argparse.ArgumentTypeError(
            f"Blur threshold must be > 0.0, got: {value}"
        )

    return value


def validate_ssim_threshold(raw: str) -> float:
    """Validate that *raw* is a float in the closed interval [0.0, 1.0].

    Args:
        raw: The raw string value supplied by the user.

    Returns:
        The validated SSIM threshold as a :class:`float`.

    Raises:
        argparse.ArgumentTypeError: If the value is outside [0.0, 1.0].
    """
    try:
        value = float(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"SSIM threshold must be a number, got: '{raw}'"
        )

    if not (0.0 <= value <= 1.0):
        raise argparse.ArgumentTypeError(
            f"SSIM threshold must be in [0.0, 1.0], got: {value}"
        )

    return value


def validate_sample_rate(raw: str) -> int:
    """Validate that *raw* is an integer >= 1.

    Args:
        raw: The raw string value supplied by the user.

    Returns:
        The validated sample rate as an :class:`int`.

    Raises:
        argparse.ArgumentTypeError: If the value is not an integer >= 1.
    """
    try:
        value = int(raw)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"Sample rate must be an integer, got: '{raw}'"
        )

    if value < 1:
        raise argparse.ArgumentTypeError(
            f"Sample rate must be >= 1, got: {value}"
        )

    return value


# ---------------------------------------------------------------------------
# Parser factory
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the fully configured :class:`argparse.ArgumentParser`.

    Separating parser construction from :func:`parse_args` makes it trivial
    to test the parser in isolation without supplying real sys.argv values.

    Returns:
        A configured :class:`argparse.ArgumentParser` instance.
    """
    parser = argparse.ArgumentParser(
        prog="frame-distill",
        description=(
            "A zero-cloud CLI tool to filter blurry and duplicate "
            "video frames for ML datasets."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  frame-distill -i clip.mp4\n"
            "  frame-distill -i clip.mp4 -o results/ -b 80 -s 0.90 -r 2\n"
            "  frame-distill -i clip.mp4 --no-report\n"
        ),
    )

    # ------------------------------------------------------------------ input
    parser.add_argument(
        "--input", "-i",
        required=True,
        type=validate_video_path,
        metavar="VIDEO",
        help=(
            "Path to the input video file. "
            f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}."
        ),
    )

    # --------------------------------------------------------------- output
    parser.add_argument(
        "--output-dir", "-o",
        default="data/output",
        type=validate_output_dir,
        metavar="DIR",
        dest="output_dir",
        help=(
            "Directory where kept frames, the SQLite database, and the "
            "HTML report will be saved. Created automatically if absent. "
            "[default: data/output]"
        ),
    )

    # -------------------------------------------------------- blur-threshold
    parser.add_argument(
        "--blur-threshold", "-b",
        default=100.0,
        type=validate_blur_threshold,
        metavar="FLOAT",
        dest="blur_threshold",
        help=(
            "Laplacian variance threshold. Frames with variance below this "
            "value are discarded as blurry. Must be > 0. [default: 100.0]"
        ),
    )

    # -------------------------------------------------------- ssim-threshold
    parser.add_argument(
        "--ssim-threshold", "-s",
        default=0.95,
        type=validate_ssim_threshold,
        metavar="FLOAT",
        dest="ssim_threshold",
        help=(
            "Structural Similarity Index threshold. Frames with SSIM above "
            "this value relative to the previous kept frame are discarded as "
            "duplicates. Must be in [0.0, 1.0]. [default: 0.95]"
        ),
    )

    # ---------------------------------------------------------- sample-rate
    parser.add_argument(
        "--sample-rate", "-r",
        default=1,
        type=validate_sample_rate,
        metavar="N",
        dest="sample_rate",
        help=(
            "Process every Nth frame (1 = every frame, 2 = every other "
            "frame, etc.). Must be >= 1. [default: 1]"
        ),
    )

    # ----------------------------------------------------------- no-report
    parser.add_argument(
        "--no-report",
        action="store_true",
        default=False,
        dest="no_report",
        help=(
            "Skip automatically opening the HTML report in the browser "
            "after the pipeline completes."
        ),
    )

    return parser


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse and validate command-line arguments for Frame-Distill.

    Args:
        args: A list of string arguments to parse. When ``None`` (default),
              ``sys.argv[1:]`` is used — the standard argparse behaviour.

    Returns:
        A populated :class:`argparse.Namespace` with validated, typed fields:

        * ``input``          – :class:`pathlib.Path` (resolved, existing video)
        * ``output_dir``     – :class:`pathlib.Path`
        * ``blur_threshold`` – :class:`float` > 0.0
        * ``ssim_threshold`` – :class:`float` in [0.0, 1.0]
        * ``sample_rate``    – :class:`int` >= 1
        * ``no_report``      – :class:`bool`
    """
    return build_parser().parse_args(args)
