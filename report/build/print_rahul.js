const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const [inp, out] = process.argv.slice(2); const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + path.resolve(inp), { waitUntil: 'load' });
  await p.pdf({ path: out, format: 'A4', printBackground: true, displayHeaderFooter: true, margin: { top: '15mm', bottom: '14mm', left: '15mm', right: '15mm' },
    headerTemplate: '<div style="font-size:6.5px;color:#7b8794;width:100%;padding:0 15mm;display:flex;justify-content:space-between;font-family:Inter,sans-serif"><span>Algo 8 reverse engineering — research summary for Rahul</span><span>11 November 2026</span></div>',
    footerTemplate: '<div style="font-size:7px;color:#52606d;width:100%;text-align:center;font-family:Inter,sans-serif">Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>' });
  await b.close();
})();
