#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:2
#SBATCH -c 18
#SBATCH --mem=60G
#SBATCH -t 36:00:00
#SBATCH -o logs/full_S4b_granite.log
export SYS=S4b_granite
export SPLIT=test
export RUNS=3
export CONC=10
export OUT=results
source ~/agents/lma-project-initial/run_body.sh
