import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image
import apple_bobber as a

class Tests(unittest.TestCase):
    def test_recorded_game_frames(self):
        fixtures=a.ROOT.parents[1]/'work/apple_probe'
        paths=sorted(fixtures.glob('frame-*.png'))
        if not paths:self.skipTest('Recorded fixtures unavailable')
        found=0
        for path in paths:
            im=Image.open(path);roi=im.crop((120,int(697*.70),880,int(697*.92)))
            sample=a.detect(roi)
            if sample:
                found+=1
                self.assertGreater(sample['confidence'],.78)
                self.assertTrue(0<sample['apple_x']<roi.width)
        self.assertGreaterEqual(found,len(paths)*.9)
    def test_random_ticket_points_stay_in_button(self):
        w={'left':40,'top':60,'width':1000,'height':697}
        points=[a.ticket_point(w) for _ in range(1000)]
        self.assertEqual(len(set(points)),1000)
        for x,y in points:
            self.assertTrue(315<=x<=385)
            self.assertTrue(60+697*.655<=y<=60+697*.700)

    def test_transition_refuses_unconfirmed_reward(self):
        with patch.object(a,'wait_for_reward',return_value=False):
            with self.assertRaises(RuntimeError):a.replay_transition(object(),{})

    def test_zero_ticket_detection(self):
        im=Image.open(a.ROOT/'inventory-reference.png').resize((1000,697))
        self.assertFalse(a.tier_one_empty(im))
        im.paste(im.crop((480,427,520,449)),(290,427))
        self.assertTrue(a.tier_one_empty(im))

    def test_confirmed_reward_retries_close_without_single_frame_rejection(self):
        class D:
            def __init__(self):self.clicks=[];self.keys=[]
            def click(self,p,w):self.clicks.append(p)
            def key(self,k,t,w):self.keys.append(k)
            def wait(self,*args):pass
        d=D();w={'left':0,'top':0,'width':1000,'height':697}
        with patch.object(a,'wait_for_reward',side_effect=[True,False]):
            a.replay_transition(d,w,confirmed=True)
        self.assertEqual(len(d.clicks),2)
        self.assertEqual(len(d.keys),2)
        d=D()
        with patch.object(a,'wait_for_reward',return_value=True):
            with self.assertRaises(RuntimeError):a.replay_transition(d,w,confirmed=True)
        self.assertEqual(len(d.clicks),3)
        self.assertEqual(d.keys,[])

    def test_blank_is_not_game(self):
        self.assertIsNone(a.detect(Image.new('RGB',(760,153),'black')))
    def test_control_direction_and_braking(self):
        c=a.Controller()
        self.assertTrue(c.decide({'bar_x':200,'apple_x':400,'scale':1},0)[0])
        self.assertFalse(c.decide({'bar_x':450,'apple_x':400,'scale':1},.2)[0])
    def test_release_does_not_need_focus(self):
        events=[]
        class Q:
            kCGHIDEventTap=0;kCGEventLeftMouseUp=3
            @staticmethod
            def CGEventCreateMouseEvent(src,t,p,b):return t
            @staticmethod
            def CGEventPost(t,e):events.append(e)
        class D:pass
        d=D();d.Q=Q
        m=a.Mouse(d,{},(10,10));m.down=True;m.release()
        self.assertEqual(events,[3]);self.assertFalse(m.down)
    def test_start_opens_e_and_uses_ticket_once(self):
        events=[]
        class D:
            def capture(self,w):return Image.new('RGB',(1000,697),'black')
            def key(self,k,t,w):events.append(('key',k))
            def click(self,p,w):events.append(('click',p))
            def wait(self,*args):pass
        w={'left':10,'top':20,'width':1000,'height':697}
        with tempfile.TemporaryDirectory() as folder,patch.object(a,'ROOT',Path(folder)),patch.object(a,'inventory_visible',side_effect=[False,True]),patch.object(a,'tier_one_empty',return_value=False):
            a.start_tier_one(D(),w)
        self.assertEqual(events[0],('key','e'))
        self.assertEqual(sum(e[0]=='click' for e in events),1)

    def test_open_inventory_does_not_toggle_e(self):
        events=[]
        class D:
            def capture(self,w):return Image.new('RGB',(1000,697),'black')
            def key(self,*args):raise AssertionError('Inventory already open')
            def click(self,*args):events.append('click')
            def wait(self,*args):pass
        w={'left':0,'top':0,'width':1000,'height':697}
        with tempfile.TemporaryDirectory() as folder,patch.object(a,'ROOT',Path(folder)),patch.object(a,'inventory_visible',return_value=True),patch.object(a,'tier_one_empty',return_value=False):
            a.start_tier_one(D(),w)
        self.assertEqual(events,['click'])

    def test_winning_reward_screen(self):
        path=a.ROOT/'test-win.png'
        if not path.exists():self.skipTest('Live win fixture unavailable')
        class D:
            def guard(self,w):pass
            def capture(self,r):
                im=Image.open(path).resize((1000,697))
                return im.crop((r['left'],r['top'],r['left']+r['width'],r['top']+r['height']))
        self.assertTrue(a.tarot.reward_visible(D(),{'window':{'left':0,'top':0,'width':1000,'height':697}}))

    def test_retina_detection(self):
        path=a.ROOT.parents[1]/'work/apple_probe/frame-31.png'
        if not path.exists():self.skipTest('Fixture unavailable')
        im=Image.open(path).crop((120,int(697*.70),880,int(697*.92)))
        one=a.detect(im);two=a.detect(im.resize((im.width*2,im.height*2)))
        self.assertIsNotNone(two)
        self.assertLess(abs(one['apple_x']-two['apple_x']/2),2)
        self.assertLess(abs(one['bar_x']-two['bar_x']/2),3)

if __name__=='__main__':unittest.main()
