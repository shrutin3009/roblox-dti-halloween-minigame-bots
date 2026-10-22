#!/usr/bin/env python3
"""Pixel-only Apple Bobbing tracker. Controls an already-started round only."""
import argparse
import csv
import random
import os
import fcntl
from functools import lru_cache
import json
import signal
import sys
import time
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'tarot_bot'))
import tarot

@lru_cache(maxsize=12)
def bar_template(name,width,height):
    image=cv2.imread(str(ROOT/'templates'/f'{name}.png'),cv2.IMREAD_GRAYSCALE)
    if image is None:raise RuntimeError(f'Missing bar reference: {name}')
    return cv2.resize(image,(width,height))


def inventory_visible(image):
    # Normalize both images so Retina pixels and logical coordinates agree.
    current=np.asarray(image.convert('L').resize((1000,697)))
    reference=Image.open(ROOT/'inventory-reference.png').convert('L').resize((1000,697))
    template=np.asarray(reference.crop((394,196,610,230)))
    scores=cv2.matchTemplate(current,template,cv2.TM_CCOEFF_NORMED)
    return float(cv2.minMaxLoc(scores)[1])>.9


def tier_one_empty(image):
    current=np.asarray(image.convert('RGB').resize((1000,697)))
    reference=np.asarray(Image.open(ROOT/'inventory-reference.png').convert('RGB').resize((1000,697)))
    # Compare white count lettering; ignore differently colored ticket panels.
    template=(reference[431:445,489:511].min(axis=2)>205).astype(np.uint8)*255
    region=(current[427:449,292:330].min(axis=2)>205).astype(np.uint8)*255
    return float(cv2.minMaxLoc(cv2.matchTemplate(region,template,cv2.TM_CCOEFF_NORMED))[1])>.94


def start_tier_one(d,w):
    image=d.capture(w)
    if not inventory_visible(image):
        print('Opening ticket inventory with E',flush=True)
        d.key('e',random.uniform(.96,1.18),w)
        deadline=time.monotonic()+6
        while not inventory_visible(d.capture(w)):
            if time.monotonic()>deadline:raise RuntimeError('Ticket inventory did not open; no ticket used')
            d.wait(.15,w)
    if tier_one_empty(d.capture(w)):
        (ROOT/'status.json').write_text(json.dumps({'state':'STOPPED','reason':'zero_tier_one_tickets','holding':False}))
        (ROOT/'controller.pid').unlink(missing_ok=True)
        raise RuntimeError('Zero Tier 1 tickets remaining; finished without buying tickets')
    print('Ticket inventory recognized; using ONE Tier 1 ticket',flush=True)
    d.capture(w).save(ROOT/'before-ticket.png')
    d.wait(random.uniform(.15,.55),w)
    d.click(ticket_point(w),w)
    # Never retry this click automatically: it could consume another ticket.
    d.wait(.3,w)


def ticket_point(w):
    # Interior of the Tier 1 green Use button in the calibrated inventory.
    return (w['left']+w['width']*random.uniform(.275,.345),
            w['top']+w['height']*random.uniform(.655,.700))

def wait_for_reward(d,w,timeout=6):
    # Confetti can temporarily cover either reward anchor.
    deadline=time.monotonic()+timeout
    while True:
        if tarot.reward_visible(d,{'window':w}):return True
        if time.monotonic()>=deadline:return False
        d.wait(.25,w)


def replay_transition(d,w,confirmed=False):
    # The caller can carry forward an already confirmed reward instead of
    # rejecting it because confetti covers a subsequent single frame.
    if not confirmed and not wait_for_reward(d,w):
        raise RuntimeError('Reward not confirmed after retry window; no ticket used')
    for attempt in range(3):
        d.wait(random.uniform(.25,.9),w)
        d.click((w['left']+w['width']*random.uniform(.46,.54),
                 w['top']+w['height']*random.uniform(.929,.939)),w)
        print(f'Reward close attempt {attempt+1}/3',flush=True)
        d.wait(random.uniform(.6,.9),w)
        # Watch several frames: one frame without text is not proof of closure.
        if not wait_for_reward(d,w,timeout=1.5):break
    else:raise RuntimeError('Reward still visible after three close attempts; no ticket used')
    direction=random.choice('wasd');opposite={'w':'s','s':'w','a':'d','d':'a'}[direction]
    duration=random.uniform(.035,.06)
    d.key(direction,duration,w);d.wait(random.uniform(.12,.25),w)
    d.key(opposite,duration,w);d.wait(random.uniform(.4,.8),w)
    # The recognized inventory remains mandatory before another ticket click.


def detect(image,logical_width=1000):
    """Track bar texture first, then red apple inside the lane's middle band."""
    rgb=np.asarray(image.convert('RGB'));h,w=rgb.shape[:2]
    scale=w/(logical_width*.76);gray=cv2.cvtColor(rgb,cv2.COLOR_RGB2GRAY)
    best=None
    for name in ['silver','purple']:
        template=bar_template(name,round(125*scale),round(34*scale))
        if h<template.shape[0] or w<template.shape[1]:continue
        scores=cv2.matchTemplate(gray,template,cv2.TM_CCOEFF_NORMED)
        _,score,_,point=cv2.minMaxLoc(scores)
        if best is None or score>best[0]:best=(score,point)
    if best is None or best[0]<.78:return None
    score,(bx,by)=best;bar=[bx-5*scale,by-4*scale,200*scale,40*scale]
    center_y=bar[1]+bar[3]/2
    top=max(0,round(center_y-12*scale));bottom=min(h,round(center_y+12*scale))
    strip=rgb[top:bottom]
    if strip.size==0:return None
    hsv=cv2.cvtColor(strip,cv2.COLOR_RGB2HSV)
    r,g,b=[strip[:,:,i].astype(float) for i in range(3)]
    red=((r>65)&(r>g*1.65)&(r>b*1.35)&(hsv[:,:,1]>110)&((hsv[:,:,0]<10)|(hsv[:,:,0]>170))).astype(np.uint8)*255
    red=cv2.morphologyEx(red,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    contours,_=cv2.findContours(red,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    apples=[]
    for contour in contours:
        x,y,bw,bh=cv2.boundingRect(contour)
        if 18*scale<bw<65*scale and bh>10*scale:
            apples.append((cv2.contourArea(contour),[x,y+top,bw,bh]))
    if not apples:return None
    apple=max(apples,key=lambda x:x[0])[1]
    return {'bar':bar,'apple':apple,'bar_x':bar[0]+bar[2]/2,
            'apple_x':apple[0]+apple[2]/2,'scale':scale,'confidence':float(score)}

class Controller:
    def __init__(self):self.last=None;self.bv=0.;self.av=0.;self.hold=False
    def decide(self,sample,now):
        if self.last:
            old,t=self.last;dt=max(.01,now-t)
            self.bv=.65*self.bv+.35*(sample['bar_x']-old['bar_x'])/dt
            self.av=.65*self.av+.35*(sample['apple_x']-old['apple_x'])/dt
        error=sample['apple_x']-sample['bar_x']
        signal=error+.10*self.av-.12*self.bv
        if signal>6*sample['scale']:self.hold=True
        elif signal< -6*sample['scale']:self.hold=False
        self.last=(sample,now)
        return self.hold,error

class Mouse:
    def __init__(self,d,w,point):self.d=d;self.w=w;self.point=point;self.down=False;self.since=0
    def set(self,down):
        self.d.guard(self.w)
        if down==self.down:return
        Q=self.d.Q
        if down and not tarot.accessibility_trusted():raise RuntimeError('Accessibility permission missing')
        if down:Q.CGEventPost(Q.kCGHIDEventTap,Q.CGEventCreateMouseEvent(None,Q.kCGEventMouseMoved,self.point,0))
        kind=Q.kCGEventLeftMouseDown if down else Q.kCGEventLeftMouseUp
        Q.CGEventPost(Q.kCGHIDEventTap,Q.CGEventCreateMouseEvent(None,kind,self.point,0))
        self.down=down;self.since=time.monotonic()
    def release(self):
        if self.down:
            Q=self.d.Q
            Q.CGEventPost(Q.kCGHIDEventTap,Q.CGEventCreateMouseEvent(None,Q.kCGEventLeftMouseUp,self.point,0))
            self.down=False

def monitor_image(image,sample):
    out=image.copy();draw=ImageDraw.Draw(out)
    if sample:
        for key,color in [('bar','lime'),('apple','red')]:
            x,y,w,h=sample[key];draw.rectangle((x,y,x+w,y+h),outline=color,width=2)
    return out

def run(args):
    # Share the same lock with the tarot controller to prevent conflicting inputs.
    lock=(ROOT.parent/'tarot_bot/.running.lock').open('w')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    (ROOT/'controller.pid').write_text(str(os.getpid()))
    d=tarot.Desktop();w=d.window();control=Controller()
    roi={'left':w['left']+int(w['width']*.12),'top':w['top']+int(w['height']*.70),
         'width':int(w['width']*.76),'height':int(w['height']*.22)}
    mouse=Mouse(d,w,(w['left']+w['width']*random.uniform(.25,.75),w['top']+w['height']*random.uniform(.805,.825)))
    signal.signal(signal.SIGINT,lambda *_:tarot.STOP.set())
    signal.signal(signal.SIGTERM,lambda *_:tarot.STOP.set())
    print(f'Start in {args.delay}s. Keep Roblox focused. Escape or main-screen top-left stops.',flush=True)
    if tarot.STOP.wait(args.delay):return
    d.guard(w)
    initial=d.capture(w)
    calibration={'window':w,'capture_pixels':list(initial.size),'scale':[initial.width/w['width'],initial.height/w['height']],'roi':roi}
    (ROOT/'calibration.json').write_text(json.dumps(calibration,indent=2))
    print('Calibration saved:',calibration,flush=True)
    if args.use_ticket:
        if args.monitor_only:raise RuntimeError('Monitor-only mode cannot use a ticket')
        if wait_for_reward(d,w,timeout=.8):
            print('Resuming from existing reward popup',flush=True)
            replay_transition(d,w,confirmed=True)
        start_tier_one(d,w)
    started=time.monotonic();last_seen=None;last_report=0;last_save=0;ticks=0;reason='time_limit'
    with (ROOT/'telemetry.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['seconds','state','apple_x','bar_x','error','holding'])
        try:
            while time.monotonic()-started<args.seconds:
                d.guard(w)
                image=d.capture(roi);sample=detect(image,w['width']);now=time.monotonic();ticks+=1
                if sample:
                    last_seen=now;hold,error=control.decide(sample,now)
                    if mouse.down and now-mouse.since>1.1:
                        mouse.set(False);d.wait(.035,w)
                    if not args.monitor_only:mouse.set(hold)
                    state='TRACKING' if not args.monitor_only else 'MONITORING'
                    writer.writerow([round(now-started,3),state,round(sample['apple_x'],2),round(sample['bar_x'],2),round(error,2),mouse.down])
                else:
                    mouse.release();state='WAITING_FOR_GAME' if last_seen is None else 'GAME_UI_MISSING'
                    if last_seen is not None and now-last_seen>2:
                        if wait_for_reward(d,w):
                            reason='reward_screen_confirmed'
                            d.capture(w).save(ROOT/'last-result.png')
                            print('WIN: reward screen confirmed.',flush=True)
                        else:
                            reason='game_bar_disappeared'
                            d.capture(w).save(ROOT/'last-result.png')
                            print('Game bar absent: round ended; result unverified.',flush=True)
                        break
                    if last_seen is None and now-started>20 and not args.monitor_only:
                        reason='game_ui_not_found';print('No active game bar found in 20 seconds; no input sent.',flush=True);break
                if now-last_report>.75:
                    text=state if not sample else f"{state} apple={sample['apple_x']:.0f} bar={sample['bar_x']:.0f} error={error:+.0f} {'HOLD' if mouse.down else 'RELEASE'}"
                    print(text,flush=True);last_report=now
                if now-last_save>.5:
                    payload={'state':state,'elapsed':round(now-started,2),'sample':sample,'holding':mouse.down,'mode':'monitor' if args.monitor_only else 'control'}
                    temp=ROOT/'status.tmp';temp.write_text(json.dumps(payload,indent=2));temp.replace(ROOT/'status.json')
                    monitor_image(image,sample).save(ROOT/'monitor.png');last_save=now;f.flush()
                d.wait(.025,w)
        except BaseException as exc:
            reason=str(exc);raise
        finally:
            mouse.release();d.release()
            (ROOT/'status.json').write_text(json.dumps({'state':'WON' if reason=='reward_screen_confirmed' else 'STOPPED','reason':reason,'holding':False,'frames':ticks},indent=2))
            (ROOT/'controller.pid').unlink(missing_ok=True)
            print(f'Input released. {ticks} frames sampled.',flush=True)
    return reason

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--monitor-only',action='store_true');p.add_argument('--use-ticket',action='store_true',help='Open inventory if needed and use exactly one Tier 1 ticket')
    p.add_argument('--repeat',action='store_true',help='Repeat owned Tier 1 tickets after confirmed rewards; stop on any uncertain state')
    p.add_argument('--seconds',type=float,default=180);p.add_argument('--delay',type=float,default=3)
    a=p.parse_args()
    if not 1<=a.seconds<=600 or not 0<=a.delay<=60:p.error('seconds: 1..600; delay: 0..60')
    try:
        if a.repeat and (not a.use_ticket or a.monitor_only):p.error('--repeat requires --use-ticket and control mode')
        round_number=0
        while True:
            reason=run(a);round_number+=1
            print(f'Completed rounds this session: {round_number}; result: {reason}',flush=True)
            if not a.repeat or reason!='reward_screen_confirmed':break
            d=tarot.Desktop();w=d.window()
            replay_transition(d,w,confirmed=True)
            a.delay=0

    except (RuntimeError,BlockingIOError) as e:print('STOPPED:',e,flush=True);sys.exit(1)
