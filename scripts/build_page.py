"""Build index.html (the GitHub Pages entry point): scripts/page_template.html with
data/eci_data.json, data/curve_fits.json (capability under other benchmark curves), data/resid_null.json (simulated null for the residual tab) and the in-browser
ECI solver (scripts/eci_fit.js), the open-choices solver (scripts/flex_fit.js) and the third tab's code (scripts/fit_tab.js) embedded."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
page = (ROOT / "scripts" / "page_template.html").read_text()
for key, src in [("/*FITTAB*/", "fit_tab.js"), ("/*FAILTAB*/", "fail_tab.js")]:   # tab code first: it holds no placeholders
    assert page.count(key) == 1, key
    page = page.replace(key, (ROOT / "scripts" / src).read_text())
fails = ROOT / "data" / "failures.json"   # notes for the fourth tab; "<" escaped so the text cannot close the script tag
key = "/*FAILS*/"
assert page.count(key) == 1, key
if fails.exists():
    import json
    F = json.loads(fails.read_text())
    rows_file = ROOT / "data" / "failures_rows.json"   # two failure tasks per benchmark
    R = {b["id"]: b for b in json.loads(rows_file.read_text())["benchmarks"]} if rows_file.exists() else {}
    for b in F["benchmarks"]:
        b["rows"] = R.get(b["id"], {}).get("rows", [])[:2]
        b["no_rows_reason"] = R.get(b["id"], {}).get("no_rows_reason")
    page = page.replace(key, json.dumps(F, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c"))
else:
    page = page.replace(key, "null")
for key, src in [("/*DATA*/", ROOT / "data" / "eci_data.json"), ("/*CURVES*/", ROOT / "data" / "curve_fits.json"),
                 ("/*RNULL*/", ROOT / "data" / "resid_null.json"),
                 ("/*SOLVER*/", ROOT / "scripts" / "eci_fit.js"), ("/*FLEX*/", ROOT / "scripts" / "flex_fit.js")]:
    assert page.count(key) == 1, key
    page = page.replace(key, src.read_text())
(ROOT / "index.html").write_text(page)
print("wrote index.html")
