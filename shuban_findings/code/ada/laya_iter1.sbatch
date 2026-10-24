#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=30G
#SBATCH -t 6:00:00
#SBATCH -o logs/laya_iter1.log
source ~/agents/lma-project-initial/laya_body.sh
