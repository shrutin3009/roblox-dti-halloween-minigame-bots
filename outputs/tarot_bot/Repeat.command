#!/bin/zsh
set -o pipefail
cd -- "${0:A:h}"
python_bin="../../work/runtime/bin/python"
if [[ ! -x "$python_bin" ]]; then python_bin=".venv/bin/python"; fi
print 'Click Roblox within 10 seconds. Continuous rounds until Escape stops.'
/usr/bin/open -a Roblox
"$python_bin" -u tarot.py play --delay 10 --rounds 0 --station-loop 2>&1 | tee repeat-run.log
read '?Finished. Press Enter to close.'
