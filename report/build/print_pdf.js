// Print an HTML file to PDF with page numbers (Chromium via Playwright).  node print_pdf.js in.html out.pdf
const { chromium } = require('playwright'); const path = require('path');
(async () => {
  const [inp, out] = process.argv.slice(2);
  const b = await chromium.launch(); const p = await b.newPage();
  await p.goto('file://' + path.resolve(inp), { waitUntil: 'load' });
  await p.pdf({ path: out, format: 'A4', printBackground: true, displayHeaderFooter: true, margin: { top: '16mm', bottom: '18mm', left: '15mm', right: '15mm' },
    headerTemplate: '<div style="font-size:7px;color:#7b8794;width:100%;padding:0 15mm;text-align:right;font-family:Inter,sans-serif">Algo 8 — Complete Research Report · 11 November 2026</div>',
    footerTemplate: '<div style="font-size:8px;color:#52606d;width:100%;text-align:center;font-family:Inter,sans-serif">Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>' });
  await b.close();
})();
