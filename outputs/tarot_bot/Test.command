#!/bin/zsh
set -o pipefail
cd -- "${0:A:h}"
python_bin="../../work/runtime/bin/python"
if [[ ! -x "$python_bin" ]]; then python_bin=".venv/bin/python"; fi
print 'TAROT TEST STARTED'
print 'Click Roblox now and keep it focused. Read-only board check starts in 10 seconds.'
"$python_bin" -u tarot.py inspect --delay 10 2>&1 | tee test-run.log
result=$?
if [[ "$result" -eq 0 ]]; then
  print 'Board inspection passed. Trying one round.'
  "$python_bin" -u tarot.py play --delay 2 2>&1 | tee -a test-run.log
fi
print 'Test finished. Results are above and saved in test-run.log.'
read '?Press Enter to close.'
