# 🚀 Running Manim Edu Pipeline on Google Colab

Google Colab provides free T4 GPUs (15 GB VRAM) which easily run `qwen2.5:14b` and `maternion/manim-coder` without memory limits or local setup issues.

---

## Quick Start (3 Easy Methods)

### Method 1: Upload Zip & Run (Easiest)

1. **Zip the `manim_edu_pipeline` folder** on your computer.
2. Open [Google Colab](https://colab.research.google.com/).
3. Change runtime to GPU: `Runtime` -> `Change runtime type` -> `T4 GPU`.
4. Upload `manim_edu_pipeline.zip` to Colab files.
5. Unzip in a code cell:
   ```bash
   !unzip manim_edu_pipeline.zip
   %cd manim_edu_pipeline
   ```
6. Open `run_colab.ipynb` or run the setup commands below.

---

## Colab Commands Step-by-Step

### 1. Install System Dependencies & LaTeX (for Manim rendering)
```bash
!apt-get update -qq
!apt-get install -y -qq build-essential python3-dev libcairo2-dev libpango1.0-dev ffmpeg zstd texlive-latex-extra texlive-fonts-extra texlive-science tipa
```

### 2. Install Python Libraries
```bash
!pip install manim pymupdf ollama
```

### 3. Install & Start Ollama Server
```bash
!curl -fsSL https://ollama.com/install.sh | sh

import subprocess, time
ollama_process = subprocess.Popen(["ollama", "serve"])
time.sleep(5)
```

### 4. Pull Ollama Models
```bash
!ollama pull maternion/manim-coder
!ollama pull qwen2.5:14b
```

### 5. Run Storyboard & Analysis Only (Review before rendering)
```bash
!python run.py --pdf iemh101.pdf --plan-only
```
To view the generated storyboard in Colab:
```python
from IPython.display import Markdown
with open("outputs/iemh101/STORYBOARD.md", "r") as f:
    display(Markdown(f.read()))
```

### 6. Run Full Generation (Code Gen -> Render -> Concatenate)
```bash
!python run.py --pdf iemh101.pdf --resume
```

### 7. Download Outputs
```python
!zip -r outputs_iemh101.zip outputs/iemh101/
from google.colab import files
files.download("outputs_iemh101.zip")
```

---

## 💡 Benefits of Colab for this Pipeline
- **15 GB VRAM (T4 GPU)** handles `qwen2.5:14b` and `maternion/manim-coder` effortlessly.
- **Fast rendering**: Manim renders much faster on Colab's multi-core CPUs + GPU.
- **Pre-installed utilities**: Linux FFmpeg and LaTeX compile cleanly.
