#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 16
#SBATCH --mem=30G
#SBATCH -t 6:00:00
#SBATCH -o logs/pilot_S4b_cpu.log
export SYS=S4b_granite
export SPLIT=test
export RUNS=1
export LIMIT=5
export CONC=10
export OUT=pilot_g2
export GRANITE_URL=cpu
source ~/agents/lma-project-initial/run_body.sh
