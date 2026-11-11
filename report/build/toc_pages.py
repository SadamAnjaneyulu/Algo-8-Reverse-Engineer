"""Second pass: find the page of every TOC heading in the first-pass PDF and write the numbers into the TOC of the HTML.
python3 build/toc_pages.py build/report.html ALGO8_COMPLETE_RESEARCH_REPORT.pdf"""
import re, sys, html
from pypdf import PdfReader
H, P = sys.argv[1:3]
norm = lambda s: re.sub(r'[^a-z0-9]', '', html.unescape(s).lower())
pages = [norm(p.extract_text() or '') for p in PdfReader(P).pages]
src = open(H, encoding='utf-8').read()
toc_start = src.index('<nav id="TOC"'); toc_end = src.index('</nav>', toc_start); toc = src[toc_start:toc_end]
def repl(m):
    text = re.sub(r'<[^>]+>', '', m.group(2)); key = norm(text)[:40]
    pg = next((i + 1 for i, t in enumerate(pages) if i >= 2 and key in t), None)
    return f'<a href="{m.group(1)}">{m.group(2)}<span class="pg">{pg or ""}</span></a>'
toc2 = re.sub(r'<a href="([^"]+)"[^>]*>(.*?)</a>', repl, re.sub(r'<span class="pg">\d*</span>', '', toc), flags=re.S)
open(H, 'w', encoding='utf-8').write(src[:toc_start] + toc2 + src[toc_end:])
print('toc entries', len(re.findall(r'class="pg"', toc2)), 'missing', len(re.findall(r'class="pg"></span>', toc2)))
