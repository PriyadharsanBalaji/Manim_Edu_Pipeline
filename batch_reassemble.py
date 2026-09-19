import sys
import json
import traceback
from pathlib import Path

from config import CROSSFADE_DURATION
from stages.assembler import assemble_video

def process_directory(base_dir: Path):
    print(f"\n{'='*60}")
    print(f"Processing: {base_dir.name}")
    print(f"{'='*60}")
    
    clips_dir = base_dir / "clips_with_audio"
    storyboard_file = base_dir / "storyboard.json"
    final_output = base_dir / f"final_{base_dir.name}.mp4"

    if not clips_dir.exists():
        print(f"  -> Skipping: 'clips_with_audio' not found.")
        return
    if not storyboard_file.exists():
        print(f"  -> Skipping: 'storyboard.json' not found.")
        return

    with open(storyboard_file, encoding="utf-8") as f:
        storyboard = json.load(f)

    # Collect combined clips
    combined_files = {}
    for clip_path in sorted(clips_dir.glob("scene_*_audio.mp4")):
        try:
            # Extract scene ID, assuming format scene_000_audio.mp4
            scene_id_str = clip_path.stem.split("_")[1]
            scene_id = str(int(scene_id_str)) # remove leading zeros
            combined_files[scene_id] = str(clip_path)
        except Exception as e:
            print(f"  -> Warning: Skipping {clip_path.name} due to parsing error.")

    if not combined_files:
        print(f"  -> Skipping: No clips found in {clips_dir}")
        return

    print(f"  -> Found {len(combined_files)} clips in {clips_dir.name}. Assembling...")

    try:
        # Assemble video
        final_path = assemble_video(
            rendered_files=combined_files,
            storyboard=storyboard,
            output_path=str(final_output),
            crossfade=CROSSFADE_DURATION,
            add_section_cards=True,
        )
        print(f"  -> Assembly complete! Output: {final_path}")
    except Exception as e:
        print(f"  -> ERROR during assembly of {base_dir.name}:")
        traceback.print_exc()

def main():
    outputs_dir = Path(r"C:\Users\DELL\Downloads\outputs (4)\outputs")
    
    if not outputs_dir.exists():
        print(f"Error: {outputs_dir} not found.")
        sys.exit(1)

    for item in outputs_dir.iterdir():
        if item.is_dir():
            process_directory(item)
            
    print("\nAll directories processed!")

if __name__ == "__main__":
    main()
