"""
config.py — Central configuration for the Manim Educational Video Pipeline.

Two Ollama models:
  - STORYBOARD_MODEL: general-purpose LLM for analysis + storyboard planning
  - MANIM_MODEL: specialized manim-coder for generating Manim Python code
"""

import os

# ── Ollama settings ──────────────────────────────────────────────────────────
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

# Storyboard planning model (needs strong reasoning + structured JSON output)
# Override: STORYBOARD_MODEL=qwen2.5:14b
STORYBOARD_MODEL = os.environ.get("STORYBOARD_MODEL", "qwen2.5:14b")

# Manim code generation model (fine-tuned on 3blue1brown dataset)
MANIM_MODEL = os.environ.get("MANIM_MODEL", "maternion/manim-coder")

# ── LLM generation parameters ───────────────────────────────────────────────
STORYBOARD_TEMPERATURE = float(os.environ.get("STORYBOARD_TEMPERATURE", "0.7"))
MANIM_TEMPERATURE = float(os.environ.get("MANIM_TEMPERATURE", "0.3"))

# ── Scene & video settings ──────────────────────────────────────────────────
# Target duration per scene in seconds (Manim scenes are flexible: 45-60s)
DEFAULT_SCENE_DURATION = int(os.environ.get("DEFAULT_SCENE_DURATION", "60"))

# Target total video duration range (minutes)
TARGET_MIN_MINUTES = int(os.environ.get("TARGET_MIN_MINUTES", "30"))
TARGET_MAX_MINUTES = int(os.environ.get("TARGET_MAX_MINUTES", "60"))

# Manim render quality: l (low/480p), m (medium/720p), h (high/1080p), k (4K)
MANIM_QUALITY = os.environ.get("MANIM_QUALITY", "m")

# ── Retry settings ───────────────────────────────────────────────────────────
MANIM_CODEGEN_MAX_RETRIES = int(os.environ.get("MANIM_CODEGEN_MAX_RETRIES", "3"))
MANIM_RENDER_MAX_RETRIES = int(os.environ.get("MANIM_RENDER_MAX_RETRIES", "4"))

# ── Crossfade / assembly ────────────────────────────────────────────────────
CROSSFADE_DURATION = float(os.environ.get("CROSSFADE_DURATION", "0.5"))

# ── Output ───────────────────────────────────────────────────────────────────
DEFAULT_OUTPUT_DIR = os.environ.get("OUTPUT_DIR", "outputs")


def calc_target_scenes(target_minutes: int = 45, avg_scene_seconds: int = DEFAULT_SCENE_DURATION) -> int:
    """Calculate target number of scenes for given video duration."""
    return max(20, (target_minutes * 60) // avg_scene_seconds)
