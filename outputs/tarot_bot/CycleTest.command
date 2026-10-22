#!/bin/zsh
set -o pipefail
cd -- "${0:A:h}"
python_bin="../../work/runtime/bin/python"
if [[ ! -x "$python_bin" ]]; then python_bin=".venv/bin/python"; fi
print 'Click Roblox within 10 seconds. Testing two rounds and automatic station replay.'
"$python_bin" -u tarot.py play --delay 10 --rounds 2 --station-loop 2>&1 | tee cycle-test.log
read '?Test finished. Press Enter to close.'
