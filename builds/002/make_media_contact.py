from PIL import Image, ImageDraw
from pathlib import Path
import math

files = [p for p in Path('builds/002/Media').glob('*.png') if p.stat().st_size > 100_000]
thumbs = []
for path in files:
    im = Image.open(path).convert('RGB')
    im.thumbnail((180, 180))
    thumbs.append((path.name, im.copy()))
w = 720
h = math.ceil(len(thumbs) / 4) * 220
out = Image.new('RGB', (w, h), '#222')
d = ImageDraw.Draw(out)
for i, (name, im) in enumerate(thumbs):
    x, y = (i % 4) * 180, (i // 4) * 220
    out.paste(im, (x, y))
    d.text((x + 3, y + 183), name[:20], fill='white')
out.save('builds/002/media-contact.jpg', quality=85)
