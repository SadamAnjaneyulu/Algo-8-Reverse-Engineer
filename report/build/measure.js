const { chromium } = require('playwright'); const path = require('path');
(async () => { const b = await chromium.launch(); const p = await b.newPage(); await p.emulateMedia({ media: 'print' }); await p.setViewportSize({ width: 680, height: 1123 });
  await p.goto('file://' + path.resolve(process.argv[2]));
  const r = await p.evaluate(() => [...document.querySelectorAll('h1, table, img, .box')].map(e => [e.tagName, (e.textContent||e.alt||'').slice(0,25).replace(/\n/g,' '), Math.round(e.getBoundingClientRect().top + scrollY), Math.round(e.getBoundingClientRect().height), Math.round(e.getBoundingClientRect().width)]));
  console.log(JSON.stringify(r)); await b.close(); })();
