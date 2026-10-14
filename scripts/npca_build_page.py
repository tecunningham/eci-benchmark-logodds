"""Build npca.html (nonparametric ECI page): scripts/npca_page_template.html with data/npca.json embedded."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
page = (ROOT / "scripts" / "npca_page_template.html").read_text()
assert page.count("/*DATA*/") == 1
page = page.replace("/*DATA*/", (ROOT / "data" / "npca.json").read_text())
(ROOT / "npca.html").write_text(page)
print("wrote npca.html")
