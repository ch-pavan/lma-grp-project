#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=40G
#SBATCH -t 10:00:00
#SBATCH -o logs/actions_job1.log
export Q35SMOKE=1
export RANKERS=Skywork/Skywork-Reward-V2-Qwen3-0.6B,Skywork/Skywork-Reward-V2-Qwen3-1.7B,Skywork/Skywork-Reward-V2-Qwen3-4B,wjldw/ToolPRM-GRPO-v4
export SYS8=S1_record,S1_none@vote3,S_oracle@rbh2,S3_llm_judge,S3_llm_judge@rbh2,S3_llm_judge@rb2,S3_llm_judge@rbh2d,S3_llm_judge@vote3
export OFF8=1 OFFN=600
export SPLIT=2,12,19,28,55,66,78,91,93,107,112,160,184,185,199 RUNS=2 CONC=10 OUT=acts/tune
source ~/agents/lma-project-initial/actions_body.sh
