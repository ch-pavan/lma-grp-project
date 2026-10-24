#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=30G
#SBATCH -t 24:00:00
#SBATCH -o logs/full_S4a_laya.log
export SYS=S4a_laya
export SPLIT=test
export RUNS=3
export CONC=10
export OUT=results
export UTIL=0.80
source ~/agents/lma-project-initial/run_body.sh
