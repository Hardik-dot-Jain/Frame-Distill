# src/main.py
# Responsibility: Top-level pipeline orchestrator.
# Wires together CLI args → storage setup → frame extraction →
# blur/duplicate filtering → database persistence → report generation.
# Phase 5 will implement the full orchestration logic.


import io
import sys
from pathlib import Path

# Reconfigure stdout/stderr to UTF-8 so emoji render correctly on Windows.
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


# Ensure Python can find the src modules when running from the root folder
sys.path.append(str(Path(__file__).parent))

from cli.parser import parse_args
from core.storage import ensure_directories
from core.mock_data import seed_mock_database, export_mock_summary_json

def main():
    # 1. Parse terminal inputs
    args = parse_args()
    
    # 2. Setup storage directories
    out_dir = Path(args.output_dir)
    dirs = ensure_directories(out_dir)
    
    print(f"\n🚀 Initializing Frame-Distill Simulated Run...")
    print(f"📁 Output directory: {dirs['base']}")
    
    # 3. Generate Mock Data & Seed SQLite
    db_path = dirs['base'] / "distill.sqlite"
    json_path = dirs['base'] / "summary.json"
    
    # Simulate extracting and filtering 100 frames
    stats = seed_mock_database(
        db_path=db_path,
        count=100,
        blur_threshold=args.blur_threshold,
        ssim_threshold=args.ssim_threshold
    )
    
    # 4. Export JSON for the Frontend Developer
    export_mock_summary_json(db_path, json_path)
    
    print(f"✅ Extraction complete!")
    print(f"📊 Total Frames: {stats['total_extracted']} | Kept: {stats['total_kept']}")
    print(f"💾 Database saved to: {db_path}")
    print(f"🌐 UI Data saved to: {json_path}\n")

if __name__ == "__main__":
    main()