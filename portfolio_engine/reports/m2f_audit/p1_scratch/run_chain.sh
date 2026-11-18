#!/bin/bash
# usage: run_chain.sh <dest> <policy>
D=$1; export PE_TIE=$2; python3 /tmp/claude-0/-home-user-Algo-8-Reverse-Engineer/065db6a7-1cda-57f8-842a-8a8064e9a7d5/scratchpad/p1/make_mirror.py $D || exit 1
cd $D
for t in m2c_closing_batches m2d_wing_body m2e_build m2e_cases m2e_charts; do
  s=$(date +%s); python3 portfolio_engine/tools/$t.py > $D/log_$t.txt 2>&1; rc=$?; echo "$t rc=$rc $(( $(date +%s)-s ))s" >> $D/chain.log
  [ $rc -ne 0 ] && break
done
echo done >> $D/chain.log
