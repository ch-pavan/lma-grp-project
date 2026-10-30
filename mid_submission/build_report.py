#!/usr/bin/env python3
"""Build Stay_On_Task_mid_report.pdf from mid_report.tex with pdflatex (MiKTeX or TeX Live).

Runs make_figs.py first if a figure is missing, then pdflatex three times (the contents, cross-references and the page count settle by the third pass),
then removes the auxiliary files.

    python mid_submission/build_report.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEX = HERE / "mid_report.tex"
JOB = "Stay_On_Task_mid_report"
FIGS = ["fig1_system", "fig2_agents", "fig3_test_baselines", "fig4_offline_laya", "fig5_live", "fig6_agreement",
        "fig7_timeline"]


def main():
    if not shutil.which("pdflatex"):
        sys.exit("pdflatex not found: install MiKTeX or TeX Live")
    if any(not (HERE / "figs" / f"{f}.pdf").exists() for f in FIGS):
        subprocess.run([sys.executable, str(HERE / "make_figs.py")], check=True)
    cmd = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", f"-jobname={JOB}", TEX.name]
    for _ in range(3):
        r = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, errors="replace")
        if r.returncode != 0:
            log = (HERE / f"{JOB}.log").read_text(errors="replace")
            err = [l for l in log.splitlines() if l.startswith("!")] or log.splitlines()[-30:]
            sys.exit("pdflatex failed:\n" + "\n".join(err[:20]))
    for ext in ("aux", "log", "out", "toc"):
        (HERE / f"{JOB}.{ext}").unlink(missing_ok=True)
    pdf = HERE / f"{JOB}.pdf"
    print(f"wrote {pdf} ({pdf.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
