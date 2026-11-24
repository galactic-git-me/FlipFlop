const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('../../../../flipflop-admin/node_modules/playwright-core');
const { spawnSync } = require('node:child_process');

const workspace = path.resolve(__dirname, '../../../..');
const output = __dirname;
const frames = path.join(output, 'frames');
const brandCover = path.join(output, 'assets/flipflop-facebook-cover.png');
const ffmpeg = 'C:/Users/mclar/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1.2-full_build/bin/ffmpeg.exe';
const mime = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.glb': 'model/gltf-binary', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };

function startServer() {
  const server = http.createServer((req, res) => {
    const pathname = decodeURIComponent(new URL(req.url, 'http://localhost').pathname);
    const filename = path.resolve(workspace, `.${pathname}`);
    if (!filename.startsWith(workspace + path.sep)) { res.writeHead(403).end(); return; }
    fs.readFile(filename, (err, data) => {
      if (err) { res.writeHead(404).end(String(err)); return; }
      res.writeHead(200, { 'Content-Type': mime[path.extname(filename)] || 'application/octet-stream' });
      res.end(data);
    });
  });
  return new Promise(resolve => server.listen(0, '127.0.0.1', () => resolve(server)));
}

function makeXCreative() {
  const svgPath = path.join(output, 'assets/x-feed-1200x628.svg');
  const pngPath = path.join(output, 'assets/x-feed-1200x628.png');
  const cover = fs.readFileSync(brandCover).toString('base64');
  const svg = `
  <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="1200" height="628" viewBox="0 0 1200 628">
    <defs>
      <linearGradient id="bg" x2="1" y2="1"><stop stop-color="#091522"/><stop offset="1" stop-color="#070b12"/></linearGradient>
      <linearGradient id="accent"><stop stop-color="#38c7ff"/><stop offset="1" stop-color="#ff9a38"/></linearGradient>
      <linearGradient id="lime"><stop stop-color="#cbff3d"/><stop offset="1" stop-color="#5eff87"/></linearGradient>
      <clipPath id="coverClip"><rect x="24" y="24" width="560" height="150" rx="13"/></clipPath>
      <clipPath id="productClip"><rect x="24" y="190" width="560" height="414" rx="15"/></clipPath>
    </defs>
    <rect width="1200" height="628" rx="24" fill="url(#bg)"/>
    <image xlink:href="data:image/png;base64,${cover}" x="24" y="24" width="560" height="150" preserveAspectRatio="xMidYMid slice" clip-path="url(#coverClip)"/>
    <image xlink:href="../../showcase-preview.png" x="24" y="190" width="560" height="414" preserveAspectRatio="xMidYMid slice" clip-path="url(#productClip)"/>
    <rect x="598" y="28" width="3" height="572" rx="2" fill="url(#accent)"/>
    <text x="646" y="65" fill="#8bc6ed" font-family="Arial,sans-serif" font-size="17" font-weight="700" letter-spacing="3">FLIPFLOP · FIRST BUILD</text>
    <text x="640" y="137" fill="url(#lime)" font-family="Arial,sans-serif" font-size="55" font-weight="900" letter-spacing="-2">PROMETHEUS</text>
    <text x="646" y="182" fill="#f2f6fb" font-family="Arial,sans-serif" font-size="21" font-weight="700">RYZEN 7 7800X3D</text>
    <text x="646" y="212" fill="#b7c7da" font-family="Arial,sans-serif" font-size="18">GEFORCE RTX 3070 · 32GB DDR5</text>
    <text x="648" y="274" fill="#aebcd0" font-family="Arial,sans-serif" font-size="18" font-weight="700">RRP</text><text x="698" y="274" fill="#aebcd0" font-family="Arial,sans-serif" font-size="20" font-weight="700" text-decoration="line-through">£1,700</text>
    <text x="642" y="345" fill="url(#accent)" font-family="Arial,sans-serif" font-size="78" font-weight="900" letter-spacing="-4">£1,349</text>
    <text x="648" y="378" fill="#e7edf4" font-family="Arial,sans-serif" font-size="16" font-weight="700">DIRECT · £50 NEW-CUSTOMER DISCOUNT INCLUDED</text>
    <rect x="646" y="403" width="500" height="2" fill="#334b64"/>
    <text x="648" y="440" fill="#aebcd0" font-family="Arial,sans-serif" font-size="16" font-weight="700">EBAY RRP</text><text x="732" y="440" fill="#aebcd0" font-family="Arial,sans-serif" font-size="18" font-weight="700" text-decoration="line-through">£1,700</text>
    <text x="648" y="473" fill="#f0a55a" font-family="Arial,sans-serif" font-size="24" font-weight="800">£1,399 ON EBAY</text>
    <text x="648" y="515" fill="#ffffff" font-family="Arial,sans-serif" font-size="21" font-weight="900" letter-spacing="1">BLACK FRIDAY · ONE REMAINING</text>
    <text x="648" y="528" fill="#94a8bd" font-family="Arial,sans-serif" font-size="16">See post copy for shopping links</text>
    <text x="648" y="577" fill="url(#accent)" font-family="Arial,sans-serif" font-size="18" font-weight="700" letter-spacing="2">BEAUTIFUL MACHINES. BUILT TO BE ADMIRED.</text>
  </svg>`;
  fs.writeFileSync(svgPath, svg);
  return pngPath;
}

const layout = (height, vertical) => `
  html,body{width:1080px!important;height:${height}px!important;min-height:${height}px!important;overflow:hidden!important}
  body{display:block!important;padding:0!important;background:#070b12!important}
  .ad{width:1080px!important;height:${height}px!important;min-height:0!important;overflow:hidden!important;padding:${vertical ? '24px 36px' : '22px 36px'}!important;border:0!important;border-radius:0!important;box-shadow:none!important;display:flex!important;flex-direction:column!important;gap:0!important}
  .head{height:${vertical ? '166px' : '142px'}!important;flex:0 0 ${vertical ? '166px' : '142px'}!important;margin:0 0 12px!important;border:1px solid #335676!important;border-radius:14px!important;overflow:hidden!important;background:#070b12 url('/builds/002/social-ad/platform-previews/assets/flipflop-facebook-cover.png') center/cover no-repeat!important}.head>*{visibility:hidden!important}.logo{width:62px!important;height:62px!important}
  .black{padding:10px 14px!important;font-size:11px!important}.brand{font-size:15px!important}.tag{font-size:10px!important}
  .eyebrow{font-size:15px!important;margin:3px 0 0!important}.title{font-size:68px!important;margin:0!important;line-height:1.06!important}.sub{font-size:15px!important;margin:4px 0 10px!important}
  .stage{height:${vertical ? '960px' : '650px'}!important;flex:0 0 ${vertical ? '960px' : '650px'}!important;padding:10px!important;margin:0!important}
  ${vertical ? '.photo-rail{display:none!important}.stage{grid-template-columns:1fr!important}.model-wrap{width:100%!important}' : ''}
  .specs{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:9px!important;margin:10px 0!important;flex:0 0 auto!important}.spec{padding:10px!important;gap:8px!important}.spec-icon{width:36px!important;height:36px!important;flex-basis:36px!important}.spec small{font-size:9px!important}.spec strong{font-size:12px!important}.spec span{font-size:10px!important}
  .performance{${vertical ? 'display:block!important' : 'display:none!important'};margin:6px 0 0!important;padding:10px!important;flex:0 0 auto!important}.performance .games,.performance .games-note{display:none!important}.performance-head{font-size:13px!important;margin-bottom:6px!important}.bench-summary{grid-template-columns:86px 1fr!important;padding:8px 12px!important;margin:0!important}.percentile-num{font-size:30px!important}.bench-copy strong{font-size:11px!important}.bench-copy span{font-size:9px!important}.bench-meter{margin-top:5px!important}
  .offer{min-height:${vertical ? '174px' : '164px'}!important;flex:0 0 ${vertical ? '174px' : '164px'}!important;margin:8px 0 0!important;padding:15px 19px!important;grid-template-columns:190px 1fr 245px!important;gap:14px!important}.badge{font-size:11px!important}.old{font-size:24px!important}.new{font-size:58px!important}.stock b{font-size:13px!important;padding:10px!important}.extra{font-size:13px!important}
  .actions,.delivery{display:none!important}.ad:after{content:'THEFLIPFLOP.SHOP';display:block;margin:12px auto 0;font:12px Nasa,sans-serif;letter-spacing:.18em;color:#57caff;text-align:center}
`;

async function applyLayout(page, height, vertical) {
  await page.setViewportSize({ width: 1080, height });
  await page.addStyleTag({ content: layout(height, vertical) });
  await page.waitForTimeout(250);
  await page.evaluate(() => window.adSetFrame(0, 0));
}

(async () => {
  fs.mkdirSync(frames, { recursive: true });
  if (!fs.existsSync(brandCover)) throw new Error(`Missing FlipFlop brand cover: ${brandCover}`);
  makeXCreative();
  const server = await startServer();
  let browser;
  try {
    browser = await chromium.launch({ headless: true, executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', args: ['--no-sandbox', '--enable-webgl', '--ignore-gpu-blocklist'] });
    const page = await browser.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 });
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    const origin = `http://127.0.0.1:${server.address().port}`;
    await page.goto(`${origin}/builds/002/social-ad/showcase.html`, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForFunction(() => typeof window.adSetFrame === 'function', null, { timeout: 90000 });

    const xPage = await browser.newPage({ viewport: { width: 1200, height: 628 }, deviceScaleFactor: 1 });
    await xPage.goto(`${origin}/builds/002/social-ad/platform-previews/assets/x-feed-1200x628.svg`, { waitUntil: 'networkidle', timeout: 30000 });
    await xPage.screenshot({ path: path.join(output, 'assets/x-feed-1200x628.png') });
    await xPage.close();

    await applyLayout(page, 1350, false);
    await page.locator('.ad').screenshot({ path: path.join(output, 'assets/meta-feed-1080x1350.png'), animations: 'disabled' });

    await applyLayout(page, 1920, true);
    await page.locator('.ad').screenshot({ path: path.join(output, 'assets/vertical-1080x1920.png'), animations: 'disabled' });
    for (let i = 0; i < 72; i++) {
      await page.evaluate(({ angle, phase }) => window.adSetFrame(angle, phase), { angle: Math.PI * 2 * i / 72, phase: i / 72 * 100 });
      await page.locator('.ad').screenshot({ path: path.join(frames, `frame-${String(i).padStart(3, '0')}.png`), animations: 'disabled' });
    }
    const encoded = spawnSync(ffmpeg, ['-y', '-hide_banner', '-loglevel', 'error', '-framerate', '8', '-i', path.join(frames, 'frame-%03d.png'), '-vf', 'fps=24,format=yuv420p', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19', '-movflags', '+faststart', path.join(output, 'assets/vertical-1080x1920.mp4')], { encoding: 'utf8' });
    if (encoded.status !== 0) throw new Error(`Vertical video encode failed: ${encoded.stderr}`);
    if (errors.length) throw new Error(errors.join('\n'));
    console.log('Rendered 4:5 Meta feed image and 9:16 vertical poster/video. Browser errors: 0. Video is silent.');
  } finally {
    if (browser) await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
