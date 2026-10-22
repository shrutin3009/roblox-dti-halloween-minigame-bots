import unittest
from unittest.mock import patch
import numpy as np
from PIL import Image,ImageDraw
import tarot

class LogicTests(unittest.TestCase):
    def test_close_retries_missing_booth_prompt(self):
        class Input:
            def __init__(self):self.clicks=[]
            def click(self,p,w):self.clicks.append(p)
            def wait(self,*args):pass
        c={'window':{'left':10,'top':20,'width':1000,'height':697}}
        d=Input()
        with patch('tarot.reward_visible',return_value=False),patch('tarot.wait_station_location',side_effect=[None,None,(20,30)]):
            tarot.close_reward_to_station(d,c)
        self.assertEqual(len(d.clicks),2)
        for x,y in d.clicks:
            self.assertTrue(465<=x<=555)
            self.assertTrue(20+697*.927<=y<=20+697*.94)
        d=Input()
        with patch('tarot.reward_visible',return_value=False),patch('tarot.wait_station_location',return_value=(20,30)):
            tarot.close_reward_to_station(d,c)
        self.assertEqual(d.clicks,[])
        d=Input()
        with patch('tarot.reward_visible',return_value=True):
            with self.assertRaises(RuntimeError):tarot.close_reward_to_station(d,c)
        self.assertEqual(len(d.clicks),3)

    def test_grid_and_retina(self):
        points=tarot.grid_centers((100,200),(700,800),4,4)
        self.assertEqual(len(points),16)
        self.assertEqual(points[5],[300,400])
        self.assertEqual((points[5][0]/2+40,points[5][1]/2+80),(190,280))
    def test_random_click_bounds_and_scaling(self):
        class Input:
            def click(self,point,window): self.point=point
            def move(self,point,window): self.pointer=point
            def wait(self,seconds,window): pass
        board=object.__new__(tarot.Board)
        board.c={'centers':[[400,600]],'card_size':[100,200]}
        board.w={'left':30,'top':50};board.sx=board.sy=2;board.d=Input()
        for extreme in [-1,1]:
            with patch('tarot.random.uniform',side_effect=lambda a,b: a if extreme<0 else b):
                board.click(0)
            x,y=board.d.point
            self.assertTrue(212.5<=x<=247.5)
            self.assertTrue(315<=y<=385)
            self.assertEqual(board.last_card,0)

    def test_distance_selection_and_pair_orientation(self):
        b=object.__new__(tarot.Board)
        b.c={'centers':[[0,0],[1000,0],[1010,0],[20,0]]}
        b.sx=b.sy=1;b.last_card=0
        self.assertEqual(b.nearest([1,3]),3)
        self.assertEqual(b.best_pair([(1,2),(0,3)]),(0,3))
        b.last_card=2
        self.assertEqual(b.best_pair([(0,1)]),(1,0))

    def test_fresh_board_waits_through_intro(self):
        class Input:
            def wait(self,*args):pass
        class Transition(tarot.Board):
            def __init__(self): self.d=Input();self.w={};self.calls=0
            def observe(self):
                self.calls+=1
                return [self.calls>=4]*16
            def back(self,i,frame):return frame
            def stable(self,*args,**kwargs):raise AssertionError('Must not use global stability during intro')
        b=Transition();b.wait_fresh_board(timeout=1)
        self.assertEqual(b.calls,5)

    def test_stability_ignores_unrelated_animated_card(self):
        clock=[0.0]
        class Input:
            def wait(self,t,w):clock[0]+=t
        class Animated(tarot.Board):
            def __init__(self):self.d=Input();self.w={};self.tick=0
            def observe(self):
                self.tick+=1
                return [np.zeros((48,32,3),dtype=np.uint8),np.full((48,32,3),255 if self.tick%2 else 0,dtype=np.uint8)]
        with patch('tarot.time.monotonic',side_effect=lambda:clock[0]):
            result=Animated().stable(.15,.5,indices=[0])
        self.assertEqual(len(result),2)

    def test_reanchor(self):
        old={'id':1,'pid':2,'width':1000,'height':697,'left':459,'top':118}
        c={'window':old.copy()}; moved=dict(old,left=100,top=50)
        tarot.reanchor_window(c,moved)
        self.assertEqual(c['window'],moved)
        with self.assertRaises(RuntimeError):tarot.reanchor_window(c,dict(moved,width=1200))
        with self.assertRaises(RuntimeError):tarot.reanchor_window(c,dict(moved,id=9))

    def test_features(self):
        a=tarot.feature(Image.new('RGB',(100,150),'red'))
        b=tarot.feature(Image.new('RGB',(200,300),'red'))
        c=tarot.feature(Image.new('RGB',(100,150),'blue'))
        self.assertEqual(tarot.distance(a,b),0)
        self.assertGreater(tarot.distance(a,c),.5)
    def test_synthetic_detection(self):
        im=Image.new('RGB',(1000,800),'black'); d=ImageDraw.Draw(im)
        for y in [110,280,450,620]:
            for x in [330,440,550,660]: d.rectangle((x-30,y-48,x+30,y+48),outline='white',width=3)
        points,size=tarot.detect_grid(im,4,4)
        self.assertEqual(len(points),16)
        self.assertLess(abs(points[0][0]-330),2)
        with self.assertRaises(ValueError):tarot.detect_grid(im,3,4)
    def test_memory_matcher(self):
        # Deterministic game with mismatch flips and persistent matched faces.
        class FakeDesktop:
            def wait(self,*args):pass
        class Sim(tarot.Board):
            def __init__(self):
                self.d=FakeDesktop();self.w={}; self.ids=[1,2,3,1,3,2]
                self.backs=[np.zeros((48,32,3),dtype=np.uint8) for _ in self.ids]
                self.open=[];self.done=set();self.clicks=[]
            def stable(self,*args,**kwargs):
                return [np.full((48,32,3),self.ids[i]*70,dtype=np.uint8) if i in self.done or i in self.open else self.backs[i] for i in range(6)]
            def observe(self):return self.stable()
            def reward(self): return False
            def reveal(self,i,next_target=None):
                self.clicks.append(i);self.open.append(i)
                face=np.full((48,32,3),self.ids[i]*70,dtype=np.uint8)
                if len(self.open)==2:
                    a,b=self.open
                    if self.ids[a]==self.ids[b]:self.done.update((a,b))
                    self.open=[]
                return face
        # Make distinct faces look deceptively similar: actual flip-back must
        # override similarity, and a failed pair must never be selected twice.
        misleading=Sim()
        actual_distance=tarot.distance
        def similar_faces(a,b):
            if np.any(a) and np.any(b):return .01
            return actual_distance(a,b)
        with patch('tarot.distance',side_effect=similar_faces):misleading.solve()
        attempts=[tuple(sorted(misleading.clicks[i:i+2])) for i in range(0,len(misleading.clicks),2)]
        self.assertEqual(len(attempts),len(set(attempts)))
        self.assertEqual(len(misleading.done),6)
        self.assertTrue(misleading.rejected_pairs)
        s=Sim();s.solve();self.assertEqual(len(s.done),6)
        self.assertLessEqual(len(s.clicks),12)
        resumed=Sim();resumed.done={0,3};resumed.solve()
        self.assertEqual(len(resumed.done),6)
        self.assertNotIn(0,resumed.clicks);self.assertNotIn(3,resumed.clicks)
        single=Sim();single.open=[0];single.solve()
        self.assertEqual(len(single.done),6)
        self.assertNotEqual(single.clicks[0],0)
    def test_observed_board(self):
        path=tarot.ROOT/'observed-roblox.png'
        if not path.exists(): self.skipTest('No captured fixture')
        points,size=tarot.detect_grid(Image.open(path),4,4)
        self.assertEqual(len(points),16)
        self.assertLess(abs(points[0][0]-689),6)
        self.assertLess(abs(points[-1][1]-1151),6)

    def test_reward_and_station_templates(self):
        fixtures=["reward-reference.png","station-after-move.png","station-current.png","station-close-view.png"]
        if any(not (tarot.ROOT/name).exists() for name in fixtures):
            self.skipTest("Optional local station captures unavailable")
        class Capture:
            def __init__(self,name):self.im=Image.open(tarot.ROOT/name).resize((1000,697))
            def guard(self,w):pass
            def capture(self,r):return self.im.crop((r['left'],r['top'],r['left']+r['width'],r['top']+r['height']))
        c={'window':{'left':0,'top':0,'width':1000,'height':697}}
        reward=Capture('reward-reference.png')
        station=Capture('station-after-move.png')
        self.assertTrue(tarot.reward_visible(reward,c))
        self.assertFalse(tarot.reward_visible(station,c))
        self.assertTrue(tarot.station_visible(station,c))
        self.assertTrue(tarot.station_visible(Capture('station-current.png'),c))
        self.assertTrue(tarot.station_visible(Capture('station-close-view.png'),c))
        self.assertFalse(tarot.station_visible(reward,c))

    def test_prompt_reacquisition(self):
        class Input:
            def wait(self,*args):pass
        with patch('tarot.station_location',side_effect=[None,None,(20,30)]):
            self.assertEqual(tarot.wait_station_location(Input(),{'window':{}}),(20,30))

    def test_recognition_recovery_preserves_memory(self):
        class Input:
            def wait(self,*args):pass
        class Flaky:
            d=Input();w={}
            def __init__(self):self.calls=0;self.memory={}
            def solve(self):
                self.calls+=1
                if self.calls==1:
                    self.memory[3]='remembered face'
                    raise tarot.RecognitionError('temporary glow')
                self.asserted=self.memory[3]
        b=Flaky();tarot.solve_with_recovery(b)
        self.assertEqual(b.calls,2);self.assertEqual(b.asserted,'remembered face')

    def test_stop_and_focus_failures_are_not_retried(self):
        class Stopped:
            def __init__(self):self.calls=0
            def solve(self):self.calls+=1;raise RuntimeError('Escape pressed')
        b=Stopped()
        with self.assertRaises(RuntimeError):tarot.solve_with_recovery(b)
        self.assertEqual(b.calls,1)

    def test_native_click_event_order(self):
        events=[]
        class Q:
            kCGHIDEventTap=0;kCGEventMouseMoved=1;kCGEventLeftMouseDown=2;kCGEventLeftMouseUp=3
            @staticmethod
            def CGEventCreateMouseEvent(source,kind,point,button):return kind
            @staticmethod
            def CGEventPost(tap,event):events.append(event)
        d=object.__new__(tarot.Desktop);d.Q=Q;d.guard=lambda saved:None
        d.wait=lambda seconds,saved:events.append(('wait',seconds))
        with patch('tarot.accessibility_trusted',return_value=True):
            d.click((20,30),{'left':0,'top':0,'width':100,'height':100})
        self.assertEqual([e for e in events if isinstance(e,int)],[1,2,3])
        self.assertEqual(len(events),6)
        self.assertEqual(events[0],1);self.assertEqual(events[2],2);self.assertEqual(events[4],3)
        self.assertTrue(.04<=events[1][1]<=.08)
        self.assertTrue(.1<=events[3][1]<=.16)
        self.assertTrue(.06<=events[5][1]<=.1)

    def test_pair_readiness_learns_and_jitters_within_half_second(self):
        clock=[2.];waits=[]
        class Input:
            def wait(self,t,w):waits.append(t);clock[0]+=t
        b=object.__new__(tarot.Board);b.d=Input();b.w={};b.last_click=0.
        with patch('tarot.time.monotonic',side_effect=lambda:clock[0]),patch('tarot.random.uniform',return_value=.3):
            b.pair_ready_wait(learn=True)
        self.assertEqual(b.pair_ready_threshold,2.)
        self.assertAlmostEqual(waits[0],.3)
        b.last_click=clock[0];clock[0]+=.4
        with patch('tarot.time.monotonic',side_effect=lambda:clock[0]),patch('tarot.random.uniform',return_value=.5):
            b.pair_ready_wait()
        self.assertAlmostEqual(clock[0]-b.last_click,2.5)
        # Slow mismatch animations must not inflate correct-match cooldown.
        b.pair_ready_threshold=3.5;b.last_click=clock[0];clock[0]+=.6
        with patch('tarot.time.monotonic',side_effect=lambda:clock[0]),patch('tarot.random.uniform',return_value=.2):
            b.pair_ready_wait(matched=True)
        self.assertAlmostEqual(clock[0]-b.last_click,1.4)
        self.assertEqual(b.pair_ready_threshold,3.5)


    def test_flipback_rejects_temporary_back_frame(self):
        clock=[0.];reads=[]
        class Input:
            def wait(self,seconds,w):clock[0]+=seconds
        class Flip(tarot.Board):
            def __init__(self):self.d=Input();self.w={};self.calls=0
            def observe(self):
                self.calls+=1
                # A misleading back frame is followed by another face frame.
                value=0 if self.calls==1 or self.calls>=4 else 100
                reads.append(value)
                return [np.full((2,2,3),value,dtype=np.uint8)]*2
            def back(self,i,frame):return not np.any(frame)
        b=Flip()
        with patch('tarot.time.monotonic',side_effect=lambda:clock[0]):b.wait_flipback((0,1))
        self.assertGreaterEqual(clock[0],.48)
        self.assertEqual(reads[-1],0)
        self.assertGreater(b.calls,4)

    def test_reveal_waits_for_face_without_extra_pointer_move(self):
        events=[]
        class Input:
            def wait(self,*args):pass
        class Reveal(tarot.Board):
            def __init__(self):self.d=Input();self.w={};self.reads=0
            def click(self,i):events.append('click')
            def stable(self,*args,**kwargs):
                self.reads+=1;events.append('back' if self.reads==1 else 'face')
                return [self.reads>1]
            def back(self,i,f):return not f
            def prepare(self,i):events.append(('move',i))
        b=Reveal();self.assertTrue(b.reveal(0,next_target=1))
        self.assertEqual(events,['click','back','face'])

    def test_route_preflight(self):
        with self.assertRaises(ValueError):tarot.validate_route([{'action':'jitter'}])

if __name__=='__main__':unittest.main()
