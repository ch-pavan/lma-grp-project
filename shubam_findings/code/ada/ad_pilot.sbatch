#!/bin/bash
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=30G
#SBATCH -t 6:00:00
#SBATCH -o logs/ad_pilot.log
export SYS=S1_none,S2_rules,S3_llm_judge
export RUNPY=agentdojo_run.py
export VERSIONS=agentdojo
export RUNS=1
export LIMIT=8
export CONC=8
export OUT=pilot_ad
source ~/agents/lma-project-initial/run_body.sh
