#!/bin/zsh
cd -- "${0:A:h}"
/usr/bin/open -a Roblox
../../work/runtime/bin/python -u ../../work/apple_probe/probe.py > ../../work/apple_probe/probe.log 2>&1
