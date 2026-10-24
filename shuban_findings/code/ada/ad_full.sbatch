#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=30G
#SBATCH -t 24:00:00
#SBATCH -o logs/ad_full.log
export SYS=S1_none,S2_rules,S3_llm_judge
export RUNPY=agentdojo_run.py
export VERSIONS=agentdojo
export RUNS=3
export LIMIT=0
export CONC=10
export OUT=results_ad
source ~/agents/lma-project-initial/run_body.sh
