#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=40G
#SBATCH -t 8:00:00
# done check judged by the Laya agent's feature trees and by Jev, alone and with rbh2d; Qwen3 8B agents
export TREE_MODEL=$HOME/agents/lma-project-initial/code/laya/tree_model.json JEV_CFG=$HOME/agents/lma-project-initial/code/laya/jev_online.json
export SYS8=S_tree@dc,S_tree@rbh2dc,S_jev@dc,S_jev@rbh2dc
export SPLIT=2,12,19,28,55,66,78,91,93,107,112,160,184,185,199 RUNS=2 CONC=10 OUT=acts/tune
source ~/agents/lma-project-initial/actions_body.sh
