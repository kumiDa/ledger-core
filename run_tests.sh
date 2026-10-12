#!/usr/bin/env bash
# Runs the replay, then the green suite, then the one intentional failure.
set -uo pipefail
cd "$(dirname "$0")"

echo
echo "### 1. REPLAY ###############################################################"
python3 replay.py || exit 1

echo
echo "### 2. TEST SUITE (must be green) ##########################################"
python3 -m unittest tests.test_acceptance tests.test_invariants -v 2>&1 | tail -n 15
green=${PIPESTATUS[0]}

echo
echo "### 3. KNOWN GAP (must fail -- this is the documented one) #################"
python3 -m unittest tests.test_known_gap 2>&1 | tail -n 20
echo
echo "### 4. ABANDONED PROTOTYPE #################################################"
python3 prototypes/retroactive_fees.py

echo
echo "############################################################################"
if [ "$green" -eq 0 ]; then
  echo "Green suite: PASS.  Known-gap test: FAILED as documented."
  exit 0
fi
echo "Green suite: FAILED -- that is a real regression."
exit 1
