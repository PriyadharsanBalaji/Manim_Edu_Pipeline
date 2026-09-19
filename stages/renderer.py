"""
stages/renderer.py — Stage 4: Render Manim scenes to MP4 video clips.

Runs `manim render` on each generated .py file.
Features:
  - Resumable: skips already-rendered scenes
  - Error recovery: sends render errors back to manim-coder for code fixes
  - Configurable quality (low/medium/high/4K)
"""

import json
import subprocess
import sys
import time
from pathlib import Path

from config import (
    MANIM_QUALITY,
    MANIM_RENDER_MAX_RETRIES,
)


# Map quality flag to manim CLI flag
QUALITY_FLAGS = {
    "l": "-ql",   # 480p, 15fps
    "m": "-qm",   # 720p, 30fps
    "h": "-qh",   # 1080p, 60fps
    "k": "-qk",   # 4K, 60fps
}


def render_all_scenes(
    scene_files: dict,
    output_dir: str,
    state_file: str = None,
    quality: str = None,
    manim_codegen_fix_fn=None,
) -> dict:
    """
    Render all Manim scene files to MP4.

    Args:
        scene_files: dict mapping scene_id -> .py file path
        output_dir: Directory for rendered MP4 files
        state_file: JSON state file for resumability
        quality: Render quality override (l/m/h/k)
        manim_codegen_fix_fn: Optional callback(scene_id, py_path, error) -> fixed_py_path
            for self-healing code fixes on render failure

    Returns:
        dict mapping scene_id -> rendered .mp4 file path
    """
    quality = quality or MANIM_QUALITY
    quality_flag = QUALITY_FLAGS.get(quality, "-qm")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load state
    state = {}
    if state_file and Path(state_file).exists():
        with open(state_file) as f:
            state = json.load(f)

    # Find the manim executable in the venv
    venv_dir = Path(__file__).parent.parent / ".venv"
    if sys.platform == "win32":
        manim_exe = venv_dir / "Scripts" / "manim.exe"
    else:
        manim_exe = venv_dir / "bin" / "manim"

    if not manim_exe.exists():
        manim_exe = "manim"  # Fall back to system manim
        print(f"[Renderer] Using system manim (venv manim not found)")
    else:
        print(f"[Renderer] Using venv manim: {manim_exe}")

    rendered = {}
    total = len(scene_files)

    print(f"[Renderer] Rendering {total} scenes at quality={quality} ({quality_flag})...")

    for scene_id, py_path in sorted(scene_files.items(), key=lambda x: int(x[0])):
        scene_id_padded = f"{int(scene_id):03d}"
        mp4_file = output_dir / f"scene_{scene_id_padded}.mp4"

        # Skip if already rendered
        if str(scene_id) in state and state[str(scene_id)].get("status") == "rendered":
            if mp4_file.exists():
                print(f"  [{scene_id_padded}] Already rendered, skipping")
                rendered[scene_id] = str(mp4_file)
                continue

        print(f"\n  [{scene_id_padded}/{total:03d}] Rendering...")

        success = _render_scene(
            manim_exe=str(manim_exe),
            py_path=py_path,
            scene_id_padded=scene_id_padded,
            output_dir=output_dir,
            mp4_file=mp4_file,
            quality_flag=quality_flag,
            manim_codegen_fix_fn=manim_codegen_fix_fn,
            scene_id=scene_id,
        )

        if success and mp4_file.exists():
            rendered[scene_id] = str(mp4_file)
            state[str(scene_id)] = {"status": "rendered", "file": str(mp4_file)}
            print(f"    ✓ Rendered -> {mp4_file.name}")
        else:
            state[str(scene_id)] = {"status": "failed"}
            print(f"    ✗ Render failed")

        # Save state
        if state_file:
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)

    print(f"\n[Renderer] ✓ {len(rendered)}/{total} scenes rendered")
    return rendered


def _render_scene(
    manim_exe: str,
    py_path: str,
    scene_id_padded: str,
    output_dir: Path,
    mp4_file: Path,
    quality_flag: str,
    manim_codegen_fix_fn=None,
    scene_id=None,
) -> bool:
    """Render a single scene with retry on failure."""
    class_name = f"Scene_{scene_id_padded}"
    current_py = py_path

    for attempt in range(MANIM_RENDER_MAX_RETRIES):
        try:
            abs_py_path = str(Path(current_py).resolve())
            abs_media_dir = str(Path(output_dir / "media").resolve())

            cmd = [
                manim_exe,
                "render",
                quality_flag,
                "--media_dir", abs_media_dir,
                abs_py_path,
                class_name,
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(Path(current_py).parent.resolve()),
            )

            if result.returncode == 0:
                # Find the rendered file (manim puts it in a nested structure)
                rendered_file = _find_rendered_mp4(output_dir / "media", class_name)
                if rendered_file:
                    # Move to our output location
                    import shutil
                    shutil.move(str(rendered_file), str(mp4_file))
                    return True
                else:
                    print(f"    ⟳ Render succeeded but MP4 not found")

            else:
                full_log = ((result.stderr or "") + "\n" + (result.stdout or "")).strip()
                error = _extract_meaningful_error(full_log)
                print(f"\n  ⚠️ Render Error details for {class_name} (attempt {attempt + 1}):")
                print("  " + "\n  ".join(full_log.split("\n")[-15:]))
                print()

                # Try self-healing if callback provided
                if manim_codegen_fix_fn and attempt < MANIM_RENDER_MAX_RETRIES - 1:
                    fixed_path = manim_codegen_fix_fn(scene_id, current_py, error)
                    if fixed_path:
                        current_py = fixed_path
                        print(f"    ⟳ Code fixed, retrying render...")
                        continue

        except subprocess.TimeoutExpired:
            print(f"    ⟳ Render timed out (attempt {attempt + 1})")
        except Exception as e:
            print(f"    ⟳ Error (attempt {attempt + 1}): {e}")

    return False


def _find_rendered_mp4(media_dir: Path, class_name: str) -> Path | None:
    """Find the MP4 file rendered by Manim in its media directory structure (excluding partial movie files)."""
    if not media_dir.exists():
        return None

    # Manim puts final videos in media/videos/{filename}/{quality}/{ClassName}.mp4
    for mp4 in media_dir.rglob(f"{class_name}.mp4"):
        if "partial_movie_files" not in str(mp4):
            return mp4

    # Also check for partial matches outside partial_movie_files
    for mp4 in media_dir.rglob("*.mp4"):
        if "partial_movie_files" not in str(mp4) and class_name.lower() in mp4.stem.lower():
            return mp4

    return None


def render_single_scene(
    py_path: str,
    scene_id: int,
    output_path: str,
    quality: str = None,
) -> bool:
    """Render a single scene file (useful for testing)."""
    quality = quality or MANIM_QUALITY
    quality_flag = QUALITY_FLAGS.get(quality, "-qm")
    scene_id_padded = f"{scene_id:03d}"

    venv_dir = Path(__file__).parent.parent / ".venv"
    if sys.platform == "win32":
        manim_exe = venv_dir / "Scripts" / "manim.exe"
    else:
        manim_exe = venv_dir / "bin" / "manim"

    if not manim_exe.exists():
        manim_exe = "manim"
    else:
        manim_exe = str(manim_exe)

    return _render_scene(
        manim_exe=manim_exe,
        py_path=py_path,
        scene_id_padded=scene_id_padded,
        output_dir=Path(output_path).parent,
        mp4_file=Path(output_path),
        quality_flag=quality_flag,
    )


def _extract_meaningful_error(full_log: str) -> str:
    """
    Extract meaningful Python/Manim error traceback, excluding generic Click/entrypoint wrapper & progress lines.
    """
    lines = [l for l in full_log.split("\n") if l.strip()]
    filtered = []
    for l in lines:
        if any(x in l for x in ("dist-packages/click", "site-packages/click", "/usr/local/bin/manim", "sys.exit(main())", "Traceback (most recent call last)", "INFO  Animation", "partial_movie_files", "scene_file_writer.py")):
            continue
        filtered.append(l)
    clean = "\n".join(filtered).strip()
    return clean[-1500:] if clean else full_log[-800:]
