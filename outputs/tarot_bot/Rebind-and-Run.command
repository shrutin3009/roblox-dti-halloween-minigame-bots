#!/bin/zsh
set -o pipefail
cd -- "${0:A:h}"
/usr/bin/open -a Roblox
../../work/runtime/bin/python -u rebind_and_play.py 2>&1 | tee repeat-run.log
read '?Finished. Press Enter to close.'
