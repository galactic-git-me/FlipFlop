const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('../../../flipflop-admin/node_modules/playwright-core');
const { spawnSync } = require('node:child_process');

const workspace = path.resolve(__dirname, '../../..');
const output = __dirname;
const frames = path.join(output, 'model-frames');
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.glb': 'model/gltf-binary', '.png': 'image/png', '.woff2': 'font/woff2' };

function startServer() {
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const filename = path.resolve(workspace, `.${pathname}`);
    if (!filename.startsWith(workspace + path.sep) && filename !== workspace) { res.writeHead(403).end(); return; }
    fs.readFile(filename, (err, data) => {
      if (err) { res.writeHead(404).end(String(err)); return; }
      res.writeHead(200, { 'Content-Type': mime[path.extname(filename)] || 'application/octet-stream', 'Access-Control-Allow-Origin': '*' });
      res.end(data);
    });
  });
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(server)));
}

(async () => {
  fs.mkdirSync(frames, { recursive: true });
  const server = await startServer();
  let browser;
  try {
    const port = server.address().port;
    browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', args: ['--no-sandbox', '--enable-webgl', '--ignore-gpu-blocklist'] });
    const page = await browser.newPage({ viewport: { width: 1116, height: 1600 }, deviceScaleFactor: 1 });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') errors.push(`${m.text()} (${m.location().url})`); });
    page.on('requestfailed', r => errors.push(`Request failed: ${r.url()} ${r.failure()?.errorText}`));
    page.on('response', r => { if (r.status() >= 400) errors.push(`HTTP ${r.status()}: ${r.url()}`); });
    await page.goto(`http://127.0.0.1:${port}/builds/002/social-ad/showcase.html`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.evaluate(() => document.fonts.ready);
    await page.waitForFunction(() => typeof window.adSetFrame === 'function', null, { timeout: 90000 });
    const responsiveChecks = [];
    for (const width of [360, 390, 768, 1080]) {
      await page.setViewportSize({ width, height: 1350 });
      await page.waitForTimeout(100);
      const metrics = await page.evaluate(() => {
        const ad = document.querySelector('.ad').getBoundingClientRect();
        const stage = document.querySelector('.stage').getBoundingClientRect();
        const model = document.querySelector('.model-wrap').getBoundingClientRect();
        const photos = document.querySelector('.photo-rail').getBoundingClientRect();
        const games = document.querySelectorAll('.game-card').length;
        const gameGrid = document.querySelector('.games').getBoundingClientRect();
        return { viewport: innerWidth, ad: Math.round(ad.width), stage: `${Math.round(stage.width)}x${Math.round(stage.height)}`, model: `${Math.round(model.width)}x${Math.round(model.height)}`, photos: `${Math.round(photos.width)}x${Math.round(photos.height)}`, games, gameGridWidth: Math.round(gameGrid.width), horizontalOverflow: document.documentElement.scrollWidth > innerWidth };
      });
      responsiveChecks.push(metrics);
      if (metrics.horizontalOverflow || metrics.model.endsWith('x0')) throw new Error(`Responsive layout failed at ${width}px: ${JSON.stringify(metrics)}`);
    }
    await page.setViewportSize({ width: 1116, height: 1600 });
    for (let i = 0; i < 72; i++) {
      await page.evaluate(({ angle, phase }) => window.adSetFrame(angle, phase), { angle: Math.PI * 2 * i / 72, phase: i / 72 * 100 });
      await page.locator('.ad').screenshot({ path: path.join(frames, `frame-${String(i).padStart(3, '0')}.png`), animations: 'disabled' });
    }
    await page.locator('.ad').screenshot({ path: path.join(output, 'showcase-preview.png') });
    await page.locator('.ad').screenshot({ path: path.join(output, 'prometheus-black-friday-portrait.png'), animations: 'disabled' });
    const ffmpeg = 'C:/Users/mclar/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1.2-full_build/bin/ffmpeg.exe';
    const encode = spawnSync(ffmpeg, ['-y', '-hide_banner', '-loglevel', 'error', '-framerate', '8', '-i', path.join(frames, 'frame-%03d.png'), '-vf', 'scale=720:-2:flags=lanczos,fps=24,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-movflags', '+faststart', path.join(output, 'prometheus-black-friday-animated.mp4')], { encoding: 'utf8' });
    if (encode.status !== 0) throw new Error(`FFmpeg encoding failed: ${encode.stderr}`);
    fs.writeFileSync(path.join(output, 'browser-check.txt'), `Supplied compressed GLB loaded in Edge WebGL; 72 full-orbit frames rendered and encoded to MP4. Responsive viewport checks: ${JSON.stringify(responsiveChecks)}. Browser resource errors: ${JSON.stringify(errors)}\n`);
    console.log(`Rendered 72 frames. Browser errors: ${errors.length}`);
    if (errors.length) console.log(errors.join('\n'));
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(e => { console.error(e); process.exitCode = 1; });
