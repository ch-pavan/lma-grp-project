#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=30G
#SBATCH -t 2:00:00
#SBATCH -o logs/q35_smoke.log
source ~/agents/lma-project-initial/q35_smoke.sh
