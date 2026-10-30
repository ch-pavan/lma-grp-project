#!/bin/sh
# Rebuild figures then the PDF. Figures 1 to 3 (system, agents, baselines) come from the team report in ../figs.
set -e
cd "$(dirname "$0")"
python3 make_figs.py
pdflatex -interaction=nonstopmode -halt-on-error -jobname=Stay_On_Task_mid_report report.tex >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error -jobname=Stay_On_Task_mid_report report.tex >/dev/null
rm -f Stay_On_Task_mid_report.aux Stay_On_Task_mid_report.log Stay_On_Task_mid_report.out
pdfinfo Stay_On_Task_mid_report.pdf | grep Pages
