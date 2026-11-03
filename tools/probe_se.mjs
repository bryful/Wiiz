/** Verify Wiz1's $0602 sound requests with the existing JSNES runtime. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import assert from 'node:assert/strict';
import NES from '../third_party/jsnes/src/nes.js';
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const rom = new Uint8Array(fs.readFileSync(path.join(root,'.nes/wiz1.nes')));
assert.equal(createHash('sha256').update(rom).digest('hex'), '38da945c819fab8255a1b3b8ad7c7ea162b51e8f09584501626d0aaa14a92e9a');
const offset = address => 16 + 2 * 16384 + address - 0x8000;
const word = address => rom[offset(address)] | rom[offset(address)+1] << 8;
const out = path.join(root,'output/audio/se'); fs.mkdirSync(out,{recursive:true});
const results = [];
for (let id = 1; id <= 13; id++) {
  const header = word(0xa268 + id*2), channels = rom[offset(header)];
  assert(channels >= 1 && channels <= 2);
  const streams = Array.from({length:channels}, (_,i)=>word(header+1+i*2));
  const pcm = [], reads = new Set(), streamReads = new Set(); let recording = false;
  const nes = new NES({sampleRate:48000,onAudioSample:(l,r)=>{if(recording)pcm.push(l,r);}});
  nes.loadROM(rom);
  for(let f=0;f<600;f++) nes.frame();
  const write = nes.cpu.write.bind(nes.cpu);
  nes.cpu.write = (address,value) => {
    if(address===0x600 && nes.cpu.REG_PC!==0x8346) return;
    if(address===0x601 && nes.cpu.REG_PC!==0x8355) return;
    if(address===0x602 && nes.cpu.REG_PC!==0x8596) return;
    return write(address,value);
  };
  nes.cpu.mem[0x600]=nes.cpu.mem[0x601]=nes.cpu.mem[0x602]=0;
  for(let f=0;f<60;f++) nes.frame();
  const load=nes.cpu.load.bind(nes.cpu);
  nes.cpu.load=address=>{
    if(nes.cpu.REG_PC>=0x8597&&nes.cpu.REG_PC<=0x85af) reads.add(address);
    if(nes.cpu.REG_PC>=0x835a&&nes.cpu.REG_PC<=0x8375) streamReads.add(address);
    return load(address);
  };
  recording=true; nes.cpu.mem[0x602]=id;
  let endFrame=null;
  for(let f=0;f<180;f++) {
    nes.frame();
    if(endFrame===null && f>0 && !nes.cpu.mem[0x610] && !nes.cpu.mem[0x611]) endFrame=f+1;
  }
  assert.equal(nes.cpu.mem[0x602],0,'One-shot request consumed');
  assert(reads.has(header),'Original driver reads SE header');
  streams.forEach(p=>assert(streamReads.has(p),'Original driver reads SE stream'));
  let peak=0,squares=0;for(const v of pcm){assert(Number.isFinite(v));peak=Math.max(peak,Math.abs(v));squares+=v*v;}
  const rms=Math.sqrt(squares/pcm.length);assert(rms>0.0001 && peak>0.01 && peak<=1,'Non-silent SE');
  const wav=Buffer.alloc(44+pcm.length*2);
  wav.write('RIFF');wav.writeUInt32LE(wav.length-8,4);wav.write('WAVEfmt ',8);
  wav.writeUInt32LE(16,16);wav.writeUInt16LE(1,20);wav.writeUInt16LE(2,22);
  wav.writeUInt32LE(48000,24);wav.writeUInt32LE(192000,28);wav.writeUInt16LE(4,32);wav.writeUInt16LE(16,34);
  wav.write('data',36);wav.writeUInt32LE(pcm.length*2,40);
  pcm.forEach((v,i)=>wav.writeInt16LE(Math.round(v*32767),44+i*2));
  const filename=`se-${String(id).padStart(2,'0')}.wav`;fs.writeFileSync(path.join(out,filename),wav);
  results.push({id,header,romOffset:offset(header),channels,streams,endFrame,seconds:pcm.length/96000,peak,rms,filename,
    sha256:createHash('sha256').update(wav).digest('hex')});
  console.log(`${filename}: header $${header.toString(16)}, ${channels} channels, RMS ${rms.toFixed(4)}, ended ${endFrame}`);
}
assert.equal(new Set(results.map(t=>t.sha256)).size,13,'Distinct SE output');
fs.writeFileSync(path.join(out,'catalog.json'),JSON.stringify({table:0xa268,request:0x602,
  note:'13 SE requests; three-second audition excerpts; scene names and hardware fidelity unverified.',sounds:results},null,2));
fs.writeFileSync(path.join(out,'index.html'),'<!doctype html><html lang="ja"><meta charset="utf-8"><title>Wiz1 SE試聴</title><style>body{font:16px system-ui;background:#131927;color:#eef;max-width:800px;margin:30px auto;padding:20px}section{margin:20px 0}audio{width:100%}</style><h1>Wiz1 SE試聴</h1><p>原作ドライバーとJSNESで生成した13種類のSEです。各約3秒。使用場面は未同定です。</p>'+results.map(t=>`<section><h2>SE ${String(t.id).padStart(2,'0')}</h2><audio controls preload="none" src="${t.filename}"></audio></section>`).join('')+'<script>document.addEventListener("play",e=>{document.querySelectorAll("audio").forEach(a=>{if(a!==e.target)a.pause()})},true)</script></html>');
console.log('PASS: all 13 requests consumed; all headers/streams read; 13 distinct non-silent WAVs.');
