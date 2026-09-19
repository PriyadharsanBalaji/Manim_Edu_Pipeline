"""
stages/manim_codegen.py — Stage 3: Generate Manim Python code via manim-coder model.

Takes each storyboard scene and generates executable Manim code using the
specialized maternion/manim-coder model (fine-tuned on 3blue1brown-manim dataset).

Features:
  - Self-healing: if code has syntax errors, retries with error context
  - Validates Python syntax before saving
  - Consistent class naming for easy rendering
"""

import ast
import json
import re
import time
from pathlib import Path

import ollama

from config import (
    OLLAMA_BASE_URL,
    MANIM_MODEL,
    MANIM_TEMPERATURE,
    MANIM_CODEGEN_MAX_RETRIES,
)


MANIM_SYSTEM = """You are an expert Manim Community Edition (ManimCE) programmer.
You generate clean, executable Python code that creates beautiful mathematical animations.

RULES:
1. Always import from manim: `from manim import *`
2. Use ONE class per scene, inheriting from Scene.
3. Class name MUST be named with the Scene_ Prefix followed by 3 digits (e.g. Scene_001, Scene_002).
4. Implement the construct(self) method.
5. Use self.play() for animations, self.wait() for pauses.
6. Use standard ManimCE objects: Text, MathTex, Tex, Circle, Square, Rectangle, Arrow, NumberLine, Axes, VGroup, etc.
7. Use raw strings for MathTex: MathTex(r"...")
8. Set background color in construct: self.camera.background_color = "#1a1a2e"
9. Avoid syntax errors, ensure all parentheses (), brackets [], and quotes "" are perfectly matched.
10. Manim coordinates MUST be 3D: [x, y, 0] or np.array([x, y, 0]). NEVER pass 2D points [x, y].
11. Polygon vertices: Use polygon.get_vertices()[i]. NEVER call .get_edge(i).
12. NEVER load external image files or ImageMobject("path.jpg"). Always use pure vector Mobjects (Rectangle, Text, etc.).
13. Output ONLY executable Python code inside ```python ``` blocks."""


MANIM_PROMPT = """Generate a Manim scene for this educational animation:

SCENE ID: {scene_id} (class name MUST be Scene_{scene_id_padded})
TITLE: {title}
DURATION: ~{duration}s of animation

NARRATION (what the voiceover says — animate in sync with this):
{narration}

VISUAL DESCRIPTION (what the viewer should see):
{visual_description}

MANIM INTENT (specific animation instructions):
{manim_intent}

KEY OBJECTS TO USE: {key_objects}

ON-SCREEN TEXT/EQUATIONS:
{on_screen_text}

BACKGROUND COLOR: {bg_color}
ACCENT COLORS: {accent_colors}

Generate the complete Python file inside a ```python ``` block. Remember:
- Class name: Scene_{scene_id_padded}
- from manim import *
- Beautiful, smooth animations
- Clean positioning (use .to_edge(), .shift(), .next_to())
- Match the narration timing with self.wait() calls"""


MANIM_FIX_PROMPT = """The previous Manim code failed during execution. Please fix all syntax and execution errors.

CRITICAL MANIM FIX RULES:
1. If error is "could not broadcast input array from shape (1,2) into shape (1,3)": Change ALL 2D points [x, y] or np.array([x, y]) to 3D points [x, y, 0] or np.array([x, y, 0]).
2. If error is "unsupported operand type(s) for /: Tex and int": Move division inside shift, e.g. .shift((p1 + p2) / 2) instead of .shift(p1 + p2) / 2.
3. If error mentions "get_edge": Replace object.get_edge(i) with object.get_vertices()[i] or .next_to(object, UP).
4. If error mentions "could not find image file" or ImageMobject: Replace ImageMobject(...) with VGroup(Rectangle(height=3.5, width=5, color=BLUE_B, fill_opacity=0.2), Text("Map Visualization", font_size=24, color=WHITE)).
5. Ensure all LaTeX in MathTex is valid and uses raw strings r"..."
6. Ensure class name is Scene_{scene_id_padded}

ORIGINAL SCENE INTENT:
{intent}

PREVIOUS BROKEN CODE:
```python
{previous_code}
```

ERROR / TRACEBACK:
{error}

Fix all errors and return the corrected complete Python file inside a ```python ``` block. Same class name: Scene_{scene_id_padded}."""


def generate_all_scenes(
    storyboard: dict,
    output_dir: str,
    state_file: str = None,
    model: str = None,
) -> dict:
    """
    Generate Manim code for all storyboard scenes.

    Args:
        storyboard: Output from storyboard_planner.plan_storyboard()
        output_dir: Directory to save .py files
        state_file: Path to JSON state file for resumability
        model: Override manim-coder model

    Returns:
        dict mapping scene_id -> .py file path
    """
    model = model or MANIM_MODEL
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load existing state for resumability
    state = {}
    if state_file and Path(state_file).exists():
        with open(state_file) as f:
            state = json.load(f)

    client = ollama.Client(host=OLLAMA_BASE_URL)
    scene_files = {}
    total_scenes = 0

    # Collect all scenes across sections
    all_scenes = []
    for section in storyboard.get("sections", []):
        for scene in section.get("scenes", []):
            all_scenes.append(scene)

    print(f"[ManimCodegen] Generating code for {len(all_scenes)} scenes with {model}...")

    for i, scene in enumerate(all_scenes):
        scene_id = scene.get("global_scene_id", scene.get("scene_id", i + 1))
        scene_id_padded = f"{scene_id:03d}"
        py_file = output_dir / f"scene_{scene_id_padded}.py"

        # Skip if already done (resumability)
        if str(scene_id) in state and state[str(scene_id)].get("status") == "done":
            if py_file.exists():
                print(f"  [{scene_id_padded}] Already done, skipping")
                scene_files[scene_id] = str(py_file)
                continue

        print(f"\n  [{scene_id_padded}/{len(all_scenes):03d}] {scene.get('title', 'Untitled')}...")

        code = _generate_scene_code(
            client=client,
            model=model,
            scene=scene,
            scene_id=scene_id,
        )

        if code:
            with open(py_file, "w", encoding="utf-8") as f:
                f.write(code)
            scene_files[scene_id] = str(py_file)
            total_scenes += 1

            # Update state
            state[str(scene_id)] = {"status": "done", "file": str(py_file)}
        else:
            state[str(scene_id)] = {"status": "failed"}
            print(f"    ✗ Failed to generate valid code")

        # Save state after each scene
        if state_file:
            Path(state_file).parent.mkdir(parents=True, exist_ok=True)
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)

        # Small delay to avoid overwhelming Ollama
        time.sleep(0.5)

    print(f"\n[ManimCodegen] ✓ {total_scenes}/{len(all_scenes)} scenes generated")
    return scene_files


def _generate_scene_code(
    client: ollama.Client,
    model: str,
    scene: dict,
    scene_id: int,
) -> str | None:
    """
    Generate Manim code for a single scene with self-healing retry.

    Returns valid Python code string or None if all retries fail.
    """
    scene_id_padded = f"{scene_id:03d}"

    on_screen_text = scene.get("on_screen_text", [])
    if isinstance(on_screen_text, list):
        on_screen_text = "\n".join(f"  - {t}" for t in on_screen_text)

    key_objects = scene.get("key_objects", [])
    if isinstance(key_objects, list):
        key_objects = ", ".join(key_objects)

    prompt = MANIM_PROMPT.format(
        scene_id=scene_id,
        scene_id_padded=scene_id_padded,
        title=scene.get("title", "Untitled"),
        duration=scene.get("duration_seconds", 30),
        narration=scene.get("narration_text", ""),
        visual_description=scene.get("visual_description", ""),
        manim_intent=scene.get("manim_intent", ""),
        key_objects=key_objects,
        on_screen_text=on_screen_text or "(none)",
        bg_color=scene.get("background_color", "#1a1a2e"),
        accent_colors=", ".join(scene.get("accent_colors", ["#e94560", "#0f3460"])),
    )

    for attempt in range(MANIM_CODEGEN_MAX_RETRIES):
        try:
            if attempt == 0:
                response = client.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": MANIM_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    options={"temperature": MANIM_TEMPERATURE, "num_predict": 4096},
                )
            else:
                # Self-healing: send error context
                fix_prompt = MANIM_FIX_PROMPT.format(
                    intent=scene.get("manim_intent", ""),
                    previous_code=last_code,
                    error=last_error,
                    scene_id_padded=scene_id_padded,
                )
                response = client.chat(
                    model=model,
                    messages=[
                        {"role": "system", "content": MANIM_SYSTEM},
                        {"role": "user", "content": fix_prompt},
                    ],
                    options={"temperature": MANIM_TEMPERATURE, "num_predict": 4096},
                )

            code = _extract_code(response["message"]["content"])

            # Validate Python syntax
            valid, error = _validate_python(code)
            if valid:
                # Ensure correct class name
                code = _ensure_class_name(code, scene_id_padded)
                print(f"    ✓ Generated ({len(code)} chars, attempt {attempt + 1})")
                return code
            else:
                last_code = code
                last_error = error
                print(f"    ⟳ Syntax error (attempt {attempt + 1}): {error[:80]}")

        except Exception as e:
            last_code = ""
            last_error = str(e)
            print(f"    ⟳ Error (attempt {attempt + 1}): {e}")

    return None


def _extract_code(text: str) -> str:
    """Extract Python code from LLM response, stripping markdown fences."""
    # Try to find code block
    match = re.search(r"```(?:python)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # If no code block, the whole response might be code
    text = text.strip()
    if text.startswith("from manim") or text.startswith("import"):
        return text

    # Try removing any leading non-code text
    lines = text.split("\n")
    code_start = None
    for i, line in enumerate(lines):
        if line.strip().startswith(("from manim", "import ", "class ")):
            code_start = i
            break

    if code_start is not None:
        return "\n".join(lines[code_start:])

    return text


def _validate_python(code: str) -> tuple[bool, str]:
    """Validate Python syntax. Returns (is_valid, error_message)."""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"


def _ensure_class_name(code: str, scene_id_padded: str) -> str:
    """Ensure the Scene class has the correct name and fix common coordinate bugs."""
    expected = f"Scene_{scene_id_padded}"

    # Find class definition
    match = re.search(r"class\s+(\w+)\s*\(", code)
    if match:
        current_name = match.group(1)
        if current_name != expected:
            code = code.replace(f"class {current_name}(", f"class {expected}(")

    # Auto-fix 2D vs 3D point coordinate bugs
    code = _auto_fix_common_manim_bugs(code)

    return code


def _auto_fix_common_manim_bugs(code: str) -> str:
    """Auto-fix common 2D vs 3D point coordinate bugs, operator precedence, invalid methods, and ImageMobject in Manim code."""
    # Convert 2D numpy arrays np.array([x, y]) -> np.array([x, y, 0])
    code = re.sub(r'np\.array\(\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]\s*\)', r'np.array([\1, \2, 0])', code)
    # Convert 2D point lists [x, y] in Dot/Line/Vector/Arrow -> [x, y, 0]
    code = re.sub(r'\b(Dot|Point|Line|Vector|Arrow)\(\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*\]', r'\1([\2, \3, 0]', code)
    # Fix Tex/Mobject division outside shift: .shift(a + b) / 2 -> .shift((a + b) / 2)
    code = re.sub(r'\.shift\(([^()]+(?:\([^()]*\)[^()]*)*)\)\s*/\s*(\d+(?:\.\d+)?)', r'.shift((\1) / \2)', code)
    # Fix invalid get_edge(n) call on Mobjects -> get_vertices()[n]
    code = re.sub(r'\.get_edge\(\s*(\d+)\s*\)', r'.get_vertices()[\1]', code)
    # Replace ImageMobject("...") with vector VGroup box
    code = re.sub(r'ImageMobject\s*\(\s*(?:"[^"]*"|\'[^\']*\'|[^)]+)\s*\)', r'VGroup(Rectangle(height=3.5, width=5, color=BLUE_B, fill_opacity=0.2), Text("Visualization", font_size=24, color=WHITE))', code)
    return code


def generate_single_scene(
    scene: dict,
    scene_id: int,
    output_path: str,
    model: str = None,
) -> str | None:
    """Generate code for a single scene (useful for testing)."""
    model = model or MANIM_MODEL
    client = ollama.Client(host=OLLAMA_BASE_URL)

    code = _generate_scene_code(client, model, scene, scene_id)
    if code and output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(code)
    return code


def fix_scene_code(
    scene: dict,
    scene_id: int,
    output_path: str,
    render_error: str,
    model: str = None,
) -> str | None:
    """
    Self-healing: take broken Python code + exact render error traceback
    and generate a fixed Python file using manim-coder.
    """
    model = model or MANIM_MODEL
    client = ollama.Client(host=OLLAMA_BASE_URL)
    scene_id_padded = f"{scene_id:03d}"

    previous_code = ""
    if Path(output_path).exists():
        with open(output_path, "r", encoding="utf-8") as f:
            previous_code = f.read()

    fix_prompt = MANIM_FIX_PROMPT.format(
        intent=scene.get("manim_intent", ""),
        previous_code=previous_code or "(no previous code)",
        error=render_error[-1000:],
        scene_id_padded=scene_id_padded,
    )

    try:
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": MANIM_SYSTEM},
                {"role": "user", "content": fix_prompt},
            ],
            options={"temperature": MANIM_TEMPERATURE, "num_predict": 4096},
        )
        code = _extract_code(response["message"]["content"])
        valid, error = _validate_python(code)
        if valid:
            code = _ensure_class_name(code, scene_id_padded)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"    [Self-heal] Fixed code written to {output_path}")
            return code
        else:
            print(f"    [Self-heal] Fix attempt had syntax error: {error[:80]}")
    except Exception as e:
        print(f"    [Self-heal] Failed to fix scene: {e}")

    return None
