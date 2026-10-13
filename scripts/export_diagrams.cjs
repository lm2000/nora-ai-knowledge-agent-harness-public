#!/usr/bin/env node
// Execution location: repository root. Requires Playwright, Chromium and FFmpeg.
const { chromium } = require('playwright');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { execFileSync } = require('node:child_process');

async function main() {
  const root = path.resolve(__dirname, '..');
  const manifest = JSON.parse(fs.readFileSync(path.join(root, 'public-docs.json'), 'utf8'));
  const requested = process.argv.slice(2);
  const pairs = manifest.diagram_pairs.filter(pair =>
    !requested.length || requested.includes(path.basename(pair.source, '.html')));
  if (!pairs.length || requested.some(stem => !pairs.some(pair => path.basename(pair.source, '.html') === stem))) {
    throw new Error('Specify existing diagram stems, or omit arguments to export all pairs.');
  }
  const options = { headless: true };
  if (process.env.NIS_BROWSER_EXECUTABLE) options.executablePath = process.env.NIS_BROWSER_EXECUTABLE;
  const browser = await chromium.launch(options);
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'nis-diagram-export-'));
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 1200 }, deviceScaleFactor: 1 });
    for (const pair of pairs) {
      const errors = [];
      const onError = error => errors.push(error.message);
      page.on('pageerror', onError);
      await page.goto(pathToFileURL(path.join(root, pair.source)).href);
      for (let frame = 0; frame < 30; frame++) {
        await page.evaluate(time => window.freezeDiagram(time), frame / 6);
        await page.locator('#export').screenshot({ path: path.join(temporary, `${String(frame).padStart(3, '0')}.png`) });
      }
      page.off('pageerror', onError);
      if (errors.length) throw new Error(`${pair.source}: ${errors.join('; ')}`);
      const preview = path.join(root, pair.preview);
      execFileSync(process.env.NIS_FFMPEG || 'ffmpeg', [
        '-hide_banner', '-loglevel', 'error', '-y', '-framerate', '6',
        '-i', path.join(temporary, '%03d.png'), '-vf',
        'split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3',
        '-loop', '0', preview,
      ]);
      console.log(`${pair.preview}: ${fs.statSync(preview).size} bytes`);
    }
  } finally {
    await browser.close();
    fs.rmSync(temporary, { recursive: true, force: true });
  }
}
main().catch(error => { console.error(error.message); process.exitCode = 1; });
