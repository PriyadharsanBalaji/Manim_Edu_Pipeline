# 🎬 Manim Educational Video Pipeline: Deep Dive Architecture

This document provides a comprehensive, technically exhaustive explanation of the Manim Educational Video Pipeline. It explains exactly **how** each stage operates under the hood (including specific Regex patterns and self-healing mechanics), alongside the exact **Inputs**, **LLM Payloads**, and **Output Structures**.

---

## 🏗️ Pipeline Overview
The pipeline is orchestrated by `pipeline.py` and uses **Ollama** (local LLMs) and **ManimCE** to automatically convert educational PDFs into 3Blue1Brown-style animated videos. It heavily relies on state tracking (`.json` files for each stage) to allow the pipeline to resume seamlessly if interrupted.

---

## 🛠️ Stage 0: PDF Text Extraction (`pdf_extractor.py`)
**Goal:** Parse unstructured PDF text into structured JSON elements.

- **📥 INPUT:** A raw `.pdf` file (e.g., `iemh101.pdf`).
- **⚙️ PROCESS (Heuristics & Regex):** 
  Uses `PyMuPDF` to read text page-by-page. It uses strict Regex patterns to scrape NCERT-style content:
  - **Chapter Title Detection:** 
    1. Looks for traditional patterns: `(?:Chapter|CHAPTER)\s*(\d+)\s*\n+\s*([A-Z][A-Z\s]+)` (e.g., "Chapter 1\nSETS").
    2. Fallback for new NCERT format: Grabs the first 2000 chars, isolates text appearing *before* `\d+\.\d+\s+Introduction`, and filters out copyright tags (`©`, `NCERT`).
  - **Section Parsing:** Uses regex `^(\d+\.\d+(?:\.\d+)?)\s+([A-Z][^\n]{3,80})` to capture headers like "1.1 Introduction" or "1.2.1 Subset" and chunks the text accordingly.
  - **Definitions:** 
    1. Keyword match: `(?:Definition|DEFINITION)[:\s]*\n?(.*?)(?:\n\n|\n(?=\d+\.\d+))`
    2. Semantic match: `(?:A|An|The)\s+\w+\s+is\s+(?:defined as|said to be|called)\s+[^.]+\.` (e.g., "A set is defined as...")
  - **Examples:** Captures blocks using `(?:Example|EXAMPLE)\s+(\d+)\s*(.*?)(?=(?:Example|EXAMPLE)\s+\d+|(?:EXERCISE|Exercise)\s+\d+|\Z)`.
  - **Exercises:** Captures blocks using `(?:EXERCISE|Exercise)\s+(\d+\.\d+)\s*(.*?)(?=(?:EXERCISE|Exercise)\s+\d+\.\d+|\Z)`.
- **📤 OUTPUT:** `chapter_content.json`
  ```json
  {
    "filename": "iemh101.pdf",
    "num_pages": 32,
    "chapter_title": "Chapter 1: Sets",
    "full_text": "Raw text of the entire chapter...",
    "sections": [
      {
        "number": "1.1",
        "title": "Introduction",
        "content": "Section text...",
        "content_length": 1500
      }
    ],
    "definitions": ["A set is a well-defined collection of objects."],
    "examples": [{"number": 1, "content": "Write the solution set of..."}],
    "exercises": ["EXERCISE 1.1..."],
    "raw_pages": [{"page": 1, "text": "..."}]
  }
  ```

---

## 🧠 Stage 1: Deep Concept Analysis (`deep_analyzer.py`)
**Goal:** Expand the raw textbook text into a rich pedagogical script (history, fun facts, exam tricks).

- **📥 INPUT:** `chapter_content.json` from Stage 0.
- **🤖 LLM INPUT (Payload):**
  The LLM (`qwen2.5:14b`) receives a system prompt acting as an expert Indian curriculum educational analyst. The user prompt is injected with:
  - `chapter_text`: The `full_text` from the PDF, truncated to ~30,000 characters to fit the context window safely.
  - `sections_summary`: Bulleted list of section numbers and titles.
  - `definitions_summary` & `examples_summary`.
- **⚙️ PROCESS (Robust JSON & Self-Correction):** 
  The LLM is strictly instructed to return a specific JSON schema covering ancient history, core concepts, misconceptions, and worked examples.
  - **Error Handling:** If the LLM hallucinates broken JSON (missing commas, unescaped quotes), a custom `_robust_json_parse()` algorithm attempts to automatically patch it. It uses regex to inject missing commas between objects (`\}(\n)\{` -> `},{`) and balances brackets/braces `[ { } ]`.
  - **Self-Healing:** If parsing still fails, the script passes the error back to the LLM to self-correct up to 3 times.
- **📤 OUTPUT:** `deep_analysis.json`
  ```json
  {
    "chapter_title": "Sets",
    "subject": "Mathematics",
    "grade": "Class 11",
    "ancient_history": [
      {
        "era": "19th Century",
        "person": "Georg Cantor",
        "event": "Developed set theory...",
        "fun_angle": "He faced heavy resistance..."
      }
    ],
    "core_concepts": [
      {
        "name": "Roster Form",
        "definition": "Listing all elements separated by commas...",
        "notation": "{1, 2, 3}",
        "intuition": "Like a grocery list...",
        "visual_idea": "A box with items dropping into it..."
      }
    ],
    "misconceptions": [...],
    "fun_facts": [...],
    "tricks_and_shortcuts": [...],
    "worked_examples": [...],
    "chapter_flow": ["Introduction", "Roster Form", "Set-Builder Form..."]
  }
  ```

---

## 📝 Stage 2: Storyboard Generation (`storyboard_planner.py`)
**Goal:** Transform the deep pedagogical analysis into a scene-by-scene director's cut.

- **📥 INPUT:** `deep_analysis.json` from Stage 1.
- **🤖 LLM INPUT (Payload):**
  The LLM acts as an award-winning 3B1B-style director. The prompt includes:
  - `target_min` / `target_max`: Target duration (e.g. 30-60 min).
  - `target_scenes`: Calculated mathematically (e.g., 45 minutes = ~45 scenes at 60s/scene).
  - `analysis_json`: A trimmed down version of `deep_analysis.json` to fit context limits.
  - `chapter_flow`: The ordered list of topics.
- **⚙️ PROCESS (Pedagogical Arc):** 
  The LLM maps out a strict arc: Hook -> History -> Core Concepts -> Misconceptions -> Examples. It is forced to define explicit `manim_intent` (specific classes like `MathTex`, `VGroup`, `FadeIn`) and `narration_text` for every scene. Finally, it assigns a `global_scene_id` (1 to N) to every scene.
- **📤 OUTPUT:** `storyboard.json` (and a human-readable `STORYBOARD.md`)
  ```json
  {
    "title": "Sets: From Cantor's Paradox to Your Exam Paper",
    "total_scenes": 45,
    "sections": [
      {
        "section_id": 1,
        "section_title": "The Story of Sets",
        "scenes": [
          {
            "global_scene_id": 1,
            "title": "Georg Cantor",
            "duration_seconds": 30,
            "narration_text": "In the late 19th century, Georg Cantor...",
            "visual_description": "A portrait of Cantor fades in...",
            "manim_intent": "FadeIn(ImageMobject(...)), Write(Text('Georg Cantor'))",
            "key_objects": ["Text", "ImageMobject"],
            "on_screen_text": ["Georg Cantor (1845-1918)"]
          }
        ]
      }
    ]
  }
  ```

---

## 💻 Stage 3: Manim Code Generation (`manim_codegen.py`)
**Goal:** Translate the storyboard's "manim_intent" into executable Python code.

- **📥 INPUT:** `storyboard.json` (specifically the individual scene dictionaries).
- **🤖 LLM INPUT (Payload):**
  The system switches to the `maternion/manim-coder` model (fine-tuned for ManimCE). For *every single scene*, it is prompted with the Scene ID, Title, Duration, Narration, Visual Description, and Manim Intent.
- **⚙️ PROCESS (AST Validation & Auto-Fixing):** 
  1. The LLM generates Python code wrapped in Markdown fences.
  2. The script extracts the code and runs Python's built-in **Abstract Syntax Tree (`ast.parse()`)** to check for syntax errors before saving.
  3. **Regex Auto-Fixer:** It runs a regex sanitization pass to automatically fix known LLM hallucinations without needing another API call:
     - Converts 2D arrays to 3D: `np.array([x, y])` -> `np.array([x, y, 0])`.
     - Fixes invalid `.get_edge(i)` calls to `.get_vertices()[i]`.
     - Replaces hallucinated `ImageMobject("file.jpg")` with vector rectangles.
     - Enforces the `class Scene_001(Scene):` naming convention using regex `class\s+(\w+)\s*\(`.
- **📤 OUTPUT:** 
  - Individual python scripts: `scenes/scene_001.py`, `scenes/scene_002.py`
  - State tracker: `codegen_state.json`

---

## 🎥 Stage 4: Manim Rendering (`renderer.py`)
**Goal:** Execute the Python scripts to generate `.mp4` video files.

- **📥 INPUT:** The `.py` files from Stage 3.
- **⚙️ PROCESS (Traceback Self-Healing):** 
  1. Invokes the `manim` CLI (`manim render -qm script.py Scene_001`) via `subprocess`. 
  2. **Self-Healing Loop:** If rendering crashes (e.g., invalid Manim logic or LaTeX failure), the script extracts the raw Python Traceback from stderr. It explicitly filters out generic noise (`click/entrypoint`, `scene_file_writer.py`) to isolate the exact error.
- **🤖 LLM INPUT (Fix Payload):** 
  It sends a `MANIM_FIX_PROMPT` back to the LLM containing the original intent, the broken code, and the extracted traceback. The LLM rewrites the code, and the renderer retries (up to 4 times).
- **📤 OUTPUT:** 
  - Individual MP4 clips: `renders/scene_001.mp4`, `renders/scene_002.mp4`
  - State tracker: `render_state.json`

---

## 🗣️ Stage 4.5: Voiceover Audio Generation (`audio_generator.py`)
**Goal:** Generate human-like narration for the scenes.

- **📥 INPUT:** The `narration_text` string from each scene in `storyboard.json`.
- **⚙️ PROCESS:** 
  The pipeline prioritizes natural, human-like voice synthesis using Microsoft's Edge Neural TTS service, with a robust fallback to Google's standard TTS.
  1. **Primary Model (`edge-tts`):** 
     - **What it is:** A reverse-engineered Python wrapper around Microsoft Edge's "Read Aloud" feature. It taps directly into Microsoft Azure's highly advanced Neural Text-to-Speech API without requiring an API key.
     - **The Voice (`en-US-ChristopherNeural`):** The default voice is explicitly configured to `Christopher`. This is a neural (AI-driven) voice model specifically chosen for educational content. Unlike robotic legacy TTS, Neural models use deep learning (transformers) to predict pacing, intonation, and emphasis based on the context of the sentence. "Christopher" provides a warm, clear, and professional American male voice that mimics the engaging style of popular YouTube educators.
     - **Execution:** It runs asynchronously (`asyncio.run()`) to efficiently fetch the audio chunks over the network and write them to an MP3 file.
  2. **Fallback Model (`gTTS`):**
     - **What it is:** Google Text-to-Speech (Google Translate's voice engine).
     - **Why it's there:** If Microsoft blocks the undocumented Edge API, or if there are network timeouts, `edge-tts` will throw an exception. The pipeline catches this and gracefully falls back to `gTTS`. While `gTTS` uses an older, less expressive concatenative TTS model, it ensures the pipeline never crashes and the video always gets its audio track.
- **📤 OUTPUT:** 
  - Individual MP3 audio tracks: `audio/scene_001.mp3`, `audio/scene_002.mp3`
  - State tracker: `audio_state.json`

---

## 🎬 Stage 5: Video Assembly & Audio Merging (`assembler.py`)
**Goal:** Stitch the disparate video clips and audio tracks into a final, seamless video.

- **📥 INPUT:** `renders/scene_XXX.mp4` and `audio/scene_XXX.mp3`
- **⚙️ PROCESS (FFmpeg Filter Chains):** 
  1. **Merge:** Uses FFmpeg to multiplex the audio track into the video track (`scene_001_audio.mp4`). It uses `-c:v copy` for lossless video copying and `-shortest` to truncate the video/audio to whichever ends first.
  2. **Assembly Strategy Check:**
     - **Lossless Concat:** If crossfade is disabled (or > 50 clips, which breaks FFmpeg's filter chain limit), it uses the **FFmpeg Concat Demuxer**. It writes a `concat_list.txt` file and losslessly stitches them together instantly (`-c copy`).
     - **Crossfade Engine:** If crossfade is enabled, it dynamically builds a massive `filter_complex` string using `xfade` (for video transitions) and `acrossfade` (for audio crossfades). It calculates precise time offsets using `ffprobe` to determine where the overlap should occur. This requires a full re-encode (`-c:v libx264`).
  3. **Error Fallback:** If the complex crossfade filter fails, it falls back to the safe, lossless Concat Demuxer.
- **📤 OUTPUT:** Final merged video (e.g., `outputs/iemh101/final_iemh101.mp4`).
