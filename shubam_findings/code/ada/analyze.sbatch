#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH -c 2
#SBATCH --mem=8G
#SBATCH -t 01:00:00
#SBATCH -o logs/analyze.log
# runs after every full job: accuracy, bootstrap CIs, chart into results/summary.{json,png}
cd ~/agents/lma-project-initial; S=/scratch/$USER/lma-an-$SLURM_JOB_ID
python3.10 -m venv $S && . $S/bin/activate && pip install -q --no-index --find-links wheels numpy matplotlib
python code/analyze.py results results/summary; rm -rf $S
