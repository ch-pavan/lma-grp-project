#!/bin/bash
# gen.sh NAME SYS GPUS HOURS VAR=VAL... -> writes NAME.sbatch that sources run_body.sh
N=$1 SYS=$2 G=$3 HRS=$4; shift 4
{ echo "#!/bin/bash"
  echo "#SBATCH -A research"; echo "#SBATCH -p u22"; echo "#SBATCH --constraint=2080ti"
  echo "#SBATCH --gres=gpu:$G"; echo "#SBATCH -c $((9*G))"; echo "#SBATCH --mem=$((30*G))G"
  echo "#SBATCH -t $HRS:00:00"; echo "#SBATCH -o logs/$N.log"
  echo "export SYS=$SYS"; for kv in "$@"; do echo "export $kv"; done
  echo "source ~/agents/lma-project-initial/run_body.sh"; } > $N.sbatch
echo $N.sbatch
