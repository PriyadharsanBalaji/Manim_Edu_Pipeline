import os
import sys
import time
import subprocess
import traceback
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from pipeline import run_pipeline
from config import STORYBOARD_MODEL, MANIM_MODEL

def pull_models():
    """Ensure required Ollama models are pulled."""
    print("============================================================")
    print(" Pulling required Ollama models...")
    print("============================================================")
    models = [STORYBOARD_MODEL, MANIM_MODEL]
    for model in models:
        try:
            print(f"Pulling {model}...")
            # We don't want to block forever if ollama server isn't running, but subprocess should handle it.
            result = subprocess.run(["ollama", "pull", model], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Successfully pulled (or already have) {model}")
            else:
                print(f"Warning: Failed to pull {model}. Output:\n{result.stderr}")
        except Exception as e:
            print(f"Warning: Could not run ollama pull for {model}. Is Ollama installed and running? Error: {e}")

import argparse

def main():
    parser = argparse.ArgumentParser(description="Batch run the Manim pipeline.")
    parser.add_argument("--first", type=str, help="Name of the PDF file to process first (e.g., 'Integers.pdf')")
    parser.add_argument("--whole-book", action="store_true", help="Chunk a large book to avoid context window issues")
    parser.add_argument("--iterations-per-book", type=int, default=1, help="Number of chunks to split the book into")
    args = parser.parse_args()

    print("\n" + "="*60)
    print("  Manim Educational Video Pipeline — Batch Runner")
    print("="*60 + "\n")

    # 1. Pull models
    pull_models()

    # 2. Find PDFs
    inputs_dir = Path("inputs")
    if not inputs_dir.exists():
        print(f"Error: Inputs directory '{inputs_dir.absolute()}' does not exist.")
        sys.exit(1)

    pdf_files = list(inputs_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {inputs_dir.absolute()}")
        sys.exit(0)

    # Prioritize the specified book if --first is provided
    if args.first:
        first_pdf = next((p for p in pdf_files if p.name.lower() == args.first.lower()), None)
        if first_pdf:
            pdf_files.remove(first_pdf)
            pdf_files.insert(0, first_pdf)
            print(f"Prioritizing {first_pdf.name} to run first.")
        else:
            print(f"Warning: Could not find '{args.first}' in inputs directory.")

    print(f"\nFound {len(pdf_files)} PDF(s) to process:\n" + "\n".join([f"  - {p.name}" for p in pdf_files]))

    # 3. Process each PDF
    successes = []
    failures = []

    for i, pdf_path in enumerate(pdf_files, 1):
        print(f"\n\n{'#'*60}")
        print(f" Processing {i}/{len(pdf_files)}: {pdf_path.name}")
        print(f"{'#'*60}\n")
        
        start_time = time.time()
        
        try:
            total_chunks = args.iterations_per_book if args.whole_book else 1
            part_videos = []
            actual_total = 1
            
            for chunk_idx in range(total_chunks):
                if total_chunks > 1:
                    print(f"\n--- Processing Chunk {chunk_idx + 1}/{total_chunks} ---")
                    output_name = f"{pdf_path.stem.lower().replace(' ', '_')}_part{chunk_idx + 1}"
                else:
                    output_name = pdf_path.stem.lower().replace(" ", "_")
                    
                result = run_pipeline(
                    pdf_path=str(pdf_path),
                    output_name=output_name,
                    target_minutes=45,       # default target
                    resume=True,             # resume if interrupted
                    plan_only=False,         # full run
                    start_stage=0,           # from beginning
                    quality="m",             # medium quality 720p
                    chunk_index=chunk_idx,
                    total_chunks=total_chunks,
                )
                
                if result and result.get("status") == "EOF":
                    actual_total = result.get("actual_total_chunks", 1)
                    print(f"\nℹ️ Reached end of book at chunk {chunk_idx}. Total required iterations to process the entire book: {actual_total}")
                    break
                
                if result and "output" in result:
                    part_videos.append(result["output"])
                    actual_total = result.get("actual_total_chunks", 1)
                    
            if total_chunks > 1 and part_videos:
                print(f"\nℹ️ NOTE: This book requires {actual_total} total iterations to process entirely. You requested {total_chunks} iterations, and we processed {len(part_videos)} chunks.")
                from stages.assembler import concat_final_videos
                final_output_path = str(Path("outputs") / f"final_{pdf_path.stem.lower().replace(' ', '_')}.mp4")
                print(f"\nConcatenating {len(part_videos)} parts into {final_output_path}...")
                concat_final_videos(part_videos, final_output_path)
                
            elapsed = time.time() - start_time
            print(f"\n✅ Successfully processed {pdf_path.name} in {elapsed/60:.1f} minutes")
            successes.append(pdf_path.name)
            
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ FAILED to process {pdf_path.name} after {elapsed/60:.1f} minutes")
            print("Error details:")
            traceback.print_exc()
            failures.append((pdf_path.name, str(e)))
            print("\nContinuing to the next PDF...")

    # 4. Summary
    print("\n" + "="*60)
    print(" BATCH RUN SUMMARY")
    print("="*60)
    print(f"Total processed: {len(pdf_files)}")
    print(f"Successes: {len(successes)}")
    print(f"Failures: {len(failures)}")
    
    if failures:
        print("\nFailed files:")
        for name, err in failures:
            print(f"  - {name}: {err}")
    
    print("\nBatch run completed.")

if __name__ == "__main__":
    main()
