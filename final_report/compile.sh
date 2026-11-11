#!/bin/sh
# Rebuild figures then the PDF. Figures reused from the mid report are already in figs/
set -e
cd "$(dirname "$0")"
python3 make_figs.py
pdflatex -interaction=nonstopmode -halt-on-error -jobname=Stay_On_Task_final_report report.tex >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error -jobname=Stay_On_Task_final_report report.tex >/dev/null
pdflatex -interaction=nonstopmode -halt-on-error -jobname=Stay_On_Task_final_report report.tex >/dev/null
rm -f Stay_On_Task_final_report.aux Stay_On_Task_final_report.log Stay_On_Task_final_report.out
pdfinfo Stay_On_Task_final_report.pdf | grep Pages
