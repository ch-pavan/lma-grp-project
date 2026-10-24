#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=30G
#SBATCH -t 3:00:00
#SBATCH -o logs/pilot_S4a_laya.log
export SYS=S4a_laya
export SPLIT=test
export RUNS=1
export LIMIT=5
export CONC=10
export OUT=pilot
export UTIL=0.78
source ~/agents/lma-project-initial/run_body.sh
