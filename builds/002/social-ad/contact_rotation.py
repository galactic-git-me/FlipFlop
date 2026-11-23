from PIL import Image, ImageDraw
from pathlib import Path
paths = sorted(Path(__file__).parent.joinpath('model-frames').glob('frame-*.png'))
out = Image.new('RGB', (1080, ((len(paths[::6]) + 5) // 6) * 250), '#202020')
d = ImageDraw.Draw(out)
for i, path in enumerate(paths[::6]):
    im = Image.open(path)
    im.thumbnail((170, 220))
    x, y = (i % 6) * 180, (i // 6) * 250
    out.paste(im, (x, y))
    d.text((x + 3, y + 222), path.name, fill='white')
out.save(Path(__file__).parent / 'rotation-contact.jpg', quality=85)
