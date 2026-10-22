#!/bin/zsh
cd -- "${0:A:h}"
/usr/bin/open -a Roblox
../../work/runtime/bin/python -u diagnose.py > diagnostic.log 2>&1
