#!/bin/zsh
set -o pipefail
cd -- "${0:A:h}"
/usr/bin/open -a Roblox
../../work/runtime/bin/python -u apple_bobber.py --delay 3 --seconds 180 2>&1 | tee run.log
read '?Finished. Press Enter to close.'
