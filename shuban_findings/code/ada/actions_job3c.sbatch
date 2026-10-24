#!/bin/bash
#SBATCH --dependency=afterany:14244
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=40G
#SBATCH -t 10:00:00
# Qwen3.5 4B as agent and judge: its done check and oracle ceiling rows on the same 120 tasks
export Q35MODEL=cyankiwi/Qwen3.5-4B-AWQ-4bit SYS35=S_oracle@dc,S_oracle@rbh2dc,S3_llm_judge@dc,S3_llm_judge@rbh2dc
export SPLIT=2,12,19,28,55,66,78,91,93,107,112,160,184,185,199 RUNS=2 CONC=10 OUT=acts/tune
source ~/agents/lma-project-initial/actions_body.sh
