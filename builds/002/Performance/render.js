const ICONS = {
  cpu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="7" y="7" width="10" height="10" rx="1.2"/><path d="M9 3v3M12 3v3M15 3v3M9 18v3M12 18v3M15 18v3M3 9h3M3 12h3M3 15h3M18 9h3M18 12h3M18 15h3"/></svg>',
  gpu: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2.5" y="6" width="19" height="12" rx="1.6"/><circle cx="9" cy="12" r="2.6"/><path d="M15 9.5h3M15 12h3M15 14.5h3"/></svg>',
  ram: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="8" width="18" height="8" rx="1.2"/><path d="M6 8v-2M9 8v-2M12 8v-2M15 8v-2M18 8v-2M6 18v-2M9 18v-2"/></svg>',
  storage: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="6.5" rx="1.2"/><rect x="3" y="13.5" width="18" height="6.5" rx="1.2"/><circle cx="7" cy="7.25" r="0.9" fill="currentColor" stroke="none"/><circle cx="7" cy="16.75" r="0.9" fill="currentColor" stroke="none"/></svg>',
  board: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="1.2"/><circle cx="8" cy="8" r="1.3"/><path d="M12 6h6M12 10h6M6 13h5v5H6z"/><path d="M15 14h4v4h-4z"/></svg>',
  os: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M3 5.6L10.3 4.6V11.4H3V5.6ZM11.3 4.4L21 3V11.3H11.3V4.4ZM3 12.4H10.3V19.4L3 18.4V12.4ZM11.3 12.4H21V20.7L11.3 19.3V12.4Z"/></svg>',
  video: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>',
  image: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>',
  cube: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><polyline points="12 22.08 12 12"/></svg>',
  broadcast: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M23 7l-7 5 7 5V7z"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>',
  layers: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 2 7 2 17 12 22 22 17 22 7 12 2"/><polyline points="2 7 12 12 22 7"/><polyline points="12 12 12 22"/></svg>',
  briefcase: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg>'
};

function el(html){ const t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstElementChild; }
function esc(s){ return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function starPct(stars){ return Math.round((stars / 5) * 100) + '%'; }

function renderCard(data){
  const card = document.getElementById('ffCard');

  const toolBadges = data.toolsUsed.map(t => `<span class="ts-tool">${esc(t)}</span>`).join('');

  const benchTiles = data.benchmarks.map(b => `
    <div class="tile${b.accent ? ' accent-' + b.accent : ''}">
      <div class="tag">${esc(b.tag)}</div>
      <div class="val">${esc(b.value)} ${b.unit ? `<span>${esc(b.unit)}</span>` : ''}</div>
      <div class="ctx">${esc(b.ctx)}</div>
      <div class="tier ${esc(b.tier)}">${esc(b.tier)}</div>
    </div>`).join('');

  const gameCards = data.games.map(g => `
    <div class="game-card">
      <div class="art"><img src="${esc(g.cover)}" alt="${esc(g.name)}"></div>
      <div class="content">
        <div class="stars" style="--pct:${starPct(g.stars)}">★★★★★</div>
        <div class="title">${esc(g.name)}</div>
        <div class="fps-row"><span class="fps-num">${esc(g.fps)}</span><span class="fps-unit">fps</span></div>
      </div>
    </div>`).join('');

  const getTaskIcon = (name) => {
    const lower = name.toLowerCase();
    if (lower.includes('video')) return ICONS.video;
    if (lower.includes('photo') || lower.includes('lightroom') || lower.includes('photoshop')) return ICONS.image;
    if (lower.includes('3d') || lower.includes('blender') || lower.includes('rendering')) return ICONS.cube;
    if (lower.includes('stream') || lower.includes('obs')) return ICONS.broadcast;
    if (lower.includes('multitask') || lower.includes('tabs')) return ICONS.layers;
    return ICONS.briefcase;
  };

  const everydayRows = data.everyday.map(e => `
    <div class="ed-row">
      <div class="ed-icon">${getTaskIcon(e.name)}</div>
      <div>
        <div class="ed-name">${esc(e.name)}</div>
        <div class="ed-note">${esc(e.note)}</div>
      </div>
      <div class="tier ${esc(e.tier)}">${esc(e.tierLabel || e.tier)}</div>
    </div>`).join('');

  const specRows = data.specs.map(s => `
    <div class="spec-row"><div class="k">${ICONS[s.icon] || ''}${esc(s.label)}</div><div class="v">${esc(s.value)}</div></div>`).join('');

  function rankRows(rows){
    const max = Math.max(...rows.map(r => r.index));
    return rows.map(r => `
      <div class="rc-row${r.isThisBuild ? ' me' : ''}">
        <div class="rc-label">${esc(r.label)}</div>
        <div class="rc-track"><div class="rc-fill" style="width:${(r.index / max * 100).toFixed(1)}%"></div></div>
        <div class="rc-val">${esc(r.index)}</div>
      </div>`).join('');
  }

  const distBars = data.cpuDistribution.bars.map(b =>
    `<rect x="${b.x}" y="${b.y}" width="100" height="${b.h}" rx="3" fill="url(#barGrad)" opacity="0.75"/>`
  ).join('');

  card.innerHTML = `
    <div class="masthead">
      ${data.buildImage ? `<div class="build-picture"><img src="${esc(data.buildImage)}" alt="Build picture"></div>` : ''}
      <div class="brand-row">
        <img class="full-logo" src="assets/logo.png" alt="${esc(data.brand.name)} — ${esc(data.meta.brandTagline)}">
        <div class="badge-verified"><span class="dot"></span>Bench-verified ${esc(data.meta.verifiedDate)}</div>
      </div>
      <div class="page-title display grad-text">${esc(data.meta.buildName)}</div>
      <div class="model-row">
        <div>
          <div class="build-name">${esc(data.meta.pageTitle)}</div>
          <div class="model-name">${esc(data.meta.modelLine)}</div>
          <div class="model-sub">${esc(data.meta.modelSub)}</div>
        </div>
        <div class="hero-score">
          <div class="stars-top">⭐⭐⭐⭐⭐</div>
          <div class="num display grad-text">${esc(data.hero.novabenchOverall)}</div>
          <div class="lbl">Novabench Overall Score</div>
          <div class="pct">Outperforms ${esc(data.hero.percentile)}% of systems tested</div>
        </div>
      </div>
    </div>

    <div class="toolstrip">
      <span class="ts-label">Benchmarked with</span>
      ${toolBadges}
    </div>

    <div class="percentile">
      <div class="num-block">
        <div class="big display">${esc(data.hero.percentile)}</div>
        <div class="suffix">percentile</div>
      </div>
      <div class="body">
        <div class="headline">${esc(data.hero.percentileHeadline)}</div>
        <div class="sub">${esc(data.hero.percentileSub)}</div>
        <div class="gauge"><div class="gauge-fill" style="width:${esc(data.hero.percentile)}%"></div></div>
        <div class="gauge-marks"><span>0</span><span>25</span><span>50</span><span>75</span><span>100</span></div>
      </div>
    </div>

    <div class="rankgrid">
      <div class="rankcard">
        <div class="rc-title">${esc(data.cpuRankChart.title)}</div>
        ${rankRows(data.cpuRankChart.rows)}
      </div>
      <div class="rankcard">
        <div class="rc-title">${esc(data.gpuRankChart.title)}</div>
        ${rankRows(data.gpuRankChart.rows)}
      </div>
    </div>
    <div class="rankgrid-foot"><i>${esc(data.rankChartFootnote)}</i></div>

    <div class="distcard">
      <div class="dc-title">${esc(data.cpuDistribution.title)}</div>
      <div class="dc-sub">${esc(data.cpuDistribution.sub)}</div>
      <svg class="distchart" viewBox="0 0 680 210" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="barGrad" x1="0" y1="1" x2="0" y2="0">
            <stop offset="0%" stop-color="${getComputedStyle(document.documentElement).getPropertyValue('--blue')}"/>
            <stop offset="100%" stop-color="${getComputedStyle(document.documentElement).getPropertyValue('--orange')}"/>
          </linearGradient>
        </defs>
        <line x1="50" y1="160" x2="650" y2="160" stroke="var(--line-strong)" stroke-width="1"/>
        <line x1="50" y1="20" x2="50" y2="160" stroke="var(--line-strong)" stroke-width="1"/>
        <text x="42" y="24" text-anchor="end" font-size="10" fill="var(--ink-faint)" font-family="Segoe UI, sans-serif">60%</text>
        <text x="42" y="164" text-anchor="end" font-size="10" fill="var(--ink-faint)" font-family="Segoe UI, sans-serif">0</text>
        ${distBars}
        <text x="50"  y="178" text-anchor="middle" font-size="10" fill="var(--ink-faint)" font-family="Segoe UI, sans-serif">0</text>
        <text x="170" y="178" text-anchor="middle" font-size="10" fill="var(--ink-faint)" font-family="Segoe UI, sans-serif">500</text>
        <text x="290" y="178" text-anchor="middle" font-size="10" fill="var(--ink-faint)" font-family="Segoe UI, sans-serif">1000</text>
        <text x="410" y="178" text-anchor="middle" font-size="10" fill="var(--ink-faint)" font-family="Segoe UI, sans-serif">1500</text>
        <text x="530" y="178" text-anchor="middle" font-size="10" fill="var(--ink-faint)" font-family="Segoe UI, sans-serif">2000</text>
        <text x="650" y="178" text-anchor="middle" font-size="10" fill="var(--ink-faint)" font-family="Segoe UI, sans-serif">${esc(data.cpuDistribution.axisMax)}</text>
        <text x="350" y="200" text-anchor="middle" font-size="10.5" fill="var(--ink-dim)" font-family="Segoe UI, sans-serif">CPU Score</text>
        <line x1="${data.cpuDistribution.thisScoreX}" y1="20" x2="${data.cpuDistribution.thisScoreX}" y2="160" stroke="var(--gold)" stroke-width="1.5" stroke-dasharray="4,3"/>
        <circle cx="${data.cpuDistribution.thisScoreX}" cy="${data.cpuDistribution.markerCircleY}" r="3.5" fill="var(--gold)"/>
        <rect x="${data.cpuDistribution.thisScoreX - 55}" y="6" width="110" height="20" rx="6" fill="var(--bg-panel)" stroke="var(--gold)" stroke-width="1"/>
        <text x="${data.cpuDistribution.thisScoreX}" y="20" text-anchor="middle" font-size="10.5" font-weight="700" fill="var(--gold)" font-family="ui-monospace, Consolas, monospace">${esc(data.cpuDistribution.thisScoreLabel)}</text>
      </svg>
    </div>

    <div class="section"><div class="section-label display">Benchmark results</div></div>
    <div class="grid">${benchTiles}</div>
    <div class="tiernote"><i>Tiers reflect how each result compares to typical results for this hardware class — see "How it ranks" above for the full picture.</i></div>

    <div class="section"><div class="section-label display">Gaming performance · estimated</div></div>
    <div class="games">${gameCards}</div>
    <div class="games-foot">${esc(data.gamesFootnote)}</div>

    <div class="section"><div class="section-label display">Beyond gaming</div></div>
    <div class="everyday">${everydayRows}</div>

    <div class="section"><div class="section-label display">System specification</div></div>
    <div class="specs">${specRows}</div>

    <div class="health">
      <div class="pill"><span class="dot"></span>Drive health: ${esc(data.health.status)}</div>
      <div class="mid">
        <span>Power-on: <b>${esc(data.health.powerOnHours)}</b></span>
        <span>Written: <b>${esc(data.health.dataWritten)}</b></span>
        <span>Temp: <b>${esc(data.health.tempLoad)}</b> load</span>
      </div>
      <div class="drive">${esc(data.health.driveModel)}</div>
    </div>

    <div class="footer">
      <div class="note">${esc(data.footerNote)}</div>
      <div class="stamp">${esc(data.brand.name)}<br><b class="grad-text">${esc(data.brand.url)}</b></div>
    </div>
  `;
}

const defaultData = {
  meta: { buildName: '', pageTitle: 'Performance Card', brandTagline: '', verifiedDate: '', modelLine: '', modelSub: '' },
  hero: { novabenchOverall: 0, percentile: 0, percentileHeadline: '', percentileSub: '' },
  toolsUsed: [],
  benchmarks: [],
  cpuDistribution: { title: '', sub: '', thisScoreLabel: '', thisScoreX: 0, axisMax: '0', bars: [], markerCircleY: 0 },
  cpuRankChart: { title: '', rows: [] },
  gpuRankChart: { title: '', rows: [] },
  rankChartFootnote: '',
  games: [],
  gamesFootnote: '',
  everyday: [],
  specs: [],
  health: { status: '', powerOnHours: '', dataWritten: '', tempLoad: '', driveModel: '' },
  footerNote: '',
  brand: { name: '', url: '' }
};

fetch('performance-data.json')
  .then(r => {
    console.log('Fetch response status:', r.status);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  })
  .then(data => {
    console.log('Loaded performance data:', data);
    renderCard(data);
  })
  .catch(err => {
    console.warn('Could not load performance-data.json:', err.message, '— using empty template');
    renderCard(defaultData);
  });

(function(){
  const loader = document.getElementById('ffLoader');
  if(!loader) return;
  const reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if(reduce){ loader.classList.add('hide'); return; }
  setTimeout(() => loader.classList.add('hide'), 2800);
})();
