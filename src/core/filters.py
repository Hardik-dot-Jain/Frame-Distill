"""
filters.py — Video Distillation Filters
========================================
Provides the core generator that walks through a video file, extracts
candidate frames, and yields structured per-frame metadata.

The output schema is enforced via a Pydantic v2 model (``FrameResult``) so
that callers always receive a well-typed, validated dict.

Typical usage
-------------
    for result in process_video("clip.mp4", "output/frames"):
        if not result.is_blurry and not result.is_duplicate:
            print(result.frame)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

import cv2
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Output contract
# ---------------------------------------------------------------------------

class FrameResult(BaseModel):
    """Validated output produced for every sampled frame.

    Attributes
    ----------
    frame:
        Relative path to the saved frame image, e.g. ``frames/0001.jpg``.
        The path is relative to *output_dir* so it remains portable.
    blur_score:
        Laplacian variance of the frame.  Lower values indicate more blur.
        A score of ``0.0`` is the placeholder used before analysis runs.
    is_blurry:
        ``True`` when the frame fails the blur threshold check.
        Always ``False`` in the current stub — set by the blur filter later.
    is_duplicate:
        ``True`` when the frame is considered too similar to a recent one.
        Always ``False`` in the current stub — set by the dedup filter later.
    """

    frame: str = Field(
        ...,
        description="Relative path to the saved frame image (e.g. frames/0001.jpg).",
        examples=["frames/0001.jpg"],
    )
    blur_score: float = Field(
        default=0.0,
        ge=0.0,
        description="Laplacian variance; lower means blurrier.",
    )
    is_blurry: bool = Field(
        default=False,
        description="True if the frame is considered too blurry to keep.",
    )
    is_duplicate: bool = Field(
        default=False,
        description="True if the frame is a near-duplicate of a recent frame.",
    )


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Only every N-th video frame is sampled.
FRAME_SAMPLE_INTERVAL: int = 5

#: Sub-directory (inside output_dir) where extracted frames are written.
FRAMES_SUBDIR: str = "frames"

#: OpenCV JPEG quality (0-100) used when saving frames.
JPEG_QUALITY: int = 95


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

def process_video(
    video_path: str | os.PathLike,
    output_dir: str | os.PathLike,
) -> Generator[FrameResult, None, None]:
    """Extract every 5th frame from *video_path* and yield a :class:`FrameResult`.

    The generator performs the minimal I/O needed to produce a valid output
    structure.  Blur scoring and duplicate detection are **not** implemented
    here yet — both flags are left at their safe defaults (``False``) so that
    downstream code can iterate over real frame paths immediately.

    Parameters
    ----------
    video_path:
        Absolute or relative path to the source video file.  Any format
        supported by the installed OpenCV build is accepted (MP4, AVI, MKV ...).
    output_dir:
        Directory under which extracted frames are stored.  The function
        creates ``<output_dir>/frames/`` automatically if it does not exist.

    Yields
    ------
    FrameResult
        One validated result per sampled frame.

    Raises
    ------
    FileNotFoundError
        If *video_path* does not exist or cannot be opened by OpenCV.
    RuntimeError
        If the video stream becomes unreadable mid-way through processing.

    Examples
    --------
    >>> for result in process_video("recording.mp4", "out"):
    ...     print(result.model_dump())
    {'frame': 'frames/0001.jpg', 'blur_score': 0.0,
     'is_blurry': False, 'is_duplicate': False}
    """
    video_path = Path(video_path)
    output_dir = Path(output_dir)

    # ------------------------------------------------------------------ setup
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    frames_dir = output_dir / FRAMES_SUBDIR
    os.makedirs(frames_dir, exist_ok=True)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"OpenCV could not open video: {video_path}")

    total_frames: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps: float = cap.get(cv2.CAP_PROP_FPS) or 0.0

    print(
        f"[process_video] source={video_path.name!r} "
        f"| total_frames={total_frames} | fps={fps:.2f}"
    )

    # ------------------------------------------------------------------ loop
    frame_index: int = 0      # absolute index of the frame read from the video
    saved_count: int = 0      # number of frames actually saved / yielded

    try:
        while True:
            ret, bgr_frame = cap.read()

            if not ret:
                # End of stream — normal termination.
                break

            # Only process every N-th frame.
            if frame_index % FRAME_SAMPLE_INTERVAL == 0:
                saved_count += 1

                # Build a zero-padded filename and its relative path.
                filename: str = f"{saved_count:04d}.jpg"
                relative_path: str = f"{FRAMES_SUBDIR}/{filename}"
                absolute_path: Path = frames_dir / filename

                # Persist the frame to disk.
                cv2.imwrite(
                    str(absolute_path),
                    bgr_frame,
                    [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY],
                )

                # ----------------------------------------------------------
                # Yield a *dummy* FrameResult.
                #
                # TODO (blur filter)  : replace blur_score=0.0 and
                #                       is_blurry=False with real Laplacian
                #                       variance computation.
                # TODO (dedup filter) : replace is_duplicate=False with a
                #                       perceptual-hash or histogram check.
                # ----------------------------------------------------------
                yield FrameResult(
                    frame=relative_path,
                    blur_score=0.0,       # placeholder — no analysis yet
                    is_blurry=False,      # placeholder — no blur filter yet
                    is_duplicate=False,   # placeholder — no dedup filter yet
                )

            frame_index += 1

    finally:
        cap.release()

    print(
        f"[process_video] done — read {frame_index} frames, "
        f"sampled {saved_count} (every {FRAME_SAMPLE_INTERVAL}th)."
    )
