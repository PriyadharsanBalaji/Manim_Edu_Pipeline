#!/bin/bash
set -e

echo "============================================================"
echo " 1/6 Installing System Dependencies (FFmpeg, Cairo, TeX)..."
echo "============================================================"
apt-get update -qq
apt-get install -y -qq build-essential python3-dev libcairo2-dev libpango1.0-dev ffmpeg zstd dvisvgm texlive-latex-base texlive-latex-extra texlive-fonts-extra texlive-science tipa

echo "============================================================"
echo " 2/6 Installing Python Packages..."
echo "============================================================"
pip install manim pymupdf ollama edge-tts gTTS

echo "============================================================"
echo " 3/6 Installing & Starting Ollama Server..."
echo "============================================================"
curl -fsSL https://ollama.com/install.sh | sh
ollama serve > ollama.log 2>&1 &
sleep 5

echo "============================================================"
echo " 4/6 Pulling Models (maternion/manim-coder + qwen2.5:14b)..."
echo "============================================================"
ollama pull maternion/manim-coder
ollama pull qwen2.5:14b

echo "============================================================"
echo " 5/6 Running Educational Video Pipeline..."
echo "============================================================"
python run.py --pdf iemh101.pdf

echo "============================================================"
echo " 6/6 Packaging Outputs..."
echo "============================================================"
zip -r outputs_iemh101.zip outputs/iemh101/

echo "============================================================"
echo " ✅ ALL DONE! Output saved to outputs_iemh101.zip"
echo "============================================================"
