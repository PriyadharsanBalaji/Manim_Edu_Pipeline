"""
stages/pdf_extractor.py — Stage 0: Extract structured text from educational PDF.

Uses PyMuPDF to extract text, detect section headers, definitions, examples,
and exercises. Outputs a structured JSON ready for LLM consumption.

Usage:
    from stages.pdf_extractor import extract_pdf
    content = extract_pdf("iemh101.pdf", output_path="chapter_content.json")
"""

import json
import re
from pathlib import Path

import pymupdf


def extract_pdf(pdf_path: str, output_path: str = None) -> dict:
    """
    Extract structured text from a PDF educational document.

    Returns:
        dict with keys: filename, num_pages, chapter_title, full_text,
        sections[], raw_pages[]
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = pymupdf.open(str(pdf_path))
    print(f"[PDF] Opened {pdf_path.name} — {len(doc)} pages, {pdf_path.stat().st_size // 1024} KB")

    # ── Extract raw text per page ────────────────────────────────────────────
    raw_pages = []
    full_text_parts = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        raw_pages.append({
            "page": page_num + 1,
            "text": text.strip(),
        })
        full_text_parts.append(text)

    full_text = "\n".join(full_text_parts)
    doc.close()

    # ── Detect chapter title ─────────────────────────────────────────────────
    chapter_title = _detect_chapter_title(full_text)
    print(f"[PDF] Detected chapter: {chapter_title}")

    # ── Parse sections ───────────────────────────────────────────────────────
    sections = _parse_sections(full_text)
    print(f"[PDF] Found {len(sections)} sections")

    # ── Extract special elements ─────────────────────────────────────────────
    definitions = _extract_definitions(full_text)
    examples = _extract_examples(full_text)
    exercises = _extract_exercises(full_text)

    print(f"[PDF] Definitions: {len(definitions)}, Examples: {len(examples)}, Exercises: {len(exercises)}")

    result = {
        "filename": pdf_path.name,
        "num_pages": len(raw_pages),
        "chapter_title": chapter_title,
        "full_text": full_text,
        "sections": sections,
        "definitions": definitions,
        "examples": examples,
        "exercises": exercises,
        "raw_pages": raw_pages,
    }

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[PDF] Saved -> {output_path}")

    return result


def _detect_chapter_title(text: str) -> str:
    """Try to detect the chapter title from the beginning of the text."""
    # NCERT pattern: "Chapter 1\nSETS" or "CHAPTER 1\n\nSETS"
    match = re.search(
        r"(?:Chapter|CHAPTER)\s*(\d+)\s*\n+\s*([A-Z][A-Z\s]+)",
        text[:2000],
    )
    if match:
        num = match.group(1)
        title = match.group(2).strip().title()
        return f"Chapter {num}: {title}"

    # New NCERT format: title text appears before "1.1 Introduction"
    # Grab all text before the first section number
    pre_section = text[:2000]
    section_match = re.search(r"\d+\.\d+\s+Introduction", pre_section)
    if section_match:
        title_text = pre_section[:section_match.start()].strip()
        # Clean up: join lines, remove copyright/header junk
        lines = [l.strip() for l in title_text.split("\n") if l.strip() and len(l.strip()) > 2]
        lines = [l for l in lines if not l.startswith(("©", "NCERT", "http", "www"))]
        if lines:
            return " ".join(lines)

    # Fallback: first substantial line
    for line in text[:1000].split("\n"):
        line = line.strip()
        if len(line) > 5 and not line.startswith("©"):
            return line
    return "Unknown Chapter"


def _parse_sections(text: str) -> list[dict]:
    """
    Parse text into sections based on NCERT section numbering patterns.
    Looks for: "1.1 Introduction", "1.2 Sets and their Representations", etc.
    """
    # Pattern: digit.digit followed by title text
    section_pattern = re.compile(
        r"^(\d+\.\d+(?:\.\d+)?)\s+([A-Z][^\n]{3,80})",
        re.MULTILINE,
    )

    matches = list(section_pattern.finditer(text))
    if not matches:
        # Fallback: return entire text as single section
        return [{"number": "1.0", "title": "Full Chapter", "content": text[:5000]}]

    sections = []
    for i, match in enumerate(matches):
        number = match.group(1)
        title = match.group(2).strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start:end].strip()

        # Limit content length for JSON sanity
        sections.append({
            "number": number,
            "title": title,
            "content": content[:8000],
            "content_length": len(content),
        })

    return sections


def _extract_definitions(text: str) -> list[str]:
    """Extract definition blocks from NCERT text."""
    definitions = []

    # NCERT uses "Definition" keyword or bold/italic definitions
    def_pattern = re.compile(
        r"(?:Definition|DEFINITION)[:\s]*\n?(.*?)(?:\n\n|\n(?=\d+\.\d+))",
        re.DOTALL | re.IGNORECASE,
    )
    for match in def_pattern.finditer(text):
        defn = match.group(1).strip()
        if len(defn) > 10:
            definitions.append(defn[:500])

    # Also look for "A set is..." patterns
    is_pattern = re.compile(
        r"(?:A|An|The)\s+\w+\s+is\s+(?:defined as|said to be|called)\s+[^.]+\.",
        re.IGNORECASE,
    )
    for match in is_pattern.finditer(text):
        defn = match.group(0).strip()
        if defn not in definitions and len(defn) > 15:
            definitions.append(defn[:500])

    return definitions


def _extract_examples(text: str) -> list[dict]:
    """Extract worked examples from the text."""
    examples = []

    # NCERT pattern: "Example 1", "Example 2", etc.
    ex_pattern = re.compile(
        r"(?:Example|EXAMPLE)\s+(\d+)\s*(.*?)(?=(?:Example|EXAMPLE)\s+\d+|(?:EXERCISE|Exercise)\s+\d+|\Z)",
        re.DOTALL | re.IGNORECASE,
    )
    for match in ex_pattern.finditer(text):
        num = match.group(1)
        content = match.group(2).strip()
        if len(content) > 20:
            examples.append({
                "number": int(num),
                "content": content[:2000],
            })

    return examples


def _extract_exercises(text: str) -> list[str]:
    """Extract exercise/question blocks."""
    exercises = []

    # Look for "EXERCISE 1.1" blocks
    ex_pattern = re.compile(
        r"(?:EXERCISE|Exercise)\s+(\d+\.\d+)\s*(.*?)(?=(?:EXERCISE|Exercise)\s+\d+\.\d+|\Z)",
        re.DOTALL,
    )
    for match in ex_pattern.finditer(text):
        exercises.append(match.group(0).strip()[:3000])

    return exercises


if __name__ == "__main__":
    import sys
    pdf = sys.argv[1] if len(sys.argv) > 1 else "iemh101.pdf"
    result = extract_pdf(pdf, output_path="chapter_content.json")
    print(f"\nExtracted: {result['chapter_title']}")
    print(f"Pages: {result['num_pages']}")
    print(f"Sections: {len(result['sections'])}")
    for s in result["sections"]:
        print(f"  {s['number']} — {s['title']} ({s['content_length']} chars)")
