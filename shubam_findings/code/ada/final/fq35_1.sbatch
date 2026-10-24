#!/bin/bash
#SBATCH --dependency=afterok:37263
#SBATCH -A research
#SBATCH -p u22
#SBATCH --constraint=2080ti
#SBATCH --gres=gpu:1
#SBATCH -c 9
#SBATCH --mem=40G
#SBATCH -t 20:00:00
#SBATCH -o logs/fq35_1.log
# Qwen3.5 AWQ as agent and judge, shard 1 of 2. Shard 0 tries the 9B at full context first and writes the choice; shard 1 follows it.
export MODEL=cyankiwi/Qwen3.5-4B-AWQ-4bit SUF=__q35 MAXLEN=16384 CHOICE=q35_model_choice.txt
export SARGS="--tool-call-parser qwen3_coder --max-num-seqs 16 --limit-mm-per-prompt {\"image\":0,\"video\":0}"
export AD=S1_none,S3_llm_judge@dc BF=S1_none,S3_llm_judge@dc,S_oracle@rbh2dc CONC=10 RUNS=1 SHARD=1/2
source ~/agents/lma-project-initial/final_body.sh
