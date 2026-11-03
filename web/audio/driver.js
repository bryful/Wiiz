/* ROM-specific glue. CPU, PPU, MMC1 and sound synthesis are unmodified JSNES. */
(function (root) {
  'use strict';
  const ROM_SHA256 = '38da945c819fab8255a1b3b8ad7c7ea162b51e8f09584501626d0aaa14a92e9a';
  function catalog(bytes) {
    if (bytes.length < 16 || String.fromCharCode(...bytes.slice(0, 4)) !== 'NES\x1a' ||
        (bytes[6] >> 4 | bytes[7] & 240) !== 1 || bytes[6] & 4 || bytes[4] !== 8) {
      throw Error('対応するWiz1 ROMではありません');
    }
    const offset = address => 16 + 2 * 16384 + address - 0x8000;
    const word = address => bytes[offset(address)] | bytes[offset(address) + 1] << 8;
    const tracks = [];
    // $8509/$850E read this table; first header begins immediately after entry 13.
    if (word(0x8689) !== 0x86a3) throw Error('BGMテーブルが一致しません');
    for (let id = 1; id <= 13; id++) {
      const header = word(0x8687 + id * 2);
      const channels = bytes[offset(header)];
      if (channels !== 3 || header !== 0x86a3 + (id - 1) * 7) throw Error('BGMヘッダーが一致しません');
      const streams = Array.from({ length: channels }, (_, i) => word(header + 1 + i * 2));
      if (streams.some(p => p < 0x8000 || p >= 0xc000)) throw Error('BGM参照が範囲外です');
      tracks.push({ id, name: id === 1 ? 'BGM 01（起動時に使用）' : `BGM ${String(id).padStart(2, '0')}`,
        bank: 2, header, romOffset: offset(header), streams });
    }
    return tracks;
  }
  function create(NES, rom, id, onSample, sampleRate = 48000) {
    if (!catalog(rom).some(t => t.id === id)) throw Error('不正なBGM番号です');
    let capture = false;
    const nes = new NES({ sampleRate, onAudioSample: (l, r) => { if (capture) onSample(l, r); } });
    nes.loadROM(rom);
    // Real game initialization, including mapper, sound driver, SRAM and NMI setup.
    for (let frame = 0; frame < 600; frame++) nes.frame();
    nes.cpu.mem[0x600] = 0;
    for (let frame = 0; frame < 2; frame++) nes.frame();
    nes.cpu.mem[0x600] = id;
    nes.cpu.mem[0x604] = 0;
    // The title screen re-requests song 1 when its wait completes. An audition
    // must ignore scene requests, while allowing the sound driver's own stop.
    const write = nes.cpu.write.bind(nes.cpu);
    nes.cpu.write = (address, value) => {
      if (address === 0x600 && nes.cpu.REG_PC !== 0x8346) return;
      if (address === 0x601 || address === 0x602) return;
      return write(address, value);
    };
    capture = true;
    return nes;
  }
  const api = { ROM_SHA256, catalog, create };
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.WiizAudio = api;
})(typeof globalThis === 'object' ? globalThis : this);
