#!/bin/bash
# Runs on the Mac. Packs what the instance needs: Shuban's harness, the BFCL data, the annotation and rejudge scripts
# and these job scripts. No run data, no keys.
# usage: bash runs/cloud/make_bundle.sh OUT.tgz
set -euo pipefail
cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"
COPYFILE_DISABLE=1 tar --no-xattrs --exclude='__pycache__' --exclude='*.pyc' --exclude='shuban_findings/code/ada' -czf "$1" \
  shuban_findings/code third_party/gorilla analysis/annotate.py analysis/rejudge_unparsed.py analysis/oracle_labels.py analysis/sample_test.py runs/cloud
ls -lh "$1"
