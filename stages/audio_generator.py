"""
stages/audio_generator.py — Generate neural AI voiceovers for each storyboard scene.

Uses edge-tts (Microsoft Edge Neural Voices) for natural, human-like voiceovers.
Falls back to gTTS if edge-tts is unavailable.
"""

import asyncio
import json
import os
from pathlib import Path


DEFAULT_VOICE = "en-US-ChristopherNeural"  # Warm, clear educational voice


async def _generate_audio_edge(text: str, output_path: str, voice: str = DEFAULT_VOICE):
    """Generate audio using edge-tts (Microsoft Edge Neural TTS)."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)


def _generate_audio_gtts(text: str, output_path: str):
    """Fallback TTS using Google Text-to-Speech."""
    from gtts import gTTS
    tts = gTTS(text=text, lang="en", slow=False)
    tts.save(output_path)


def generate_scene_audio(
    storyboard: dict,
    output_dir: str,
    voice: str = DEFAULT_VOICE,
    state_file: str = None,
) -> dict:
    """
    Generate audio voiceover MP3 files for all storyboard scenes.

    Args:
        storyboard: Storyboard dictionary
        output_dir: Directory to save scene audio MP3s
        voice: Voice identifier for edge-tts
        state_file: Path to state tracking JSON

    Returns:
        Dict mapping scene_id -> mp3 file path
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    state = {}
    if state_file and Path(state_file).exists():
        with open(state_file, encoding="utf-8") as f:
            state = json.load(f)

    all_scenes = []
    for section in storyboard.get("sections", []):
        for scene in section.get("scenes", []):
            all_scenes.append(scene)

    audio_files = {}
    print(f"[AudioGenerator] Generating voiceover audio for {len(all_scenes)} scenes...")

    for i, scene in enumerate(all_scenes):
        scene_id = scene.get("global_scene_id", scene.get("scene_id", i + 1))
        scene_id_padded = f"{scene_id:03d}"
        mp3_path = output_dir / f"scene_{scene_id_padded}.mp3"
        narration = scene.get("narration_text", "").strip()

        if not narration:
            narration = scene.get("title", f"Scene {scene_id}")

        # Skip if already generated
        if str(scene_id) in state and state[str(scene_id)].get("status") == "done":
            if mp3_path.exists():
                print(f"  [{scene_id_padded}] Audio already exists, skipping")
                audio_files[scene_id] = str(mp3_path)
                continue

        print(f"  [{scene_id_padded}/{len(all_scenes):03d}] Generating voiceover ({len(narration.split())} words)...")

        success = False
        try:
            # Try edge-tts first (high-quality neural voice)
            asyncio.run(_generate_audio_edge(narration, str(mp3_path), voice))
            success = True
        except Exception as e:
            print(f"    ⟳ edge-tts failed ({e}), trying gTTS fallback...")
            try:
                _generate_audio_gtts(narration, str(mp3_path))
                success = True
            except Exception as e2:
                print(f"    ✗ Voiceover generation failed: {e2}")

        if success and mp3_path.exists():
            audio_files[scene_id] = str(mp3_path)
            state[str(scene_id)] = {"status": "done", "file": str(mp3_path)}
        else:
            state[str(scene_id)] = {"status": "failed"}

        if state_file:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)

    print(f"[AudioGenerator] ✓ {len(audio_files)}/{len(all_scenes)} voiceovers generated in {output_dir}")
    return audio_files
