#!/usr/bin/env python3
"""External pixel-only Roblox memory game helper. No game internals."""
import argparse
import ctypes
import fcntl
import itertools
import json
import math
import random
import signal
import threading
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
STOP = threading.Event()
KEYS = {'w': 13, 'a': 0, 's': 1, 'd': 2, 'e': 14, 'space': 49}

class RecognitionError(RuntimeError):
    """A visual observation can be retried without authorizing more input."""


def accessibility_trusted():
    services = ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
    services.AXIsProcessTrusted.argtypes = []
    services.AXIsProcessTrusted.restype = ctypes.c_bool
    return bool(services.AXIsProcessTrusted())

def distance(a, b):
    return float(np.mean(np.abs(a.astype(np.float32) - b.astype(np.float32)))) / 255

def feature(image):
    # Keep colour and spatial information; exclude decorative border at crop time.
    return np.asarray(image.convert('RGB').resize((32, 48)), dtype=np.uint8)

def grid_centers(first, last, rows, cols):
    if rows < 2 or cols < 2:
        raise ValueError('Grid requires at least two rows and columns')
    return [[first[0] + (last[0]-first[0])*c/(cols-1),
             first[1] + (last[1]-first[1])*r/(rows-1)]
            for r in range(rows) for c in range(cols)]

def detect_grid(image, rows, cols):
    """Find repeated portrait card outlines, rejecting incomplete grids."""
    rgb = np.asarray(image.convert('RGB'))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 45, 120)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    boxes = []
    for contour in contours:
        x, y, bw, bh = cv2.boundingRect(contour)
        if not (.035*w < bw < .15*w and .08*h < bh < .25*h and .48 < bw/bh < .82):
            continue
        if cv2.contourArea(contour) < .6*bw*bh:
            continue
        center = (x+bw/2, y+bh/2)
        if all(math.dist(center, (a+c/2, b+d/2)) > min(bw,bh)*.35 for a,b,c,d in boxes):
            boxes.append((x,y,bw,bh))
    if 0 < len(boxes) != rows*cols:
        # Canny borders may be broken by bloom. A surviving card supplies a
        # local template; repeated backs recover the complete grid.
        for x,y,bw,bh in list(boxes):
            dx,dy=max(2,int(bw*.08)),max(2,int(bh*.06))
            template=rgb[y+dy:y+bh-dy,x+dx:x+bw-dx]
            if not template.size or np.std(template)<8: continue
            scores=cv2.matchTemplate(rgb,template,cv2.TM_CCOEFF_NORMED)
            recovered=[]
            for _ in range(rows*cols+1):
                _,value,_,point=cv2.minMaxLoc(scores)
                if value<.88: break
                px,py=point
                recovered.append((px-dx,py-dy,bw,bh))
                scores[max(0,py-bh//2):py+bh//2,max(0,px-bw//2):px+bw//2]=-1
            if len(recovered)==rows*cols:
                boxes=recovered; break
    if len(boxes) != rows*cols:
        raise ValueError(f'Found {len(boxes)} candidate cards, expected {rows*cols}. Use manual calibration.')
    boxes.sort(key=lambda b:b[1]+b[3]/2)
    ordered = []
    for r in range(rows):
        row = sorted(boxes[r*cols:(r+1)*cols], key=lambda b:b[0])
        if np.std([b[1]+b[3]/2 for b in row]) > np.median([b[3] for b in row])*.15:
            raise ValueError('Card candidates do not form a regular grid')
        ordered.extend(row)
    centers = [[x+bw/2,y+bh/2] for x,y,bw,bh in ordered]
    for c in range(cols):
        if np.std([centers[r*cols+c][0] for r in range(rows)]) > np.median([b[2] for b in ordered])*.15:
            raise ValueError('Columns are not aligned')
    return centers, [float(np.median([b[2] for b in ordered])),float(np.median([b[3] for b in ordered]))]

class Desktop:
    def __init__(self):
        import Quartz as Q
        import AppKit
        import mss
        self.Q, self.AppKit, self.sct = Q, AppKit, mss.MSS()
        self.held = set()
        if not Q.CGPreflightScreenCaptureAccess():
            raise RuntimeError('Enable Screen Recording for the terminal/app running Python, then restart it.')

    def window(self):
        Q = self.Q
        windows = Q.CGWindowListCopyWindowInfo(Q.kCGWindowListOptionOnScreenOnly | Q.kCGWindowListExcludeDesktopElements, 0)
        found = [w for w in windows if w.get('kCGWindowOwnerName') == 'Roblox' and w.get('kCGWindowLayer') == 0
                 and w['kCGWindowBounds']['Width'] > 300]
        if len(found) != 1:
            raise RuntimeError(f'Expected one visible Roblox window, found {len(found)}')
        w = found[0]; b = w['kCGWindowBounds']
        return {'id':int(w['kCGWindowNumber']), 'pid':int(w['kCGWindowOwnerPID']),
                'left':int(b['X']), 'top':int(b['Y']), 'width':int(b['Width']), 'height':int(b['Height'])}

    def capture(self, rect):
        shot = self.sct.grab({k:int(rect[k]) for k in ('left','top','width','height')})
        return Image.frombytes('RGB', shot.size, shot.rgb)

    def guard(self, saved):
        if STOP.is_set(): raise RuntimeError('Emergency stop')
        Q = self.Q
        if Q.CGEventSourceKeyState(Q.kCGEventSourceStateCombinedSessionState, 53):
            STOP.set(); raise RuntimeError('Escape pressed')
        p = Q.CGEventGetLocation(Q.CGEventCreate(None))
        # Main-display top-left corner is always an emergency stop.
        if 0 <= p.x <= 5 and 0 <= p.y <= 5:
            STOP.set(); raise RuntimeError('Pointer emergency stop')
        current = self.window()
        if current != saved:
            raise RuntimeError(f'Window changed during operation: saved {saved}; current {current}. Recalibrate after resizing.')
        front = self.AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
        if front is None or int(front.processIdentifier()) != saved['pid']:
            name = front.localizedName() if front is not None else 'unavailable'
            raise RuntimeError(f'Roblox lost focus (foreground app: {name})')

    def wait(self, seconds, saved):
        until = time.monotonic()+seconds
        while time.monotonic() < until:
            self.guard(saved)
            time.sleep(min(.025,max(0,until-time.monotonic())))

    def click(self, point, saved):
        self.guard(saved)
        Q = self.Q
        if not accessibility_trusted(): raise RuntimeError('Accessibility permission is required for input')
        x,y = point
        if not (saved['left'] <= x < saved['left']+saved['width'] and saved['top'] <= y < saved['top']+saved['height']):
            raise RuntimeError('Click outside calibrated window')
        Q.CGEventPost(Q.kCGHIDEventTap, Q.CGEventCreateMouseEvent(None,Q.kCGEventMouseMoved,(x,y),0))
        self.wait(random.uniform(.04,.08),saved)
        self.guard(saved)
        try:
            Q.CGEventPost(Q.kCGHIDEventTap,Q.CGEventCreateMouseEvent(None,Q.kCGEventLeftMouseDown,(x,y),0))
            self.wait(random.uniform(.1,.16),saved)
        finally:
            Q.CGEventPost(Q.kCGHIDEventTap,Q.CGEventCreateMouseEvent(None,Q.kCGEventLeftMouseUp,(x,y),0))
        self.wait(random.uniform(.06,.1),saved)

    def move(self,point,saved):
        self.guard(saved)
        x,y=point
        if not (saved['left']<=x<saved['left']+saved['width'] and saved['top']<=y<saved['top']+saved['height']):
            raise RuntimeError('Pointer destination outside Roblox')
        Q=self.Q
        Q.CGEventPost(Q.kCGHIDEventTap,Q.CGEventCreateMouseEvent(None,Q.kCGEventMouseMoved,(x,y),0))

    def key(self, key, duration, saved):
        self.guard(saved)
        if key not in KEYS or not 0 < duration <= 2: raise ValueError('Invalid bounded key action')
        Q = self.Q; code = KEYS[key]
        if not accessibility_trusted(): raise RuntimeError('Accessibility permission required')
        self.held.add(code)
        try:
            Q.CGEventPost(Q.kCGHIDEventTap,Q.CGEventCreateKeyboardEvent(None,code,True))
            self.wait(duration,saved)
        finally:
            Q.CGEventPost(Q.kCGHIDEventTap,Q.CGEventCreateKeyboardEvent(None,code,False))
            self.held.discard(code)

    def release(self):
        for code in list(self.held):
            self.Q.CGEventPost(self.Q.kCGHIDEventTap,self.Q.CGEventCreateKeyboardEvent(None,code,False))
        self.held.clear()

def preview(image, centers, size):
    result = image.copy(); draw = ImageDraw.Draw(result)
    for i,(x,y) in enumerate(centers):
        bw,bh = size
        draw.rectangle((x-bw/2,y-bh/2,x+bw/2,y+bh/2),outline='lime',width=3)
        draw.ellipse((x-15,y-15,x+15,y+15),fill='yellow',outline='black',width=2)
        draw.text((x-6,y-6),str(i+1),fill='black')
    return result

def edit_calibration(image, centers, size, rows, cols):
    import tkinter as tk
    from PIL import ImageTk
    root = tk.Tk(); root.title('Tarot calibration — drag centers; Enter saves, Escape cancels')
    scale = min(1,1100/image.width,760/image.height)
    points = [p[:] for p in centers]; selected = [None]; accepted = [False]; manual = []
    canvas = tk.Canvas(root,width=int(image.width*scale),height=int(image.height*scale)); canvas.pack()
    tk.Label(root,text='Drag numbered centers. For a new grid, press R then click center of FIRST and LAST cards. Enter accepts; Esc cancels.').pack()
    pictures = []
    def render():
        photo = ImageTk.PhotoImage(preview(image,points,size).resize((int(image.width*scale),int(image.height*scale))))
        pictures[:] = [photo]; canvas.delete('all'); canvas.create_image(0,0,anchor='nw',image=photo)
    def down(e):
        p = [e.x/scale,e.y/scale]
        if manual:
            manual.append(p)
            if len(manual)==3:
                points[:] = grid_centers(manual[1],manual[2],rows,cols); manual.clear(); render()
        elif points:
            i = min(range(len(points)),key=lambda i: math.dist(points[i],p))
            if math.dist(points[i],p)*scale < 35: selected[0] = i
    def drag(e):
        if selected[0] is not None:
            points[selected[0]] = [max(size[0]/2,min(image.width-size[0]/2,e.x/scale)),max(size[1]/2,min(image.height-size[1]/2,e.y/scale))]; render()
    def accept(e):
        if len(points)==rows*cols and not manual: accepted[0]=True; root.destroy()
    canvas.bind('<Button-1>',down); canvas.bind('<B1-Motion>',drag)
    canvas.bind('<ButtonRelease-1>',lambda e:selected.__setitem__(0,None))
    root.bind('r',lambda e:manual.__setitem__(slice(None),[True]))
    root.bind('<Return>',accept); root.bind('<Escape>',lambda e:root.destroy())
    render(); root.mainloop()
    if not accepted[0]: raise RuntimeError('Calibration cancelled')
    return points

def calibrate(args):
    desktop = Desktop(); win = desktop.window()
    print('Focus Roblox within 5 seconds for calibration.',flush=True)
    time.sleep(5); desktop.guard(win); image = desktop.capture(win)
    try: centers,size = detect_grid(image,args.rows,args.cols)
    except ValueError as e:
        print(e)
        if args.auto: raise
        centers = grid_centers((image.width*.34,image.height*.30),(image.width*.66,image.height*.83),args.rows,args.cols)
        size = [image.width*.065,image.height*.14]
    if not args.auto: centers = edit_calibration(image,centers,size,args.rows,args.cols)
    sx,sy = image.width/win['width'],image.height/win['height']
    config = {'version':1,'window':win,'pixels':[image.width,image.height], 'scale':[sx,sy],
              'rows':args.rows,'cols':args.cols,'centers':centers,'card_size':size,'confirmed':not args.auto}
    # Store the observed backs only once; gameplay frames remain in memory.
    image.save(ROOT/'calibration.png')
    preview(image,centers,size).save(ROOT/'numbered-grid.png')
    Path(args.config).write_text(json.dumps(config,indent=2))
    print(f'Saved {len(centers)} centers. Pixel/logical scale: {sx:.3f}, {sy:.3f}. Confirmed: {config["confirmed"]}')


def template_present(d,c,filename,crop,search,threshold=.82,white_text=False,return_location=False):
    """Small-region template check, scaled from reference pixels to capture pixels."""
    w=c['window']; d.guard(w)
    rect={'left':w['left']+int(search[0]*w['width']),
          'top':w['top']+int(search[1]*w['height']),
          'width':int((search[2]-search[0])*w['width']),
          'height':int((search[3]-search[1])*w['height'])}
    live=d.capture(rect).convert('RGB')
    ref=Image.open(ROOT/filename)
    box=(crop[0]*ref.width,crop[1]*ref.height,crop[2]*ref.width,crop[3]*ref.height)
    tw=max(1,round((crop[2]-crop[0])*w['width']*live.width/rect['width']))
    th=max(1,round((crop[3]-crop[1])*w['height']*live.height/rect['height']))
    temp=ref.crop(box).convert('RGB').resize((tw,th))
    if tw>live.width or th>live.height:return None if return_location else False
    if white_text:
        live_array=(np.min(np.asarray(live),axis=2)>190).astype(np.uint8)*255
        temp_array=(np.min(np.asarray(temp),axis=2)>190).astype(np.uint8)*255
    else:
        live_array=np.asarray(live.convert('L'));temp_array=np.asarray(temp.convert('L'))
    scores=cv2.matchTemplate(live_array,temp_array,cv2.TM_CCOEFF_NORMED)
    _,score,_,point=cv2.minMaxLoc(scores)
    if score<threshold:return None if return_location else False
    if return_location:
        return (rect['left']+(point[0]+tw/2)*rect['width']/live.width,
                rect['top']+(point[1]+th/2)*rect['height']/live.height)
    return True


def reward_visible(d,c):
    return (template_present(d,c,'reward-reference.png',(.432,.302,.566,.34),(.39,.27,.61,.37))
        and template_present(d,c,'reward-reference.png',(.448,.923,.553,.947),(.39,.89,.61,.97),.78))


def station_location(d,c):
    return template_present(d,c,'station-reference.png',(837/2000,750/1394,1070/2000,784/1394),(.18,.3,.82,.8),.77,white_text=True,return_location=True)

def station_visible(d,c):
    return station_location(d,c) is not None


def wait_station_location(d,c,timeout=3):
    deadline=time.monotonic()+timeout
    while True:
        point=station_location(d,c)
        if point is not None:return point
        if time.monotonic()>=deadline:return None
        d.wait(random.uniform(.1,.2),c['window'])


def close_reward_to_station(d,c,max_clicks=3):
    w=c['window']
    for attempt in range(max_clicks):
        if not reward_visible(d,c) and wait_station_location(d,c,timeout=1.0) is not None:
            return
        # A missed close can leave the overlay hiding the station prompt.
        # User-authorized recovery: retry only the bottom close-prompt area.
        d.wait(random.uniform(.2,.6),w)
        d.click((w['left']+random.uniform(.455,.545)*w['width'],
                 w['top']+random.uniform(.927,.94)*w['height']),w)
        print(f'Reward close attempt {attempt+1}/{max_clicks}; checking booth prompt',flush=True)
        d.wait(random.uniform(.45,.85),w)
    if reward_visible(d,c) or wait_station_location(d,c,timeout=3) is None:
        raise RuntimeError('Reward close attempted three times; station still unavailable')


def station_restart(d,c):
    w=c['window']
    deadline=time.monotonic()+8
    while not reward_visible(d,c) and not station_visible(d,c):
        if time.monotonic()>deadline:raise RuntimeError('No reward or station prompt after the round')
        d.wait(.25,w)
    close_reward_to_station(d,c)
    d.wait(random.uniform(.1,.45),w)
    print('Station interaction verified; replaying without movement',flush=True)
    board=Board(d,c)
    d.key('e',random.uniform(1.0,1.18),w)
    board.wait_fresh_board(timeout=12)
    # Intro can show backs before the game enables card input. Do not treat
    # its first back-looking frames as proof of input readiness.
    startup_delay=random.uniform(2.5,3.0)
    d.wait(startup_delay,w)
    board.wait_fresh_board(timeout=12)
    print(f'Fresh board and startup guard confirmed ({startup_delay:.3f}s)',flush=True)
    d.wait(random.uniform(.1,.4),w)
    return board

class Board:
    def __init__(self, desktop, config):
        self.d,self.c = desktop,config
        self.w = config['window']; self.sx,self.sy = config['scale']
        self.boxes = []
        bw,bh = config['card_size']
        for x,y in config['centers']:
            # Interior only: remove card frame and most background.
            self.boxes.append((x-bw*.33,y-bh*.35,x+bw*.33,y+bh*.35))
        base = Image.open(ROOT/'calibration.png')
        self.backs = [feature(base.crop(b)) for b in self.boxes]
        # One capture around the whole grid per observation, never full-screen.
        self.origin = (int(min(b[0] for b in self.boxes)),int(min(b[1] for b in self.boxes)))
        self.extent = (int(math.ceil(max(b[2] for b in self.boxes))),int(math.ceil(max(b[3] for b in self.boxes))))

    def observe(self):
        self.d.guard(self.w)
        ox,oy = self.origin; ex,ey = self.extent
        rect = {'left':self.w['left']+math.floor(ox/self.sx),'top':self.w['top']+math.floor(oy/self.sy),
                'width':math.ceil((ex-ox)/self.sx)+1,'height':math.ceil((ey-oy)/self.sy)+1}
        im = self.d.capture(rect)
        rx,ry = im.width/rect['width'],im.height/rect['height']
        def crop(b):
            return ((self.w['left']+b[0]/self.sx-rect['left'])*rx,
                    (self.w['top']+b[1]/self.sy-rect['top'])*ry,
                    (self.w['left']+b[2]/self.sx-rect['left'])*rx,
                    (self.w['top']+b[3]/self.sy-rect['top'])*ry)
        return [feature(im.crop(crop(b))) for b in self.boxes]

    def travel(self,a,b):
        centers=getattr(self,'c',{}).get('centers')
        if not centers:return abs(a-b)
        return math.hypot((centers[a][0]-centers[b][0])/self.sx,
                          (centers[a][1]-centers[b][1])/self.sy)

    def nearest(self,choices,origin=None):
        origin=getattr(self,'last_card',0) if origin is None else origin
        return min(choices,key=lambda i:(self.travel(origin,i),i))

    def best_pair(self,pairs):
        origin=getattr(self,'last_card',0)
        oriented=[p for a,b in pairs for p in ((a,b),(b,a))]
        return min(oriented,key=lambda p:(self.travel(origin,p[0])+self.travel(p[0],p[1]),p))

    def click(self,i):
        last=getattr(self,'last_click',None)
        if last is not None:
            remaining=last+random.uniform(.45,.8)-time.monotonic()
            if remaining>0:self.d.wait(remaining,self.w)
        else:
            self.d.wait(random.uniform(.05,.12),self.w)
        x,y = self.c['centers'][i]
        bw,bh = self.c['card_size']
        x += random.uniform(-.35*bw,.35*bw)
        y += random.uniform(-.35*bh,.35*bh)
        self.d.click((self.w['left']+x/self.sx,self.w['top']+y/self.sy),self.w)
        self.last_click=time.monotonic()
        self.last_card=i

    def wait_fresh_board(self,timeout=12):
        # Shuffle/intro frames may never meet global stability thresholds.
        # Instead require every card to be a back on two successive observations.
        deadline=time.monotonic()+timeout;consecutive=0
        while time.monotonic()<deadline:
            frames=self.observe()
            consecutive=consecutive+1 if all(self.back(i,f) for i,f in enumerate(frames)) else 0
            if consecutive>=2:return
            self.d.wait(.04,self.w)
        raise RuntimeError('New round did not reach a face-down board before timeout')

    def back(self,i,f):
        reference=self.backs[i]
        if distance(f,reference)<.065:return True
        # Small hover/lighting shifts should not turn a card back into a
        # mysterious new face. Require strong structural similarity.
        if float(np.std(reference))<2:return False
        scores=cv2.matchTemplate(f,reference[2:-2,2:-2],cv2.TM_CCOEFF_NORMED)
        return float(cv2.minMaxLoc(scores)[1])>.93

    def stable(self,seconds=.4,timeout=4,indices=None):
        start = time.monotonic(); last = None; stable_since = start
        while time.monotonic()-start < timeout:
            frames = self.observe()
            selected=range(len(frames)) if indices is None else indices
            if last is None or max(distance(cv2.GaussianBlur(frames[i],(5,5),0),cv2.GaussianBlur(last[i],(5,5),0)) for i in selected) > .025:
                stable_since=time.monotonic()
            if time.monotonic()-stable_since >= seconds: return frames
            last=frames; self.d.wait(.04,self.w)
        raise RecognitionError('Board did not settle; stopped')

    def wait_flipback(self,indices,timeout=5):
        # A single back-looking frame can occur during the animation.
        # Require BOTH full backs continuously, with no structural changes.
        deadline=time.monotonic()+timeout;ready_since=None;previous=None
        while time.monotonic()<deadline:
            frames=self.observe();now=time.monotonic()
            backs=all(self.back(i,frames[i]) for i in indices)
            unchanged=previous is not None and all(distance(frames[i],previous[i])<.015 for i in indices)
            if backs and unchanged:
                if ready_since is None:ready_since=now
                if now-ready_since>=.28:
                    self.d.wait(.08,self.w)
                    verified=self.observe()
                    if all(self.back(i,verified[i]) for i in indices):return verified
                    ready_since=None
            else:ready_since=None
            previous=frames;self.d.wait(.04,self.w)
        raise RecognitionError('Previous mismatched cards have not finished flipping back; no next click sent')

    def pair_ready_wait(self,learn=False,matched=False):
        last=getattr(self,'last_click',None)
        if last is None:return  # Synthetic boards do not emit native clicks.
        elapsed=time.monotonic()-last
        # Bootstrap conservatively; real flip-back observations raise the bound.
        threshold=1.2 if matched else getattr(self,'pair_ready_threshold',1.2)
        if learn:
            threshold=max(threshold,elapsed)
            self.pair_ready_threshold=threshold
        target=threshold+random.uniform(0,.5)
        remaining=target-(time.monotonic()-last)
        if remaining>0:self.d.wait(remaining,self.w)
        kind='match' if matched else 'mismatch'
        print(f'Pair readiness ({kind}): observed={elapsed:.3f}s threshold={threshold:.3f}s target={target:.3f}s',flush=True)

    def reveal(self,i,next_target=None):
        for attempt in range(2):
            self.click(i)
            self.d.wait(random.uniform(.03,.06),self.w)
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                frames=self.stable(.15,2,indices=[i])
                if not self.back(i,frames[i]):
                    face=frames[i]
                    return face
                self.d.wait(random.uniform(.1,.2),self.w)
            if attempt==0: print(f'Card {i+1} stayed face down; retrying once',flush=True)
        raise RecognitionError(f'Card {i+1} did not flip after one retry')

    def reward(self): return reward_visible(self.d,self.c)

    def solve(self):
        if self.reward():
            print('Reward screen confirmed: round complete',flush=True);return
        frames=self.observe()
        if all(self.back(i,f) for i,f in enumerate(frames)):
            self.wait_fresh_board();frames=self.observe()
        else:
            self.d.wait(.4,self.w);frames=self.observe()
        memory=getattr(self,'memory',{})
        self.memory=memory
        rejected=getattr(self,'rejected_pairs',set())
        self.rejected_pairs=rejected
        matched=set(); turns=0; n=len(frames)
        # Resume only visually unambiguous, already exposed matching pairs.
        visible=[i for i,f in enumerate(frames) if not self.back(i,f)]
        unpaired=[]
        while visible:
            a=visible.pop(0)
            choices=sorted((distance(frames[a],frames[b]),b) for b in visible)
            if not choices or choices[0][0]>=.085 or (len(choices)>1 and choices[1][0]-choices[0][0]<.025):
                unpaired.append(a);continue
            b=choices[0][1]; visible.remove(b); matched.update((a,b))
            memory[a],memory[b]=frames[a],frames[b]
        if len(unpaired)>1:
            raise RecognitionError('More than one unpaired visible card; waiting for flip-back')
        open_card=unpaired[0] if unpaired else None
        if open_card is not None:
            memory[open_card]=frames[open_card]
            print(f'Resuming with card {open_card+1} already selected',flush=True)
        if matched: print(f'Resuming: {len(matched)}/{n} cards already matched',flush=True)
        while len(matched)<n and turns < n*2:
            pending=[i for i in range(n) if i not in matched]
            pairs=[(a,b) for a in pending for b in pending if a<b and a in memory and b in memory
                   and (a,b) not in rejected and distance(memory[a],memory[b])<.085]
            if open_card is not None:
                a,b=open_card,None
                open_card=None
            else:
                eligible=[i for i in pending if any(tuple(sorted((i,j))) not in rejected for j in pending if j!=i)]
                if not eligible:raise RecognitionError('All remaining pairs contradicted by observed mismatches; refusing repeated guesses')
                a,b = self.best_pair(pairs) if pairs else (self.nearest([i for i in eligible if i not in memory] or eligible),None)
                provisional_b=b
                memory[a]=self.reveal(a,next_target=provisional_b)
            if b is None:
                candidates=sorted((distance(memory[a],memory[i]),i) for i in pending if i!=a and i in memory and tuple(sorted((a,i))) not in rejected)
                possible=[i for score,i in candidates if score<.085]
                if possible: b=self.nearest(possible,origin=a)
                else:
                    available=[i for i in pending if i!=a and tuple(sorted((a,i))) not in rejected]
                    if not available:raise RecognitionError('No untried partner for selected card; refusing repeated mismatch')
                    unseen=[i for i in available if i not in memory]
                    b=self.nearest(unseen,origin=a) if unseen else min(available,key=lambda i:(distance(memory[a],memory[i]),self.travel(a,i)))
            next_candidate=next((i for i in pending if i not in (a,b) and i not in memory),None)
            memory[b]=self.reveal(b,next_target=next_candidate); turns+=1
            self.d.wait(random.uniform(.02,.05),self.w)
            deadline=time.monotonic()+7
            confirmed=False
            while True:
                if self.reward():
                    print('Reward screen confirmed: round complete',flush=True);return
                after=self.stable(random.uniform(.12,.2),3,indices=[a,b])
                if self.back(a,after[a]) and self.back(b,after[b]):
                    after=self.wait_flipback((a,b))
                    self.pair_ready_wait(learn=True)
                    after=self.observe()
                    if not all(self.back(i,after[i]) for i in (a,b)):
                        raise RecognitionError('Pair changed after flip-back readiness check')
                    rejected.add(tuple(sorted((a,b))))
                    print(f'Cards {a+1}, {b+1}: mismatch returned face down; pair excluded for this round',flush=True)
                    break
                # Classify the settled pair rather than two different moments
                # of their reveal animations. Persistent faces are the match signal.
                if not self.back(a,after[a]) and not self.back(b,after[b]) and distance(after[a],after[b])<.085:
                    self.pair_ready_wait(matched=True)
                    verified=self.stable(.15,3,indices=[a,b])
                    if (not self.back(a,verified[a]) and not self.back(b,verified[b])
                        and distance(verified[a],verified[b])<.085):
                        matched.update((a,b)); memory[a],memory[b]=verified[a],verified[b]
                        after=verified; confirmed=True
                        print(f'Confirmed {len(matched)}/{n}',flush=True)
                        break
                if time.monotonic()>deadline:
                    raise RecognitionError('Pair result unclear after waiting; stopped for inspection')
                self.d.wait(random.uniform(.12,.3),self.w)
            # Other unseen cards must remain backs; rejects many overlays/scene transitions.
            other=[i for i in pending if i not in (a,b) and i not in matched]
            deadline=time.monotonic()+4
            while any(not self.back(i,after[i]) for i in other):
                if time.monotonic()>deadline:
                    changed=[i+1 for i in other if not self.back(i,after[i])]
                    raise RecognitionError(f'Unselected card appearance changed: {changed}')
                self.d.wait(random.uniform(.12,.25),self.w)
                after=self.observe()
        if len(matched)!=n: raise RuntimeError('Turn limit reached')
        print('All pairs visually confirmed.')


def solve_with_recovery(board,max_recoveries=5):
    # Only recognition failures are recoverable. Input/focus/window/stop
    # exceptions bypass this handler and cannot cause automatic restart.
    for attempt in range(max_recoveries+1):
        try:
            return board.solve()
        except RecognitionError as exc:
            if attempt==max_recoveries:raise
            print(f'Reading board again ({attempt+1}/{max_recoveries}); retaining card memory: {exc}',flush=True)
            board.d.wait(random.uniform(.5,.9),board.w)


def reanchor_window(config, current):
    saved=config['window']
    if any(current[k]!=saved[k] for k in ('id','pid','width','height')):
        raise RuntimeError(f'Recalibration required: saved window {saved["width"]}x{saved["height"]} (ID {saved["id"]}); current {current["width"]}x{current["height"]} (ID {current["id"]}). Choose Calibrate in Run.command.')
    # Card coordinates are window-relative. Only a translation is safe to rebind.
    config['window']=current


def run(args):
    c=json.loads(Path(args.config).read_text())
    if c.get('version')!=1 or len(c['centers'])!=c['rows']*c['cols']:
        raise ValueError('Invalid calibration; recalibrate')
    if not c['confirmed']: raise RuntimeError('Review calibration first: run calibrate without --auto')
    if args.rounds==0 or args.rounds>1:
        if not args.route and not args.station_loop: raise ValueError('Repeat requires --station-loop or a taught --route')
        if not args.station_loop: validate_route(json.loads(Path(args.route).read_text()))
    d=Desktop()
    # Poll Escape independently as well as in guarded waits.
    def watch():
        while not STOP.wait(.02):
            if d.Q.CGEventSourceKeyState(d.Q.kCGEventSourceStateCombinedSessionState,53): STOP.set()
    threading.Thread(target=watch,daemon=True).start()
    signal.signal(signal.SIGINT,lambda *_:STOP.set())
    print(f'Focus Roblox within {args.delay} seconds. Escape, Ctrl-C, or pointer at main display top-left stops.',flush=True)
    try:
        if STOP.wait(args.delay): return
        reanchor_window(c,d.window())
        board=Board(d,c)
        if args.station_loop and (reward_visible(d,c) or station_visible(d,c)):
            board=station_restart(d,c)
        if args.command=='inspect':
            frames=board.stable(); print(['BACK' if board.back(i,f) else 'CHANGED' for i,f in enumerate(frames)]); return
        for round_index in (itertools.count() if args.rounds==0 else range(args.rounds)):
            print(f'Round {round_index+1} starting',flush=True)
            solve_with_recovery(board)
            if args.rounds==0 or round_index+1 < args.rounds:
                if args.station_loop:
                    threshold=getattr(board,'pair_ready_threshold',1.2)
                    board=station_restart(d,c)
                    board.pair_ready_threshold=threshold
                else:
                    execute_route(d,c,json.loads(Path(args.route).read_text()))
                    board=Board(d,c)
    finally: d.release(); STOP.set()

def anchor(d,c,step):
    rect=step['rect']
    w=c['window']
    if not (w['left']<=rect['left'] and w['top']<=rect['top'] and rect['left']+rect['width']<=w['left']+w['width'] and rect['top']+rect['height']<=w['top']+w['height']):
        raise ValueError('Anchor outside Roblox')
    d.guard(w)
    expected=feature(Image.open(ROOT/step['image']))
    return distance(feature(d.capture(rect)),expected)<.045

def validate_route(route):
    if not isinstance(route,list) or not 2<=len(route)<=30:
        raise ValueError('Route requires 2..30 steps')
    if route[-1].get('action')!='check':
        raise ValueError('Route must end with a visual return checkpoint')
    for step in route:
        if 'rect' not in step or 'image' not in step:
            raise ValueError('Every route step needs a visual precondition')
        if step.get('action') not in ('check','key','jitter'):
            raise ValueError('Unknown route action')
        if step['action']=='key' and (step.get('key') not in KEYS or not 0<float(step.get('seconds',0))<=2):
            raise ValueError('Invalid bounded key action')
    for i,step in enumerate(route):
        if step['action']=='jitter' and (i+1==len(route) or route[i+1]['action']!='check'):
            raise ValueError('Random movement must be immediately followed by a visual return check')


def teach_route(args):
    c=json.loads(Path(args.config).read_text()); d=Desktop(); route=[]
    print('Teach from the POST-ROUND screen. Each action captures a visual precondition.')
    print('Commands: key w 0.1 (or a/s/d/e/space), jitter, check, save, cancel.')
    print('Use a fixed camera. Select an anchor rectangle in GLOBAL logical coordinates.')
    print('The anchor should show distinctive static scenery; exclude chat, timer and avatar animations.')
    values=input('Anchor left top width height: ').split()
    if len(values)!=4: raise ValueError('Four numbers required')
    rect=dict(zip(('left','top','width','height'),map(int,values)))
    try:
        while len(route)<30:
            command=input('Next action: ').strip().split()
            if not command: continue
            if command[0]=='cancel': return
            if command[0]=='save':
                validate_route(route)
                dest=Path(args.route or ROOT/'route.json'); dest.write_text(json.dumps(route,indent=2))
                print('Saved route. Repeated runs still verify every checkpoint.'); return
            step={'action':command[0],'rect':rect.copy(),'image':f'route-anchor-{len(route):02}.png'}
            if command[0]=='key':
                if len(command)!=3 or command[1] not in KEYS or not 0<float(command[2])<=2:
                    raise ValueError('Use key w/a/s/d/e/space duration (0..2 seconds)')
                step.update(key=command[1],seconds=float(command[2]))
            elif command[0] not in ('check','jitter'): raise ValueError('Unknown command')
            print('Focus Roblox: capturing and acting in 5 seconds.',flush=True)
            time.sleep(5); d.guard(c['window']); d.capture(rect).save(ROOT/step['image'])
            if step['action']=='key': d.key(step['key'],step['seconds'],c['window'])
            elif step['action']=='jitter':
                key=random.choice(['w','a','s','d']); duration=random.uniform(.08,.16)
                d.key(key,duration,c['window']); d.key({'w':'s','s':'w','a':'d','d':'a'}[key],duration,c['window'])
            route.append(step); print('Action complete. Return to terminal to teach the next step.')
    finally: d.release()


def execute_route(d,c,route):
    """Bounded taught sequence with visual checkpoints; no blind walk loop."""
    validate_route(route)
    for step in route:
        if 'rect' not in step or 'image' not in step: raise ValueError('Every route step needs a visual precondition')
        if not anchor(d,c,step): raise RuntimeError('Station route visual precondition failed')
        if step.get('action')=='jitter':
            # Equal inverse duration is only an attempt; the next anchor verifies return.
            key=random.choice(['w','a','s','d']); duration=random.uniform(.08,.16)
            d.key(key,duration,c['window']); d.key({'w':'s','s':'w','a':'d','d':'a'}[key],duration,c['window'])
            d.wait(.5,c['window'])
            if not anchor(d,c,step): raise RuntimeError('Random movement did not return to the station view')
        elif step.get('action')=='key': d.key(step['key'],float(step['seconds']),c['window'])
        elif step.get('action')!='check': raise ValueError('Unknown route action')
        d.wait(.5,c['window'])
    if not route or route[-1].get('action')!='check': raise ValueError('Route must end with a visual return checkpoint')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('command',choices=['calibrate','inspect','play','teach-route'])
    p.add_argument('--config',default=str(ROOT/'calibration.json'))
    p.add_argument('--rows',type=int,default=4); p.add_argument('--cols',type=int,default=4)
    p.add_argument('--auto',action='store_true',help='Save unconfirmed detection preview without GUI')
    p.add_argument('--rounds',type=int,default=1,help='0 repeats until stopped; 1..20 runs a bounded session'); p.add_argument('--route')
    p.add_argument('--station-loop',action='store_true',help='Close known reward, verify station and hold E without movement')
    p.add_argument('--delay',type=float,default=5,help='Seconds to focus Roblox before input')
    a=p.parse_args()
    if not 0<=a.delay<=60: p.error('delay must be 0..60')
    if not 0<=a.rounds<=20: p.error('rounds must be 0 (until stopped), or 1..20')
    lock=(ROOT/'.running.lock').open('w')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        print('STOPPED: Another tarot tool instance is already running. Stop it with Escape first.');return
    try:
        if a.command=='calibrate': calibrate(a)
        elif a.command=='teach-route': teach_route(a)
        else: run(a)
    except (RuntimeError,ValueError) as e:
        print(f'STOPPED: {e}'); raise SystemExit(1)

if __name__=='__main__': main()
