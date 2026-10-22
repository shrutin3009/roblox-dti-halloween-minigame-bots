#!/bin/zsh
set -o pipefail
cd -- "${0:A:h}"
/usr/bin/open -a Roblox
../../work/runtime/bin/python -u benchmark.py 2>&1 | tee benchmark.log
read '?Benchmark finished. Press Enter to close.'
