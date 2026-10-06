"""Embed data/eci_data.json into scripts/page_template.html -> index.html (GitHub Pages entry point)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
page = (ROOT / "scripts" / "page_template.html").read_text()
data = (ROOT / "data" / "eci_data.json").read_text()
assert page.count("/*DATA*/") == 1
(ROOT / "index.html").write_text(page.replace("/*DATA*/", data))
print("wrote index.html")
