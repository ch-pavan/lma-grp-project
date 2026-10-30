# Mid submission report (8 pages)

- Text and tables: edit `report.tex`.
- Figures 4 to 7 (offline detection, effect sizes, label agreement, timeline): the numbers are typed into `make_figs.py`. Change them there and rebuild. Figures 1 to 3 are PDFs in `figs/` taken from the team report.
- `sources.md` maps every number in the report to the file it comes from.

Build on Linux or macOS with TeX Live and Python 3 with matplotlib:

```
sh compile.sh
```

It redraws the figures, runs pdflatex twice and prints the page count. On Overleaf, upload this folder and compile `report.tex` with pdflatex. The figures are already in `figs/`, so Overleaf does not need Python.
