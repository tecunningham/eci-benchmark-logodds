"""Build npca.html (nonparametric ECI page): scripts/npca_page_template.html with data/npca.json
(joint fits, from npca_build.py) data/npca_links.json (curve options, from npca_links.py) and data/npca_accel.json (acceleration, from
npca_accel.py) embedded."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
page = (ROOT / "scripts" / "npca_page_template.html").read_text()
for key, name in [("/*DATA*/", "npca.json"), ("/*LINKS*/", "npca_links.json"), ("/*ACCEL*/", "npca_accel.json")]:
    assert page.count(key) == 1, key
    page = page.replace(key, (ROOT / "data" / name).read_text())
(ROOT / "npca.html").write_text(page)
print("wrote npca.html")
