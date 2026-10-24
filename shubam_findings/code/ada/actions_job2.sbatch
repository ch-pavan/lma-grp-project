#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=40G
#SBATCH -t 16:00:00
#SBATCH -o logs/actions_job2.log
# context fix reruns, oracle per mode, done check (alone and with the best rollback mode), then Qwen3.5 4B rows
export DROPCTX=1
export SYS8=S1_record,S1_none@vote3,S_oracle@rbh2,S3_llm_judge,S3_llm_judge@rbh2,S3_llm_judge@rb2,S3_llm_judge@rbh2d,S3_llm_judge@vote3,S_oracle,S_oracle@rb2,S_oracle@rbh2d,S_oracle@vote3,S_oracle@dc,S_oracle@rbh2dc,S3_llm_judge@dc,S3_llm_judge@rbh2dc
export Q35MODEL=cyankiwi/Qwen3.5-4B-AWQ-4bit SYS35=S1_none,S3_llm_judge,S3_llm_judge@rbh2d OFF35=1 OFFN=600
export SPLIT=2,12,19,28,55,66,78,91,93,107,112,160,184,185,199 RUNS=2 CONC=10 OUT=acts/tune
source ~/agents/lma-project-initial/actions_body.sh
