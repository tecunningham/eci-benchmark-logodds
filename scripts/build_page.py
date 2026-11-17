"""Build index.html (the GitHub Pages entry point): scripts/page_template.html with
data/eci_data.json, data/curve_fits.json (capability under other benchmark curves), data/resid_null.json (simulated null for the residual tab) and the in-browser
ECI solver (scripts/eci_fit.js), the open-choices solver (scripts/flex_fit.js) and the third tab's code (scripts/fit_tab.js) embedded."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
page = (ROOT / "scripts" / "page_template.html").read_text()
key = "/*FITTAB*/"
assert page.count(key) == 1, key
page = page.replace(key, (ROOT / "scripts" / "fit_tab.js").read_text())
for key, src in [("/*DATA*/", ROOT / "data" / "eci_data.json"), ("/*CURVES*/", ROOT / "data" / "curve_fits.json"),
                 ("/*RNULL*/", ROOT / "data" / "resid_null.json"),
                 ("/*SOLVER*/", ROOT / "scripts" / "eci_fit.js"), ("/*FLEX*/", ROOT / "scripts" / "flex_fit.js")]:
    assert page.count(key) == 1, key
    page = page.replace(key, src.read_text())
(ROOT / "index.html").write_text(page)
print("wrote index.html")
