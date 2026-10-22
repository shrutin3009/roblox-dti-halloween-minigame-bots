"""Bounded live win/loss timing experiment. No purchases or movement."""
import csv,fcntl,json,signal,time
from pathlib import Path
import tarot as t
ROOT=Path(__file__).resolve().parent

def result_wait(d,c,timeout=10):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        if t.reward_visible(d,c):return True
        d.wait(.15,c['window'])
    return False

def lose(b):
    pair=None
    # Find a real nonmatching pair, then reuse it only for this deliberate-loss experiment.
    for a in range(0,len(b.backs),2):
        b.reveal(a);b.reveal(a+1)
        end=time.monotonic()+7
        while time.monotonic()<end:
            f=b.observe()
            if b.back(a,f[a]) and b.back(a+1,f[a+1]):pair=(a,a+1);break
            b.d.wait(.1,b.w)
        if pair:break
    if pair is None:raise RuntimeError('No confirmed mismatch found for loss test')
    for attempt in range(11):
        for i in pair:b.reveal(i)
        end=time.monotonic()+8
        while time.monotonic()<end:
            if t.reward_visible(b.d,b.c):return
            f=b.observe()
            if all(b.back(i,f[i]) for i in pair):break
            b.d.wait(.1,b.w)
        else:
            b.d.capture(b.w).save(ROOT/'benchmark-loss-transition.png')
            return
    result_wait(b.d,b.c)

def main():
    lock=(ROOT/'.running.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    signal.signal(signal.SIGINT,lambda *_:t.STOP.set())
    d=t.Desktop();c=json.loads((ROOT/'calibration.json').read_text());t.reanchor_window(c,d.window())
    print('Benchmark starts in 10 seconds',flush=True)
    if t.STOP.wait(10):return
    d.guard(c['window']);b=t.Board(d,c)
    if t.reward_visible(d,c) or t.station_visible(d,c):b=t.station_restart(d,c)
    with (ROOT/'benchmark.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['mode','trial','play_seconds','restart_seconds','cycle_seconds','reward_recognized']);f.flush()
        try:
            for mode in ['win','win','win']:
                start=time.monotonic()
                print('BENCHMARK START',mode,flush=True)
                if mode=='win':t.solve_with_recovery(b)
                else:lose(b)
                recognized=result_wait(d,c);finished=time.monotonic()
                trial=main.count;main.count+=1
                d.capture(c['window']).save(ROOT/f'benchmark-{trial}-{mode}.png')
                if not recognized:
                    writer.writerow([mode,trial,finished-start,'','',False]);f.flush()
                    raise RuntimeError('Result needs inspection; stopped bounded experiment')
                b=t.station_restart(d,c);ready=time.monotonic()
                writer.writerow([mode,trial,finished-start,ready-finished,ready-start,True]);f.flush()
                print('BENCHMARK RESULT',mode,round(finished-start,2),round(ready-start,2),flush=True)
        finally:d.release()
main.count=1
if __name__=='__main__':
    try:main()
    except RuntimeError as e:print('BENCHMARK STOPPED:',e,flush=True)
