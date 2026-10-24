#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=30G
#SBATCH -t 36:00:00
#SBATCH -o logs/full_S3_llm_judge_1.log
export SYS=S3_llm_judge
export SPLIT=test
export RUNS=3
export CONC=10
export OUT=results
export SHARD=1/2
source ~/agents/lma-project-initial/run_body.sh
