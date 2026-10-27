"""Read-only source checks plus DOCX/PDF rendering and layout validation."""
from __future__ import annotations
import argparse,hashlib,json,re,subprocess,zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
import fitz
import numpy as np
import pandas as pd
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;CACHE=HERE/'.cache';CACHE.mkdir(exist_ok=True)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def norm(s):return re.sub(r'\s+',' ',s).strip()

def run(reviewed=False):
    docx=ROOT/'Rahul_Algo8_Reverse_Engineering_Report.docx';pdf=ROOT/'Rahul_Algo8_Reverse_Engineering_Report.pdf';source=ROOT/'Rahul_Algo8_Report_Sources.md'
    assert docx.exists() and pdf.exists() and source.exists()
    evidence=json.loads((HERE/'verified_claims.json').read_text());assert evidence['counts']==dict(fill_records=41421,parent_orders=39874,cycles=35,primary_cycles=32,atomic_books=21882,index_days=170,index_bars=63678,option_contract_days=3243,trade_first='2026-06-23',trade_last='2026-10-22')
    for name,h in evidence['source_hashes'].items():
        if ':STRONG_FINDINGS.md' in name:
            content=subprocess.check_output(['git','show',name],cwd=ROOT);assert hashlib.sha256(content).hexdigest()==h
        else:assert sha(ROOT/name)==h,name
    v=json.loads((ROOT/'research/final_alpha_attribution/validation_audit.json').read_text());assert v['repository_tests']==252 and v['exactly_reproduced_numeric_artifacts']==26 and v['status']=='passed'
    for name,h in v['numeric_artifacts_sha256'].items():assert sha(ROOT/'research/final_alpha_attribution'/name)==h,name
    raw=json.loads((ROOT/'research/final_alpha_attribution/input_audit.json').read_text())
    for name,h in raw['immutable_inputs_sha256'].items():assert sha(ROOT/name)==h,name
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with zipfile.ZipFile(docx) as z:
        root=ET.fromstring(z.read('word/document.xml'));media=[n for n in z.namelist() if n.startswith('word/media/')]
        assert len(media)==12,len(media);anchors=[x.get('{'+ns['w']+'}anchor') for x in root.findall('.//w:hyperlink',ns) if x.get('{'+ns['w']+'}anchor')]
        assert len(anchors)>=12
    figures=json.loads((HERE/'figure_data.json').read_text());assert len(figures)==12
    figure_hashes={}
    for n in range(1,13):
        png=HERE/f'Figure_{n:02}.png';svg=HERE/f'Figure_{n:02}.svg';im=Image.open(png).convert('RGB');assert im.width>=1800 and np.asarray(im).std()>5
        ET.parse(svg);figure_hashes[png.name]=sha(png);figure_hashes[svg.name]=sha(svg)
    # Audit stored numeric plot inputs against the authoritative current results.
    assert figures['3']['data']['numerator']==[544,541,530,531,533,533,529]
    assert figures['3']['data']['denominator']==[544,544,544,543,543,543,544]
    assert figures['4']['data']['model28']==[28,17,19]
    motifs=pd.read_csv(ROOT/'research/policy_execution_separation/reversal_motif_ledger.csv')
    assert len(motifs)==59 and motifs.atomic_quantity_equal.sum()==49 and not motifs.same_parent_at_boundary.any()
    assert motifs.prior_atomic_quantity.gt(0).sum()==43 and motifs.prior_atomic_quantity.lt(0).sum()==16
    reversal=pd.read_csv(ROOT/'research/policy_execution_separation/reversal_pattern_coverage.csv')
    duplicate=reversal[reversal.model_id.eq(32)].iloc[0];assert duplicate.predicted_motifs==559 and duplicate.matched_contract_time==0
    manifest=json.loads((ROOT/'research/hypothesis_controller_search/outputs/search_manifest.json').read_text());assert manifest['candidate_count']==13864
    np.testing.assert_allclose(figures['8']['data']['rupees'],[1894355.5,821401.076875,475346.65375,-477316.84625],atol=1e-6,rtol=0)
    np.testing.assert_allclose(figures['9']['data']['rupees'],[475346.65375,1721.58125,-423305.62375],atol=1e-6,rtol=0)
    assert abs(sum(figures['10']['data']['rupees'])-1894355.5)<1e-6 and abs(sum(figures['11']['data']['rupees'])-1894355.5)<1e-5
    d=fitz.open(pdf);assert len(d)==22,len(d);toc={norm(title):page for level,title,page in d.get_toc()};plan=json.loads((HERE/'page_plan.json').read_text())
    for anchor,p in plan.items():assert toc.get(norm(p['title']))==p['expected_page'],(anchor,toc.get(norm(p['title'])),p['expected_page'])
    links=d[1].get_links();assert sum(x['kind']==fitz.LINK_GOTO for x in links)==12
    expected_fig_pages={1:5,2:6,3:7,4:8,5:9,6:10,7:11,8:13,9:14,10:15,11:16,12:17}
    for n,page in expected_fig_pages.items():
        p=d[page-1];assert p.get_images(),(n,page);assert f'Figure {n}.' in p.get_text(),(n,page)
    alltext='\n'.join(p.get_text() for p in d);assert '\ufffd' not in alltext
    for text in ['41,421','39,874','21,882','63,678','3,243','1,371,078.56','523,276.94','1,894,355.50','529/544','36.4%','9.8%','18.0%','16.6%','252','26']:
        assert text in alltext,text
    bounds=[];page_audit=[];rendered=[]
    for i,p in enumerate(d):
        for block in p.get_text('dict')['blocks']:
            if 'lines' not in block:continue
            for line in block['lines']:
                for span in line['spans']:
                    x0,y0,x1,y1=span['bbox']
                    if x0<30 or x1>p.rect.width-25 or y0<10 or y1>p.rect.height-10:bounds.append(dict(page=i+1,text=span['text'],bbox=span['bbox']))
        text=p.get_text();assert len(text.split())>80,(i+1,len(text.split()))
        if i:assert f'{i+1} / 22' in text,(i+1,'footer')
        pix=p.get_pixmap(matrix=fitz.Matrix(110/72,110/72),alpha=False);path=CACHE/f'page_{i+1:02}.png';pix.save(path);rendered.append(path)
        page_audit.append(dict(page=i+1,words=len(text.split()),images=len(p.get_images()),links=len(p.get_links()),render_sha256=sha(path)))
    assert not bounds,bounds[:8]
    sheets=[]
    for start in range(0,len(rendered),2):
        ims=[Image.open(p).convert('RGB') for p in rendered[start:start+2]];width=sum(im.width for im in ims)+30;height=max(im.height for im in ims)+35;sheet=Image.new('RGB',(width,height),'#DEE5E9');draw=ImageDraw.Draw(sheet);x=10
        for j,im in enumerate(ims):sheet.paste(im,(x,25));draw.text((x+5,7),f'Page {start+j+1}',fill='black');x+=im.width+10
        path=CACHE/f'review_{start+1:02}_{min(start+2,len(rendered)):02}.png';sheet.save(path);sheets.append(str(path.relative_to(ROOT)))
    changed=subprocess.check_output(['git','diff','21ce61d','--name-only'],cwd=ROOT,text=True).splitlines();allowed=['Rahul_Algo8_Reverse_Engineering_Report.docx','Rahul_Algo8_Reverse_Engineering_Report.pdf','Rahul_Algo8_Report_Sources.md']
    assert all(x in allowed or x.startswith('rahul_report_figures/') for x in changed),changed
    result=dict(status='passed' if reviewed else 'automated_checks_passed_visual_review_pending',pdf_pages=len(d),mandatory_figures=12,vector_and_high_resolution_figures=True,
        toc_internal_links=12,toc_page_numbers_match=True,pdf_outline_entries=len(d.get_toc()),all_pages_rendered=True,all_pages_visually_reviewed=reviewed,
        text_spans_outside_safe_bounds=bounds,headline_values_reconciled=True,underlying_research_artifacts_unchanged=True,
        source_files_reverified=len(raw['immutable_inputs_sha256']),saved_research_validation=dict(tests_passed=252,numeric_artifacts_reproduced=26,inspection='saved audit inspected and current hashes reverified; trading searches not rerun'),
        outcome='B',original_controller_or_alpha_recovery_claimed=False,document_sha256={p.name:sha(p) for p in [docx,pdf,source]},figure_sha256=figure_hashes,
        page_audit=page_audit,review_sheets=sheets,rendering='DOCX converted with LibreOffice; every PDF page rendered with PyMuPDF at110dpi for visual inspection')
    (HERE/'report_validation.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['document_sha256','figure_sha256','page_audit','review_sheets']},indent=2));print('Review sheets:',*sheets,sep='\n')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--reviewed',action='store_true');args=parser.parse_args();run(args.reviewed)
