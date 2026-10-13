"""Extract existing embedded WAVs and the original icon, without new dependencies."""
import io
import json
import struct
import wave
from pathlib import Path
import cairo

ROOT = Path(__file__).resolve().parents[1]
blob = (ROOT/'正式版'/'src'/'sounds.bin').read_bytes()
dest = ROOT/'linux'/'sounds'
dest.mkdir(exist_ok=True)
for i, name in enumerate(('mine_1', 'mine_2', 'mine_3', 'mine_4', 'win', 'tick')):
    offset, length = struct.unpack_from('<II', blob, 12+i*20)
    data = blob[12+6*20+offset:12+6*20+offset+length]
    with wave.open(io.BytesIO(data)) as wav:
        assert wav.getnframes() > 0
    (dest/f'{name}.wav').write_bytes(data)
atlas = cairo.ImageSurface.create_from_png(str(ROOT/'素材'/'图集.png'))
slot = next(s for s in json.loads((ROOT/'素材'/'图集.json').read_text())['slots'] if s['name'] == 'icon')
icon = cairo.ImageSurface(cairo.FORMAT_ARGB32, slot['w'], slot['h'])
ctx = cairo.Context(icon)
ctx.set_source_surface(atlas, -slot['x'], -slot['y'])
ctx.paint()
icon.write_to_png(str(ROOT/'linux'/'icon.png'))
print('原版图标及 6 段 WAV 已提取。')
