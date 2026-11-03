"""Extract iNES CHR tiles without third-party dependencies."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import zlib


def png(path, width, height, pixels):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    rows = b''.join(b'\0' + bytes(pixels[y * width:(y + 1) * width]) for y in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 0, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))


def decode_tile(data):
    if len(data) != 16:
        raise ValueError('A tile must contain 16 bytes')
    return [((data[y] >> (7 - x)) & 1) | (((data[y + 8] >> (7 - x)) & 1) << 1)
            for y in range(8) for x in range(8)]


def extract(rom, output):
    data = rom.read_bytes()
    if len(data) < 16 or data[:4] != b'NES\x1a':
        raise ValueError('Not an iNES ROM')
    if data[7] & 12 == 8:
        raise ValueError('NES 2.0 is not supported yet')
    prg_size, chr_size = data[4] * 16384, data[5] * 8192
    start = 16 + (512 if data[6] & 4 else 0) + prg_size
    if len(data) < start + chr_size:
        raise ValueError('Truncated ROM')
    if not chr_size:
        raise ValueError('CHR RAM cartridge: graphics must be located in PRG data')
    output.mkdir(parents=True, exist_ok=True)
    banks = []
    shades = [0, 85, 170, 255]
    for bank_id in range(chr_size // 4096):
        offset = start + bank_id * 4096
        raw = data[offset:offset + 4096]
        pixels = bytearray(128 * 128)
        for tile_id in range(256):
            tile = decode_tile(raw[tile_id * 16:tile_id * 16 + 16])
            tx, ty = (tile_id % 16) * 8, (tile_id // 16) * 8
            for y in range(8):
                for x in range(8):
                    pixels[(ty + y) * 128 + tx + x] = shades[tile[y * 8 + x]]
        name = f'bank_{bank_id:02d}'
        png(output / (name + '.png'), 128, 128, pixels)
        (output / (name + '.chr')).write_bytes(raw)
        banks.append(dict(bank=bank_id, file_offset=offset, file_offset_hex=f'0x{offset:06X}', first_tile=bank_id * 256, image=name + '.png'))
    manifest = dict(source=rom.name, sha256=hashlib.sha256(data).hexdigest(), file_size=len(data),
                    mapper=(data[6] >> 4) | (data[7] & 240), prg_size=prg_size, chr_size=chr_size,
                    chr_offset=start, trailing_bytes=len(data) - start - chr_size,
                    tile_format='8x8, 2bpp planar, 16 bytes/tile',
                    palette='Diagnostic grayscale; original palettes and tile arrangements not yet decoded', banks=banks)
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    cards = ''.join(f'<section><h2>Bank {b["bank"]:02d}</h2><p>ROM {b["file_offset_hex"]}</p><img data-bank="{b["bank"]}" data-offset="{b["file_offset"]}" src="{b["image"]}" width="384" height="384"><p class="position">画像にマウスを合わせるとタイル位置を表示</p></section>' for b in banks)
    page = '''<!doctype html><html lang="ja"><meta charset="utf-8"><title>Wizardry CHR atlas</title>
<style>body{background:#14181f;color:#e6edf3;font:15px sans-serif;margin:28px}main{display:flex;flex-wrap:wrap;gap:24px}section{background:#202731;padding:16px}img{image-rendering:pixelated;cursor:crosshair}h2{margin:0}p{font-family:monospace}.position{font-size:12px}</style>
<h1>Wizardry CHR タイル一覧</h1><p>8×8 / 2bpp / 4 KiB単位。表示色は確認用の4階調です。配置・実パレットは未解析です。</p><main>''' + cards + '''</main><script>
document.querySelectorAll('img').forEach(img=>img.onmousemove=e=>{
const r=img.getBoundingClientRect(), x=Math.min(15,Math.floor((e.clientX-r.left)/r.width*16)), y=Math.min(15,Math.floor((e.clientY-r.top)/r.height*16));
const tile=y*16+x, global=Number(img.dataset.bank)*256+tile, offset=Number(img.dataset.offset)+tile*16;
img.nextElementSibling.textContent=`Tile $${tile.toString(16).padStart(2,'0')} / Global ${global} / ROM 0x${offset.toString(16).padStart(6,'0')}`;
});</script></html>'''
    (output / 'index.html').write_text(page, encoding='utf-8')
    print(json.dumps({k: v for k, v in manifest.items() if k != 'banks'}, indent=2))
    print(f'Extracted {len(banks)} banks / {chr_size // 16} tiles to {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('rom', type=Path)
    parser.add_argument('--output', type=Path, default=Path('output/chr'))
    args = parser.parse_args()
    extract(args.rom, args.output)
