import fs from 'fs';
import path from 'path';
import { PNG } from 'pngjs';

const root = path.resolve('public/pics');
const targets = [
  path.join(root, 'logo.png'),
  path.join(root, 'logo_mini.png'),
  ...fs.readdirSync(path.join(root, 'logo_animation'))
    .filter((n) => n.endsWith('.png'))
    .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
    .map((n) => path.join(root, 'logo_animation', n)),
];

const start = { r: 0x00, g: 0xff, b: 0xff }; // cyan
const end = { r: 0x00, g: 0xdc, b: 0x82 };   // green-cyan hue

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

function blend(a, b, t) {
  return Math.round(a + (b - a) * t);
}

function relight(v, factor) {
  return clamp(Math.round(v * factor), 0, 255);
}

for (const file of targets) {
  const buf = fs.readFileSync(file);
  const png = PNG.sync.read(buf);
  const { width, height, data } = png;
  const denom = Math.max(1, (width - 1) + (height - 1));

  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const idx = (width * y + x) * 4;
      const a = data[idx + 3];
      if (a === 0) continue;

      const t = ((x) + (y)) / denom; // exact 45-degree diagonal
      const gr = blend(start.r, end.r, t);
      const gg = blend(start.g, end.g, t);
      const gb = blend(start.b, end.b, t);

      const luminance = (0.2126 * data[idx] + 0.7152 * data[idx + 1] + 0.0722 * data[idx + 2]) / 255;
      const factor = 0.55 + luminance * 0.95;

      data[idx] = relight(gr, factor);
      data[idx + 1] = relight(gg, factor);
      data[idx + 2] = relight(gb, factor);
    }
  }

  fs.writeFileSync(file, PNG.sync.write(png));
}

console.log(`Updated ${targets.length} logo PNGs with 45° cyan->green gradient.`);
