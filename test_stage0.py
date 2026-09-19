"""Quick test for Stage 0 — PDF extraction."""
import sys
sys.path.insert(0, ".")

from stages.pdf_extractor import extract_pdf

result = extract_pdf("iemh101.pdf", "outputs/iemh101/chapter_content.json")

print("\n--- Sections ---")
for s in result["sections"]:
    print(f"  {s['number']} - {s['title']}")

print(f"\nDefinitions: {len(result['definitions'])}")
for d in result["definitions"][:3]:
    print(f"  • {d[:100]}...")

print(f"\nExamples: {len(result['examples'])}")
for e in result["examples"][:3]:
    print(f"  • Ex {e['number']}: {e['content'][:80]}...")

print(f"\nExercises: {len(result['exercises'])}")
print(f"Full text length: {len(result['full_text'])} chars")
