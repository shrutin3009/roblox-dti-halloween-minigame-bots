#!/bin/zsh
set -o pipefail
cd -- "${0:A:h}"
/usr/bin/open -a Roblox
../../work/runtime/bin/python -u loss_benchmark.py 2>&1 | tee loss-benchmark.log
read '?Test finished. Press Enter to close.'
