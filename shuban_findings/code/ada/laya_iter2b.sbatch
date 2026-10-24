#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=30G
#SBATCH -t 8:00:00
#SBATCH -o logs/laya_iter2b.log
export PHASES=pilot2 PILOT2="S1_record S4v_single S4v_head S_jev" MAXLEN=8192 UTIL=0.78 LAYA_DEVICE=cpu PILOT_OUT=pilot2b
export JEV_CFG=$HOME/agents/lma-project-initial/code/laya/jev_online.json
source ~/agents/lma-project-initial/laya_body.sh
