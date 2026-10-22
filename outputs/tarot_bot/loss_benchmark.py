"""Three bounded loss cycles, alternating a confirmed mismatching pair."""
import csv,fcntl,json,signal,time
from pathlib import Path
import tarot as t
R=Path(__file__).resolve().parent

def play_loss(b):
    pair=None;used=0
    for a in range(0,len(b.backs),2):
        b.reveal(a);b.reveal(a+1)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            f=b.observe()
            if b.back(a,f[a]) and b.back(a+1,f[a+1]):pair=(a+1,a);used=1;break
            b.d.wait(.08,b.w)
        if pair:break
    if pair is None:raise RuntimeError('No verified mismatching pair')
    print('Confirmed mismatching pair:',pair,flush=True)
    while used<12:
        for i in pair:
            if t.station_visible(b.d,b.c) or t.reward_visible(b.d,b.c):return used
            b.reveal(i)
        used+=1
        print('Mismatch attempt',used,flush=True)
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            if t.station_visible(b.d,b.c):return used
            if t.reward_visible(b.d,b.c):return used
            f=b.observe()
            if all(b.back(i,f[i]) for i in pair):break
            b.d.wait(.08,b.w)
        else:raise RuntimeError('Loss transition not recognized')
        pair=pair[::-1]
    deadline=time.monotonic()+6
    while time.monotonic()<deadline:
        if t.station_visible(b.d,b.c) or t.reward_visible(b.d,b.c):return used
        b.d.wait(.1,b.w)
    raise RuntimeError('No verified end after twelve mismatches')

def main():
    lock=(R/'.running.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.signal(signal.SIGINT,lambda *_:t.STOP.set())
    d=t.Desktop();c=json.loads((R/'calibration.json').read_text());t.reanchor_window(c,d.window())
    print('Loss benchmark starts in 10 seconds',flush=True)
    if t.STOP.wait(10):return
    d.guard(c['window']);d.capture(c['window']).save(R/'loss-before.png')
    partial=not (t.station_visible(d,c) or t.reward_visible(d,c))
    b=t.Board(d,c) if partial else t.station_restart(d,c)
    if partial:d.wait(1,c['window'])
    with (R/'loss-benchmark.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['trial','play_seconds','restart_seconds','cycle_seconds','mismatches','partial_start'])
        try:
            for trial in range(1,4):
                start=time.monotonic();used=play_loss(b);end=time.monotonic()
                d.capture(c['window']).save(R/f'loss-after-{trial}.png')
                b=t.station_restart(d,c);ready=time.monotonic()
                writer.writerow([trial,end-start,ready-end,ready-start,used,partial and trial==1]);f.flush()
                print('LOSS RESULT',trial,round(end-start,3),round(ready-start,3),flush=True)
            print('Three losses measured; leaving next board untouched.',flush=True)
        finally:d.release()
if __name__=='__main__':
    try:main()
    except RuntimeError as e:print('STOPPED:',e,flush=True)
