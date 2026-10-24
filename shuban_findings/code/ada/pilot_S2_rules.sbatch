#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=30G
#SBATCH -t 3:00:00
#SBATCH -o logs/pilot_S2_rules.log
export SYS=S2_rules
export SPLIT=test
export RUNS=1
export LIMIT=5
export CONC=10
export OUT=pilot
source ~/agents/lma-project-initial/run_body.sh
