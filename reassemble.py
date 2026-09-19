import sys
import json
from pathlib import Path

from config import CROSSFADE_DURATION
from stages.assembler import assemble_video

def main():
    base_dir = Path(r"C:\Users\DELL\Downloads\outputs (1)\outputs\arithmeticexp")
    clips_dir = base_dir / "clips_with_audio"
    storyboard_file = base_dir / "storyboard.json"
    final_output = base_dir / "final_arithmeticexp.mp4"

    if not clips_dir.exists():
        print(f"Error: {clips_dir} not found.")
        sys.exit(1)

    with open(storyboard_file, encoding="utf-8") as f:
        storyboard = json.load(f)

    # Collect combined clips
    combined_files = {}
    for clip_path in sorted(clips_dir.glob("scene_*_audio.mp4")):
        # Extract scene ID, assuming format scene_000_audio.mp4
        scene_id_str = clip_path.stem.split("_")[1]
        scene_id = str(int(scene_id_str)) # remove leading zeros to match original scene_id keys
        combined_files[scene_id] = str(clip_path)

    print(f"Found {len(combined_files)} clips in {clips_dir}")

    # Assemble video
    final_path = assemble_video(
        rendered_files=combined_files,
        storyboard=storyboard,
        output_path=str(final_output),
        crossfade=CROSSFADE_DURATION,
        add_section_cards=True,
    )
    
    print(f"\nAssembly complete! Re-generated final video with audio at:\n{final_path}")

if __name__ == "__main__":
    main()
