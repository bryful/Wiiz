"""Original Wizardry Turbo File backup/restore and character transfer, isolated saves."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import os,subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
exe=str(Path(sys.argv[1]).resolve())
env=dict(os.environ,SDL_VIDEO_DRIVER='dummy',SDL_AUDIO_DRIVER='dummy',SDL_RENDER_DRIVER='software')
BASE='DDDDADDDA'
with tempfile.TemporaryDirectory(dir=ROOT/'output',prefix='tf-check-') as tmp:
 def group(edited):
  folder=Path(tmp)/('edited' if edited else 'normal');folder.mkdir()
  names=['wiz1p','wiz2p','wiz3p'] if edited else ['wiz1','WIZ2','WIZ3']
  def run(game,keys):
   # III shows Start game on subsequent boots; new battery data skips it.
   name=names[game-1];save=folder/'saves'/(name+'.sav')
   if game==3 and save.exists():keys='A'+keys
   (folder/'keys.txt').write_text(keys)
   p=subprocess.run([exe,'--turbofile-check',str(ROOT/'.nes'/(name+'.nes')),str(folder)],env=env,capture_output=True,text=True,timeout=60)
   assert p.returncode==0,(name,keys,p.stdout+p.stderr)
   return save.read_bytes()
  def record(data,game,slot):
   start,stride,payload=(0,256,112) if game==1 else (0x400,96,94)
   return data[start+(slot-1)*stride:start+(slot-1)*stride+payload]
  def rename(game,text):
   save=folder/'saves'/(names[game-1]+'.sav');d=bytearray(save.read_bytes());offset=0 if game==1 else 0x400
   codes=[ord(c)-48 if c.isdigit() else ord(c)-55 for c in text] if game==1 else list(text.encode())
   d[offset+1]=len(codes);d[offset+2:offset+10]=bytes(codes+[36 if game==1 else 32]*(8-len(codes)))
   level=35 if game==1 else 33;d[offset+level:offset+level+2]=bytes([0,13]);save.write_bytes(d)
  run(1,BASE);rename(1,'TFR1')
  # Export, roll back the device + CPU state, export again.
  source=run(1,BASE+'SALA')
  card=(folder/'turbofile.tbf').read_bytes();assert len(card)==8192 and any(card)
  assert (folder/'observed.tbf').read_bytes()==card
  dest2=run(2,BASE+'DDAAAA');dest3=run(3,BASE+'DDAAA')
  for game,data in [(2,dest2),(3,dest3)]:
   r=record(data,game,7);assert r[0] and r[1]==4 and r[2:6]==b'TFR1',(names,game,r.hex())
  rename(2,'TFR2');run(2,BASE+'A')
  dest3=run(3,BASE+'DDADAAA')
  r=record(dest3,3,8);assert r[0] and r[2:6]==b'TFR2',(names,r.hex())
  # All three original ROMs verify the writes and restore the full roster.
  for game in (1,2,3):
   exported=run(game,BASE+'AA') # second A confirms overwrite if this file exists
   rename(game,'BAD1')
   restored=run(game,BASE+'DAA')
   for slot in range(1,21):
    assert record(restored,game,slot)==record(exported,game,slot),(names[game-1],slot,'backup restore')
   rebooted=run(game,'')
   for slot in range(1,21):assert record(rebooted,game,slot)==record(restored,game,slot)
  assert list((folder/'backups'/'turbofile').glob('*.tbf'))
  print(('edited' if edited else 'normal')+': I->II descendants, I->III and II->III transfer, I/II/III backup/readback/reboot, shared 8KB card, state rollback, automatic backups: OK',flush=True)
 with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(group,(False,True)))

 badfolder=Path(tmp)/'invalid';badfolder.mkdir();image=bytes(8191);(badfolder/'turbofile.tbf').write_bytes(image)
 p=subprocess.run([exe,'--turbofile-check',str(ROOT/'.nes/wiz1.nes'),str(badfolder)],env=env,capture_output=True,text=True,timeout=30)
 assert p.returncode!=0 and (badfolder/'turbofile.tbf').read_bytes()==image
 print('Invalid Turbo File image rejected without overwriting it: OK',flush=True)
