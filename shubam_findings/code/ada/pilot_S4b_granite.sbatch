#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:2
#SBATCH -c 18
#SBATCH --mem=60G
#SBATCH -t 3:00:00
#SBATCH -o logs/pilot_S4b_granite.log
export SYS=S4b_granite
export SPLIT=test
export RUNS=1
export LIMIT=5
export CONC=10
export OUT=pilot
source ~/agents/lma-project-initial/run_body.sh
