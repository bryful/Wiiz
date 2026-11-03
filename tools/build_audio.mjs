/** Detect Wiz1 music headers and render via unmodified JSNES CPU/PPU/MMC1/APU. */
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
import NES from '../third_party/jsnes/src/nes.js';
const require = createRequire(import.meta.url);
const driver = require('../web/audio/driver.js');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const romPath = path.resolve(root, process.argv[2] || '.nes/wiz1.nes');
const rom = new Uint8Array(fs.readFileSync(romPath));
const hash = data => createHash('sha256').update(data).digest('hex');
assert.equal(hash(rom), driver.ROM_SHA256, 'Unsupported ROM SHA256');
const output = path.join(root, 'output/audio'); fs.mkdirSync(output, { recursive: true });
const catalog = driver.catalog(rom);
function wav(pcm) {
  const buffer = Buffer.alloc(44 + pcm.length * 2);
  buffer.write('RIFF'); buffer.writeUInt32LE(buffer.length - 8, 4); buffer.write('WAVEfmt ', 8);
  buffer.writeUInt32LE(16, 16); buffer.writeUInt16LE(1, 20); buffer.writeUInt16LE(2, 22);
  buffer.writeUInt32LE(48000, 24); buffer.writeUInt32LE(192000, 28); buffer.writeUInt16LE(4, 32);
  buffer.writeUInt16LE(16, 34); buffer.write('data', 36); buffer.writeUInt32LE(pcm.length * 2, 40);
  for (let i = 0; i < pcm.length; i++) buffer.writeInt16LE(Math.round(Math.max(-1, Math.min(1, pcm[i])) * 32767), 44 + i * 2);
  return buffer;
}
const results = [];
for (const track of catalog) {
  const pcm = [], reads = new Set(), pointers = new Set(); let writes = 0, pitches = 0;
  const nes = driver.create(NES, rom, track.id, (l,r) => pcm.push(l,r));
  const load = nes.cpu.load.bind(nes.cpu);
  nes.cpu.load = address => {
    // $8509/$850E select the header; $8515 reads its channel count.
    if (nes.cpu.REG_PC >= 0x8508 && nes.cpu.REG_PC <= 0x8522) reads.add(address);
    const pc = nes.cpu.REG_PC;
    if (pc >= 0x835a && pc <= 0x8375 && address >= 0x8000) pointers.add(address);
    return load(address);
  };
  const write = nes.papu.writeReg.bind(nes.papu);
  nes.papu.writeReg = (address,value) => {
    writes++;
    if ([0x4002,0x4006,0x400a].includes(address)) pitches++;
    return write(address,value);
  };
  const frames = track.id === 1 ? 1800 : 600;
  for (let frame = 0; frame < frames; frame++) nes.frame();
  assert([0,track.id].includes(nes.cpu.mem[0x604]), 'Driver must accept or finish requested song');
  assert(reads.has(track.header), 'Real driver must read the detected header');
  for (const stream of track.streams) assert(pointers.has(stream), `Driver must read stream ${stream.toString(16)}`);
  let maximum = 0, squares = 0, clipped = 0;
  for (const sample of pcm) {
    assert(Number.isFinite(sample), 'Nonfinite audio');
    maximum = Math.max(maximum, Math.abs(sample)); squares += sample * sample;
    if (Math.abs(sample) > 1) clipped++;
  }
  const rms = Math.sqrt(squares / pcm.length);
  assert(rms > 0.001 && maximum > 0.01 && pitches > 0 && clipped === 0, 'Audible nonclipping musical output required');
  const filename = `bgm-${String(track.id).padStart(2,'0')}.wav`;
  const bytes = wav(pcm); fs.writeFileSync(path.join(output, filename), bytes);
  const result = { ...track, filename, frames, seconds: pcm.length / 2 / 48000,
    samplesPerChannel: pcm.length / 2, peak: maximum, rms, clipped, apuWrites: writes,
    pitchWrites: pitches, headerRead: true, streamsRead: true, wavSha256: hash(bytes) };
  results.push(result); console.log(`${filename}: ${result.seconds.toFixed(2)}s, RMS ${rms.toFixed(4)}, pitch writes ${pitches}`);
}
assert.equal(new Set(results.map(r => r.wavSha256)).size, 13, 'All songs must have distinct output');
// Fresh initialization must yield reproducible audio, not depend on a previous song.
const repeat = [];
const nes = driver.create(NES, rom, 1, (l,r) => repeat.push(l,r));
for (let frame = 0; frame < 60; frame++) nes.frame();
const firstWav = fs.readFileSync(path.join(output, 'bgm-01.wav'));
assert.deepEqual(wav(repeat).subarray(44), firstWav.subarray(44, 44 + repeat.length * 2));
const manifest = { romSha256: hash(rom), emulator: 'JSNES 2.1.0 (Apache-2.0)',
  table: { bank: 2, cpuAddress: 0x8687, firstId: 1, lastId: 13 },
  note: 'Local audition excerpts; game-scene names and hardware audio fidelity unverified. No synthetic music or custom APU.', tracks: results };
fs.writeFileSync(path.join(output, 'catalog.json'), JSON.stringify(manifest, null, 2));
const escape = s => s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
let html = fs.readFileSync(path.join(root,'web/audio/index.html'),'utf8');
const replacements = {
  '__ROM_BASE64__': Buffer.from(rom).toString('base64'),
  '__JSNES__': fs.readFileSync(path.join(root,'third_party/jsnes/dist/jsnes.js'),'utf8'),
  '__DRIVER__': fs.readFileSync(path.join(root,'web/audio/driver.js'),'utf8'),
  '__LICENSE_TEXT__': escape(fs.readFileSync(path.join(root,'third_party/jsnes/LICENSE'),'utf8') + '\n\n' + fs.readFileSync(path.join(root,'third_party/jsnes/AUTHORS.md'),'utf8')),
};
for (const [key,value] of Object.entries(replacements)) html = html.replace(key, () => value);
fs.writeFileSync(path.join(output,'index.html'), html);
console.log('PASS: 13 headers/39 streams read by original driver; distinct non-silent WAVs; deterministic restart.');
