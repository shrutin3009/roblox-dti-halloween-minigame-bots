#!/bin/zsh
cd -- "${0:A:h}"
python_bin="../../work/runtime/bin/python"
if [[ ! -x "$python_bin" ]]; then
  python_bin=".venv/bin/python"
fi
if [[ ! -x "$python_bin" ]]; then
  print 'Install Python 3.12+, then follow README.md setup instructions.'
  read '?Press Enter to close.'
  exit 1
fi
print '1) Calibrate / correct card centers'
print '2) Inspect only (no clicks)'
print '3) Play one round'
print '4) Teach a station route'
read 'choice?Choose 1–4: '
case "$choice" in
  1) "$python_bin" tarot.py calibrate ;;
  2) "$python_bin" tarot.py inspect ;;
  3) "$python_bin" tarot.py play ;;
  4) "$python_bin" tarot.py teach-route ;;
  *) print 'Cancelled.' ;;
esac
read '?Press Enter to close.'
