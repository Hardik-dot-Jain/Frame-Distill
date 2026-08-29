"""
src/core/storage.py
--------------------
File-system utilities for Frame-Distill.

Responsibilities
----------------
* ensure_directories        – create the run output tree on first use.
* get_file_size_mb          – single-file size in MB.
* get_directory_size_mb     – recursive directory size in MB.
* calculate_storage_savings – distillation ROI: how much disk space was saved.

All functions use `pathlib.Path` exclusively.  No global state is mutated so
every function is trivially testable in isolation with a temp directory.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BYTES_PER_MB: int = 1024 * 1024  # 1 048 576 bytes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ensure_directories(output_dir: Path) -> dict[str, Path]:
    """Create *output_dir* and the nested ``frames`` subdirectory.

    Safe to call multiple times — ``exist_ok=True`` means existing
    directories are silently accepted.

    Args:
        output_dir: Root directory for a pipeline run (e.g.
                    ``data/output/run_001``).

    Returns:
        A dict with two keys:

        ``"base"``   – the resolved *output_dir* :class:`pathlib.Path`.
        ``"frames"`` – ``output_dir / "frames"``, where kept frame images
                       will be written.
    """
    frames_dir: Path = output_dir / "frames"
    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir.mkdir(parents=True, exist_ok=True)
    return {"base": output_dir, "frames": frames_dir}


def get_file_size_mb(filepath: Path) -> float:
    """Return the size of *filepath* in Megabytes, rounded to 2 dp.

    Args:
        filepath: Path to the file whose size is needed.

    Returns:
        File size in MB (``bytes / 1_048_576``), rounded to 2 decimal places.

    Raises:
        FileNotFoundError: If *filepath* does not exist on disk.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: '{filepath}'")

    size_bytes: int = filepath.stat().st_size
    return round(size_bytes / _BYTES_PER_MB, 2)


def get_directory_size_mb(dir_path: Path) -> float:
    """Recursively sum all file sizes under *dir_path* and return total in MB.

    Directories that do not exist or are empty return ``0.0`` without raising.
    Symlinks are followed (``Path.rglob`` default behaviour).

    Args:
        dir_path: Root directory to measure.

    Returns:
        Total size of all files beneath *dir_path* in MB, rounded to 2 dp.
        Returns ``0.0`` if the directory is missing or contains no files.
    """
    if not dir_path.exists():
        return 0.0

    total_bytes: int = sum(
        f.stat().st_size
        for f in dir_path.rglob("*")
        if f.is_file()
    )
    return round(total_bytes / _BYTES_PER_MB, 2)


def calculate_storage_savings(
    original_video: Path,
    frames_dir: Path,
) -> dict:
    """Compute disk-space savings produced by the distillation pipeline.

    Compares the size of the source video against the total size of the kept
    frame images to quantify the ROI of running Frame-Distill.

    Args:
        original_video: Path to the source video file.
        frames_dir:     Directory containing the kept frame images (the
                        ``"frames"`` sub-directory produced by
                        :func:`ensure_directories`).

    Returns:
        A dict with four keys:

        ``"original_mb"``      (:class:`float`) – size of the input video.
        ``"final_mb"``         (:class:`float`) – total size of kept frames.
        ``"saved_mb"``         (:class:`float`) – ``original_mb - final_mb``.
        ``"saved_percentage"`` (:class:`float`) – ``(saved_mb / original_mb)
                               * 100``, rounded to 1 dp.  Returns ``0.0`` when
                               *original_mb* is ``0.0`` to avoid division by
                               zero.
    """
    original_mb: float = get_file_size_mb(original_video)
    final_mb: float = get_directory_size_mb(frames_dir)
    saved_mb: float = round(original_mb - final_mb, 2)

    if original_mb == 0.0:
        saved_percentage = 0.0
    else:
        saved_percentage = round((saved_mb / original_mb) * 100.0, 1)

    return {
        "original_mb": original_mb,
        "final_mb": final_mb,
        "saved_mb": saved_mb,
        "saved_percentage": saved_percentage,
    }
