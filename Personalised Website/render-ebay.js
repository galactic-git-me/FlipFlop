#!/usr/bin/env node
/**
 * Renders ebay-listing-template.html + a data JSON file into a final,
 * fully static HTML file with no {{tokens}} and no <script> tags — safe to
 * paste directly into eBay's listing description box.
 *
 * Usage:
 *   node render-ebay.js [data.json] [output.html]
 *
 * Defaults to ebay-listing-data.json -> ebay-listing-output.html
 *
 * This is the "compile" step referenced in ebay-listing-template.html: the
 * admin tool's build-listing flow should produce a JSON file matching the
 * shape below, then call this same logic (or a JS port of it) to generate
 * the final HTML for both the admin preview and what gets copied to eBay.
 */
const fs = require("fs");
const path = require("path");

const dataPath = path.resolve(process.argv[2] || "ebay-listing-data.json");
const outPath = path.resolve(process.argv[3] || "ebay-listing-output.html");
const templatePath = path.resolve(__dirname, "ebay-listing-template.html");

const data = JSON.parse(fs.readFileSync(dataPath, "utf8"));
let html = fs.readFileSync(templatePath, "utf8");

function starGlyphs(stars) {
  const full = Math.floor(stars);
  const half = stars - full >= 0.5 ? 1 : 0;
  const empty = 5 - full - half;
  return "&#9733;".repeat(full) + "&#9734;".repeat(half + empty);
}

function gameCardCell(game, index, total) {
  const width = Math.floor(100 / total);
  const padLeft = index === 0 ? "0" : "6px";
  const padRight = index === total - 1 ? "0" : "6px";
  return `
        <td width="${width}%" valign="top" style="padding:0 ${padRight} 12px ${padLeft};">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#11141b;border:1px solid #232a35;border-radius:10px;overflow:hidden;">
            <tr><td><img src="${game.cover}" width="220" alt="${game.name}" style="display:block;width:100%;border:0;"></td></tr>
            <tr><td style="padding:10px 12px;">
              <div style="font-size:13px;font-weight:bold;color:#eef2f7;">${game.name}</div>
              <div style="font-size:18px;font-weight:900;color:#ffc94d;margin-top:2px;">${game.fps} <span style="font-size:10px;color:#93a0b3;font-weight:normal;">FPS</span></div>
              <div style="color:#ffc94d;font-size:11px;letter-spacing:1px;">${starGlyphs(game.stars)}</div>
            </td></tr>
          </table>
        </td>`;
}

function everydayRow(item) {
  return `      <tr><td width="18" valign="top" style="color:#ffc94d;">&#9679;</td><td><b style="color:#eef2f7;">${item.name}</b> &mdash; ${item.note}</td></tr>`;
}

const replacements = {
  "{{logo}}": data.assets.logo,
  "{{heroVideo}}": data.assets.heroVideo,
  "{{heroImage}}": data.assets.heroImage,
  "{{specCard}}": data.assets.specCard,
  "{{performanceReportUrl}}": data.assets.performanceReportUrl,
  "{{buildId}}": data.buildId,
  "{{buildName}}": data.buildName,
  "{{headline}}": data.headline,
  "{{story}}": data.story,
  "{{feelStory}}": data.feelStory,
  "{{novabenchOverall}}": data.hero.novabenchOverall,
  "{{percentile}}": data.hero.percentile,
  "{{toolBadges}}": data.toolsUsed.join(" &middot; "),
  "{{gameCards}}": data.games.map((g, i) => gameCardCell(g, i, data.games.length)).join("\n"),
  "{{gamesFootnote}}": data.gamesFootnote,
  "{{everydayRows}}": data.everyday.map(everydayRow).join("\n"),
  "{{driveHealth}}": data.driveHealth,
  "{{closingHeadline}}": data.closingHeadline,
  "{{closingSub}}": data.closingSub,
  "{{brandUrl}}": data.brandUrl,
};

// Strip the template's own explanatory HTML comment first — it's for template
// maintainers, not for eBay, and its prose literally contains "{{tokens}}" as
// an example, which would otherwise trip the leftover-token check below.
html = html.replace(/<!--[\s\S]*?FLIPFLOP EBAY LISTING TEMPLATE[\s\S]*?-->\s*/, "");

for (const [token, value] of Object.entries(replacements)) {
  html = html.split(token).join(String(value));
}

const leftover = html.match(/\{\{[A-Za-z0-9_]+\}\}/g);
if (leftover) {
  console.warn("Warning: unresolved tokens left in output:", [...new Set(leftover)].join(", "));
}

fs.writeFileSync(outPath, html, "utf8");
console.log(`Rendered ${dataPath} -> ${outPath}`);
