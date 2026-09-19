"""
run.py — CLI for the Manim Educational Video Pipeline.

Examples:
    # Full pipeline: PDF → 45 min video
    python run.py --pdf iemh101.pdf

    # Plan only (review storyboard before rendering)
    python run.py --pdf iemh101.pdf --plan-only

    # Resume interrupted pipeline
    python run.py --pdf iemh101.pdf --resume

    # Skip to rendering stage (stages 0-2 must be done)
    python run.py --pdf iemh101.pdf --stage 3

    # High quality render
    python run.py --pdf iemh101.pdf --quality h

    # Use specific models
    python run.py --pdf iemh101.pdf --storyboard-model gemma4:12b --manim-model maternion/manim-coder
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Manim Educational Video Pipeline — PDF → 30-60 min animated video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py --pdf iemh101.pdf                          Full pipeline
  python run.py --pdf iemh101.pdf --plan-only              Review storyboard first
  python run.py --pdf iemh101.pdf --resume --stage 3       Resume from stage 3
  python run.py --pdf iemh101.pdf --minutes 30             Shorter video
  python run.py --pdf iemh101.pdf --quality h               1080p render
        """,
    )

    parser.add_argument(
        "--pdf", required=True, metavar="PATH",
        help="Path to educational PDF (e.g., iemh101.pdf)",
    )
    parser.add_argument(
        "--name", default=None,
        help="Output slug under outputs/ (default: derived from PDF name)",
    )
    parser.add_argument(
        "--minutes", type=int, default=45,
        help="Target video duration in minutes (default: 45)",
    )
    parser.add_argument(
        "--plan-only", action="store_true",
        help="Stop after storyboard generation — review before rendering",
    )
    parser.add_argument(
        "--resume", action="store_true", default=True,
        help="Resume from existing state (default: True)",
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Ignore saved state, regenerate everything",
    )
    parser.add_argument(
        "--stage", type=int, default=0, choices=[0, 1, 2, 3, 4, 5],
        help="Start from this stage (0=PDF, 1=Analysis, 2=Storyboard, 3=Codegen, 4=Render, 5=Assembly)",
    )
    parser.add_argument(
        "--quality", default="m", choices=["l", "m", "h", "k"],
        help="Manim render quality: l=480p, m=720p, h=1080p, k=4K (default: m)",
    )
    parser.add_argument(
        "--storyboard-model", default=None,
        help="Override storyboard LLM model (default: from config)",
    )
    parser.add_argument(
        "--manim-model", default=None,
        help="Override manim-coder model (default: maternion/manim-coder)",
    )

    args = parser.parse_args()

    resume = not args.no_resume

    # Validate PDF exists
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"Error: PDF not found: {pdf_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"  Manim Educational Video Pipeline")
    print(f"{'='*60}")
    print(f"  PDF      : {pdf_path}")
    print(f"  Target   : {args.minutes} minutes")
    print(f"  Quality  : {args.quality}")
    print(f"  Mode     : {'plan-only' if args.plan_only else 'full pipeline'}")
    print(f"  Resume   : {resume}")
    if args.stage > 0:
        print(f"  Stage    : starting from {args.stage}")
    print(f"{'='*60}\n")

    result = run_pipeline(
        pdf_path=str(pdf_path),
        output_name=args.name,
        target_minutes=args.minutes,
        resume=resume,
        plan_only=args.plan_only,
        start_stage=args.stage,
        quality=args.quality,
        storyboard_model=args.storyboard_model,
        manim_model=args.manim_model,
    )

    if args.plan_only:
        print("\n📋 Review the storyboard, then run again without --plan-only to generate video:")
        print(f"   python run.py --pdf {args.pdf} --resume\n")
    else:
        print(f"\n🎬 Video ready: {result.get('output', 'unknown')}")
        print(f"   Total scenes: {result.get('total_scenes', '?')}")
        print(f"   Time taken: {result.get('elapsed_minutes', 0):.1f} minutes\n")


if __name__ == "__main__":
    main()
