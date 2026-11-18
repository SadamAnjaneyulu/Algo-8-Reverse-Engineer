"""Editable Word version of the 6-page report: pandoc converts the Markdown, python-docx applies a compact A4 layout.
python3 report/build/make_docx.py  (run from the repository root)"""
import subprocess, os, copy
from docx import Document
from docx.shared import Pt, Mm, Inches, RGBColor
from docx.enum.text import WD_BREAK
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
HERE = os.path.dirname(os.path.abspath(__file__)); R = os.path.dirname(HERE)
SRC = os.path.join(R, 'ALGO8_RESEARCH_REPORT_RAHUL.md'); TMP = os.path.join(HERE, 'rahul_raw.docx'); OUT = os.path.join(R, 'ALGO8_RESEARCH_REPORT_RAHUL.docx')
subprocess.run(['pandoc', SRC, '-f', 'markdown+smart', '-t', 'docx', '--resource-path', R, '-o', TMP], check=True)
d = Document(TMP); INK = RGBColor(0x10, 0x2a, 0x43); BLUE = RGBColor(0x2b, 0x6c, 0xb0)
s = d.sections[0]; s.page_width, s.page_height = Mm(210), Mm(297); s.left_margin = s.right_margin = Mm(15); s.top_margin = Mm(15); s.bottom_margin = Mm(14)
def sty(n):
    for x in d.styles:
        if x.name.lower() == n.lower(): return x
    return None
def font(style, size, bold=None, color=None, name='Calibri'):
    st = sty(style)
    if st is None: return
    st.font.name = name; st.font.size = Pt(size)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), name)
    if bold is not None: st.font.bold = bold
    if color is not None: st.font.color.rgb = color
    pf = st.paragraph_format; pf.space_before = Pt(0); pf.space_after = Pt(3); pf.line_spacing = 1.08
for n in ('Normal', 'Body Text', 'First Paragraph', 'Compact'): 
    font(n, 9.5)
font('Heading 1', 14, True, INK); sty('Heading 1').paragraph_format.space_before = Pt(0); sty('Heading 1').paragraph_format.space_after = Pt(5)
font('Heading 2', 11, True, RGBColor(0x1c, 0x3d, 0x5a)); sty('Heading 2').paragraph_format.space_before = Pt(6); sty('Heading 2').paragraph_format.space_after = Pt(3)
for n in ('Title', 'Subtitle'):
    font(n, 18 if n == 'Title' else 9, True if n == 'Title' else False, INK)
def shade(cell, hexcol):
    tcPr = cell._tc.get_or_add_tcPr(); sh = OxmlElement('w:shd'); sh.set(qn('w:val'), 'clear'); sh.set(qn('w:color'), 'auto'); sh.set(qn('w:fill'), hexcol); tcPr.append(sh)
def borders(tbl):
    tblPr = tbl._tbl.tblPr; b = OxmlElement('w:tblBorders')
    for e in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'):
        x = OxmlElement(f'w:{e}'); x.set(qn('w:val'), 'single'); x.set(qn('w:sz'), '4'); x.set(qn('w:space'), '0'); x.set(qn('w:color'), 'B8C4D0'); b.append(x)
    tblPr.append(b)
    m = OxmlElement('w:tblCellMar')
    for e, v in (('top', 20), ('left', 60), ('bottom', 20), ('right', 60)):
        x = OxmlElement(f'w:{e}'); x.set(qn('w:w'), str(v)); x.set(qn('w:type'), 'dxa'); m.append(x)
    tblPr.append(m)
# tables: borders, compact font, shaded header, autofit to width, rows may not split
for t in d.tables:
    borders(t); t.autofit = True
    for i, row in enumerate(t.rows):
        trPr = row._tr.get_or_add_trPr(); cs = OxmlElement('w:cantSplit'); trPr.append(cs)
        for c in row.cells:
            if i == 0: shade(c, 'E8EEF5')
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(0); p.paragraph_format.space_before = Pt(0); p.paragraph_format.line_spacing = 1.0
                for r in p.runs: r.font.size = Pt(8); r.font.name = 'Calibri'
                if i == 0:
                    for r in p.runs: r.bold = True
# sections flow naturally (no forced page break) so the editable file stays compact
first = True
for p in d.paragraphs:
    if p.style.name.lower() == 'heading 1':
        if first: first = False
        else: p.paragraph_format.keep_with_next = True      # sections flow naturally so the editable file stays compact
# charts: merge the two chart images of page 3 into one paragraph; size all images
from docx.shared import Emu
body = d.element.body
imgs = [p for p in d.paragraphs if p._p.xpath('.//w:drawing')]
def resize(p, w_in):
    for inl in p._p.xpath('.//wp:inline'):
        ext = inl.find(qn('wp:extent')); cx, cy = int(ext.get('cx')), int(ext.get('cy')); k = Inches(w_in) / cx
        ext.set('cx', str(int(cx * k))); ext.set('cy', str(int(cy * k)))
        for e in inl.iter(qn('a:ext')): 
            if e.get('cx'): e.set('cx', str(int(int(e.get('cx')) * k))); e.set('cy', str(int(int(e.get('cy')) * k)))
        for e in inl.iter('{http://schemas.openxmlformats.org/drawingml/2006/picture}spPr'): pass
# image order in the document: 0 readiness (page 1), 1-2 the two exit-engine charts (page 3), 3 re-sale chart (page 4)
assert len(imgs) == 4, len(imgs)
resize(imgs[0], 6.9)
a, b = imgs[1], imgs[2]; resize(a, 3.45); resize(b, 3.45)
for r in b._p.xpath('./w:r'): a._p.append(r)
b._p.getparent().remove(b._p)
resize(imgs[3], 3.6)
for q in (imgs[0], a, imgs[3]): q.paragraph_format.space_after = Pt(2)
# page-1 masthead: first paragraph becomes the title line
first_p = d.paragraphs[0]
for r in first_p.runs: r.font.size = Pt(18); r.font.bold = True; r.font.color.rgb = INK
d.core_properties.title = 'Algo 8 Reverse Engineering — Research Summary'; d.core_properties.author = 'Research team'; d.core_properties.subject = 'Prepared for Rahul, 11 November 2026'
# footer page numbers
ft = s.footer.paragraphs[0]; ft.alignment = 1
def fld(par, instr):
    r = par.add_run(); b = OxmlElement('w:fldChar'); b.set(qn('w:fldCharType'), 'begin'); r._r.append(b)
    r2 = par.add_run(); it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve'); it.text = instr; r2._r.append(it)
    r3 = par.add_run(); e = OxmlElement('w:fldChar'); e.set(qn('w:fldCharType'), 'end'); r3._r.append(e)
ft.add_run('Algo 8 research summary for Rahul · 11 November 2026 · Page '); fld(ft, 'PAGE')
for r in ft.runs: r.font.size = Pt(8); r.font.color.rgb = RGBColor(0x52, 0x60, 0x6d)
d.save(OUT); os.remove(TMP); print('saved', OUT)
