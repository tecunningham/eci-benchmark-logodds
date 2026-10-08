"""Build index.html (the GitHub Pages entry point): scripts/page_template.html with
data/eci_data.json and the in-browser ECI solver (scripts/eci_fit.js) embedded."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
page = (ROOT / "scripts" / "page_template.html").read_text()
for key, src in [("/*DATA*/", ROOT / "data" / "eci_data.json"), ("/*SOLVER*/", ROOT / "scripts" / "eci_fit.js")]:
    assert page.count(key) == 1, key
    page = page.replace(key, src.read_text())
(ROOT / "index.html").write_text(page)
print("wrote index.html")
