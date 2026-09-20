"""
stages/assembler.py — Stage 5: Assemble rendered scenes into final video.

Uses FFmpeg to concatenate MP4 clips with optional crossfade transitions
and section title cards.
"""

import subprocess
import sys
from pathlib import Path

from config import CROSSFADE_DURATION


def merge_scene_audio_video(
    rendered_files: dict,
    audio_files: dict,
    output_dir: str,
) -> dict:
    """
    Combine each rendered scene MP4 with its voiceover MP3 audio into a new MP4 clip.

    Args:
        rendered_files: dict mapping scene_id -> video .mp4 path
        audio_files: dict mapping scene_id -> voiceover .mp3 path
        output_dir: directory to save combined clips

    Returns:
        dict mapping scene_id -> combined .mp4 clip path
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ffmpeg = _find_ffmpeg()

    combined_clips = {}
    print(f"[Assembler] Merging voiceover audio into video clips...")

    for scene_id in sorted(rendered_files.keys(), key=lambda x: int(x)):
        video_path = rendered_files[scene_id]
        audio_path = audio_files.get(scene_id)
        scene_id_padded = f"{int(scene_id):03d}"
        output_clip = output_dir / f"scene_{scene_id_padded}_audio.mp4"

        if audio_path and Path(audio_path).exists() and Path(video_path).exists():
            # Combine video + audio using FFmpeg
            cmd = [
                ffmpeg, "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                str(output_clip),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0 and output_clip.exists():
                combined_clips[scene_id] = str(output_clip)
            else:
                combined_clips[scene_id] = video_path
        else:
            combined_clips[scene_id] = video_path

    print(f"[Assembler] ✓ {len(combined_clips)} video+audio clips ready")
    return combined_clips


def assemble_video(
    rendered_files: dict,
    storyboard: dict,
    output_path: str,
    crossfade: float = None,
    add_section_cards: bool = True,
) -> str:
    """
    Concatenate all rendered scene clips into a single video.

    Args:
        rendered_files: dict mapping scene_id -> .mp4 path
        storyboard: Storyboard dict (for section info)
        output_path: Final output .mp4 path
        crossfade: Crossfade duration in seconds (0 to disable)
        add_section_cards: Whether to add section title cards between sections

    Returns:
        Path to final output video
    """
    crossfade = crossfade if crossfade is not None else CROSSFADE_DURATION
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect clips in order
    clips = []
    for scene_id in sorted(rendered_files.keys(), key=lambda x: int(x)):
        mp4_path = rendered_files[scene_id]
        if Path(mp4_path).exists():
            clips.append(mp4_path)

    if not clips:
        raise RuntimeError("No rendered clips to assemble!")

    print(f"[Assembler] Assembling {len(clips)} clips -> {output_path}")

    if len(clips) == 1:
        # Single clip — just copy
        import shutil
        shutil.copy2(clips[0], str(output_path))
        print(f"[Assembler] ✓ Single clip copied -> {output_path}")
        return str(output_path)

    # Use FFmpeg concat demuxer (fastest, no re-encoding)
    concat_file = output_path.parent / "concat_list.txt"

    with open(concat_file, "w") as f:
        for clip in clips:
            # FFmpeg concat needs forward slashes and escaped single quotes
            safe_path = str(Path(clip).resolve()).replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    # Find ffmpeg
    ffmpeg = _find_ffmpeg()

    if crossfade > 0 and len(clips) <= 50:
        # Use filter_complex for crossfade (limited by FFmpeg's filter chain depth)
        _assemble_with_crossfade(ffmpeg, clips, str(output_path), crossfade)
    else:
        # Simple concat (fast, works for any number of clips)
        _assemble_concat(ffmpeg, str(concat_file), str(output_path))

    # Clean up
    concat_file.unlink(missing_ok=True)

    if output_path.exists():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"[Assembler] ✓ Final video: {output_path} ({size_mb:.1f} MB)")
    else:
        print(f"[Assembler] ✗ Assembly failed — output not found")

    return str(output_path)


def _assemble_concat(ffmpeg: str, concat_file: str, output_path: str) -> None:
    """Simple concatenation using FFmpeg concat demuxer."""
    cmd = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        output_path,
    ]

    print(f"[Assembler] Running concat (no re-encode)...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        # Fallback: re-encode if concat copy fails (codec mismatch)
        print(f"[Assembler] Concat copy failed, trying with re-encode...")
        cmd = [
            ffmpeg,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264",
            "-crf", "23",
            "-preset", "fast",
            "-c:a", "aac",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg assembly failed: {result.stderr[-300:]}")


def _get_clip_duration(filepath: str) -> float:
    """Get precise duration of a video clip using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", filepath
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception as e:
        print(f"[Assembler] Warning: failed to get duration for {filepath} ({e})")
    
    # Fallback if ffprobe fails or is not available
    return 25.0


def _assemble_with_crossfade(
    ffmpeg: str,
    clips: list[str],
    output_path: str,
    crossfade: float,
) -> None:
    """Concatenation with crossfade transitions between clips (Video + Audio)."""
    # Build filter_complex for xfade between consecutive clips
    inputs = []
    durations = []
    for clip in clips:
        inputs.extend(["-i", clip])
        durations.append(_get_clip_duration(clip))

    # Build xfade filter chain
    filter_parts = []
    current_v = "[0:v]"
    current_a = "[0:a]"
    acc_dur = durations[0]

    for i in range(1, len(clips)):
        # Video offset is absolute from the start of the accumulated video
        offset = max(0, acc_dur - crossfade)
        next_v = f"[{i}:v]"
        next_a = f"[{i}:a]"
        
        out_v = f"[v{i}]" if i < len(clips) - 1 else "[outv]"
        out_a = f"[a{i}]" if i < len(clips) - 1 else "[outa]"
        
        # Crossfade video
        filter_parts.append(
            f"{current_v}{next_v}xfade=transition=fade:duration={crossfade}:offset={offset}{out_v}"
        )
        # Crossfade audio
        filter_parts.append(
            f"{current_a}{next_a}acrossfade=d={crossfade}{out_a}"
        )
        
        current_v = out_v
        current_a = out_a
        acc_dur = acc_dur + durations[i] - crossfade

    filter_complex = ";".join(filter_parts)

    cmd = [
        ffmpeg, "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-crf", "23",
        "-preset", "fast",
        "-c:a", "aac",
        output_path,
    ]

    print(f"[Assembler] Running crossfade assembly ({len(clips)} clips)...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

    if result.returncode != 0:
        print(f"[Assembler] Crossfade failed: {result.stderr[-300:]}")
        print(f"[Assembler] Falling back to simple concat...")
        # Write concat file and use simple method
        concat_file = Path(output_path).parent / "concat_list.txt"
        with open(concat_file, "w") as f:
            for clip in clips:
                safe_path = str(Path(clip).resolve()).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")
        _assemble_concat(ffmpeg, str(concat_file), output_path)
        concat_file.unlink(missing_ok=True)


def concat_final_videos(video_paths: list[str], output_path: str) -> str:
    """Concatenate multiple final video parts into a single video."""
    if not video_paths:
        raise ValueError("No videos provided to concatenate.")
    if len(video_paths) == 1:
        import shutil
        shutil.copy2(video_paths[0], output_path)
        return output_path
    
    ffmpeg = _find_ffmpeg()
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    concat_file = output_path_obj.parent / "final_concat_list.txt"
    with open(concat_file, "w") as f:
        for clip in video_paths:
            safe_path = str(Path(clip).resolve()).replace("\\", "/")
            f.write(f"file '{safe_path}'\n")
            
    _assemble_concat(ffmpeg, str(concat_file), str(output_path_obj))
    concat_file.unlink(missing_ok=True)
    
    if output_path_obj.exists():
        size_mb = output_path_obj.stat().st_size / (1024 * 1024)
        print(f"[Assembler] ✓ Concatenated final video: {output_path_obj} ({size_mb:.1f} MB)")
    else:
        print(f"[Assembler] ✗ Final concatenation failed")
        
    return str(output_path)


def _find_ffmpeg() -> str:
    """Find ffmpeg executable."""
    # Check if ffmpeg is in PATH
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return "ffmpeg"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check common Windows locations
    if sys.platform == "win32":
        common_paths = [
            Path.home() / "scoop" / "shims" / "ffmpeg.exe",
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe"),
        ]
        for p in common_paths:
            if p.exists():
                return str(p)

    raise FileNotFoundError(
        "FFmpeg not found. Install it:\n"
        "  Windows: winget install ffmpeg\n"
        "  macOS: brew install ffmpeg\n"
        "  Linux: sudo apt install ffmpeg"
    )
