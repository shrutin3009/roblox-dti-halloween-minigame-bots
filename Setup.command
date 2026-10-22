#!/bin/zsh
set -e
cd -- "${0:A:h}"
trap 'print "Setup failed. Review the error above."; read "?Press Enter to close."' ZERR
python_bin="$(command -v python3.12 || command -v python3 || true)"
if [[ -z "$python_bin" ]]; then
  print 'Install Python 3.12 from python.org, then run Setup.command again.'
  read '?Press Enter to close.'
  exit 1
fi
"$python_bin" -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12 or newer required"; import tkinter'
"$python_bin" -m venv work/runtime
work/runtime/bin/python -m pip install --upgrade pip
work/runtime/bin/python -m pip install -r requirements.txt
work/runtime/bin/python -c 'import numpy, PIL, cv2, mss, Quartz, AppKit, tkinter; print("Dependencies verified.")'
chmod +x ./*.command outputs/tarot_bot/*.command outputs/apple_bobber/*.command
print 'Setup complete. Next: enable Terminal permissions and calibrate Tarot. See README.md.'
read '?Press Enter to close.'
