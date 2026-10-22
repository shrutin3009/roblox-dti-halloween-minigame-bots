"""Rebind a reopened, same-sized Roblox window after validating all card backs."""
import json,sys
import tarot as t
p=t.ROOT/'calibration.json'
c=json.loads(p.read_text());d=t.Desktop();w=d.window()
if any(w[k]!=c['window'][k] for k in ('width','height')):
    raise RuntimeError('Window dimensions changed; full calibration required')
c['window']=w
b=t.Board(d,c);frames=b.observe()
if not all(b.back(i,f) for i,f in enumerate(frames)):
    raise RuntimeError('Could not verify all saved card positions against this window')
p.write_text(json.dumps(c,indent=2))
print('Verified all 16 card positions; rebound reopened Roblox window',flush=True)
sys.argv=['tarot.py','play','--delay','10','--rounds','0','--station-loop']
t.main()
