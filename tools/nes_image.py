"""Diagnostic NES colors and dependency-free PNG output."""
import struct
import zlib

# Analog NES RGB output varies between emulators/displays.
COLORS = '''666666 002a88 1412a7 3b00a4 5c007e 6e0040 6c0600 561d00
333500 0b4800 005200 004f08 00404d 000000 000000 000000
adadad 155fd9 4240ff 7527fe a01acc b71e7b b53120 994e00
6b6d00 388700 0c9300 008f32 007c8d 000000 000000 000000
fffeff 64b0ff 9290ff c676ff f36aff fe6ecc fe8170 ea9e22
bcbe00 88d800 5ce430 45e082 48cdde 4f4f4f 000000 000000
fffeff c0dfff d3d2ff e8c8ff fbc2ff fec4ea feccc5 f7d8a5
e4e594 cfef96 bdf4ab b3f3cc b5ebf2 b8b8b8 000000 000000'''.split()


def write_png(path, width, height, pixels, channels):
    if channels not in (3, 4) or width < 1 or height < 1 or len(pixels) != width * height * channels:
        raise ValueError('Invalid PNG dimensions/channels/pixel count')
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    raw = b''.join(b'\0' + pixels[y * width * channels:(y + 1) * width * channels] for y in range(height))
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2 if channels == 3 else 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def rgb_png(path, width, height, pixels):
    write_png(path, width, height, pixels, 3)


def rgba_png(path, width, height, pixels):
    write_png(path, width, height, pixels, 4)
