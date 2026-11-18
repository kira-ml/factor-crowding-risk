# One-page research brief

A designed A4 summary for LinkedIn and research-sharing.

| File | Use |
| :--- | :--- |
| `factor_crowding_research_brief.pdf` | Print-quality A4; best for a LinkedIn document post |
| `factor_crowding_research_brief.png` | 1818 × 2573 image; best for a LinkedIn image post |
| `factor_crowding_research_brief.html` | Source layout and copy |
| `chart_capacity.png` | Capacity-surface chart, generated from `outputs/tables/capacity_sensitivity_cost.csv` |
| `chart_overlay_es.png` | Overlay expected-shortfall chart, generated from `outputs/tables/overlay_summary.csv` and `overlay_tests.csv` |

## Regenerate

```bash
python scripts/make_one_pager_charts.py
```

Then render the HTML to PDF with headless Chrome and convert to PNG:

```bash
chrome --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=docs/one_pager/factor_crowding_research_brief.pdf \
  docs/one_pager/factor_crowding_research_brief.html

python -c "import pymupdf, pathlib; \
p=pathlib.Path('docs/one_pager/factor_crowding_research_brief.pdf'); \
d=pymupdf.open(p); d[0].get_pixmap(dpi=220).save('docs/one_pager/factor_crowding_research_brief.png')"
```

The values are read from the generated tables, not hardcoded. If the report is
regenerated, run the chart script and the render step again.
