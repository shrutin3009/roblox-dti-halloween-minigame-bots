import json,time
import tarot
c=json.loads((tarot.ROOT/'calibration.json').read_text())
d=tarot.Desktop();time.sleep(2)
c['window']=d.window();d.guard(c['window'])
print('Window:',c['window'],flush=True)
im=d.capture(c['window']);im.save(tarot.ROOT/'native-diagnostic.png')
print('Native image size:',im.size,flush=True)
for _ in range(5):
 print('Station location:',tarot.station_location(d,c),flush=True);d.wait(.15,c['window'])
