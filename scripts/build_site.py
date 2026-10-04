#!/usr/bin/env python3
"""Build the Arabic research site using only the Python standard library.

Canonical content: content/source.json and content/editorial.json.
Run from any directory: python scripts/build_site.py
"""
from pathlib import Path
from html import escape
import json
import os
import re

ROOT = Path(__file__).resolve().parents[1]
TITLE = 'تصميم وتطوير مختبر الهندسة بالواقع الافتراضي'
SITE = 'https://zuhdizahdeh.github.io/geometry-vr-lab-research/'
REPO = 'https://github.com/ZuhdiZahdeh/geometry-vr-lab-research'
APP = 'https://zuhdizahdeh.github.io/math-apps/geometry-vr-lab/index.html'
source = json.loads((ROOT / 'content/source.json').read_text(encoding='utf-8'))
pages = source['pages']
page_by_path = {p['path']: p for p in pages}
chapters = [p for p in pages if p['kind'] == 'chapter']
appendices = [p for p in pages if p['kind'] == 'appendix']
search_items = []

def read_data(path, default):
    f = ROOT / path
    return json.loads(f.read_text(encoding='utf-8')) if f.exists() else default

def rel(current, target):
    if target.startswith(('https:', 'http:', 'mailto:', '#')):
        return target
    file, sep, fragment = target.partition('#')
    relative = os.path.relpath(ROOT / file, (ROOT / current).parent).replace(os.sep, '/')
    return relative + (sep + fragment if sep else '')

def link(current, target, text, cls=''):
    return f'<a href="{escape(rel(current, target), quote=True)}"' + (f' class="{cls}"' if cls else '') + f'>{escape(text)}</a>'

def root_prefix(path):
    return rel(path, 'index.html').removesuffix('index.html')

def section(id, title, html):
    return f'<section class="section" id="{escape(id)}"><h2>{escape(title)} <a class="anchor" href="#{escape(id)}" aria-label="رابط مباشر إلى {escape(title, quote=True)}">#</a></h2>{html}</section>'

def table(headers, rows, caption='', id=''):
    cap = f'<caption>{escape(caption)}</caption>' if caption else ''
    return '<div class="table-wrap"' + (f' id="{id}"' if id else '') + '><table>' + cap + '<thead><tr>' + ''.join(f'<th scope="col">{escape(str(h))}</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{str(c)}</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table></div>'

qa = read_data('content/evidence-notes.json', {})
citation_map = {v['source']: v['references'] for v in qa.get('citation_link_suggestions', [])}
source_locations = {}
for p in pages:
    for b in p['blocks']:
        if b.get('source'):
            source_locations.setdefault(b['source'], (p['path'], b.get('id', 'top'), p['title']))
backlinks = {}
for pid, refs in citation_map.items():
    for ref in refs:
        backlinks.setdefault(ref.lower().replace('ref-', 'ref-'), []).append(source_locations[pid])

def source_blocks(page):
    path = page['path']
    output = []
    for b in page['blocks']:
        typ = b['type']
        sid = b.get('source', '')
        bid = b.get('id', '')
        attributes = f' data-source="{escape(sid)}"'
        if typ == 'heading':
            if bid == 'top':
                continue  # Source title is preserved in the article header.
            level = max(2, min(4, b['level']))
            output.append(f'<h{level} id="{bid}"{attributes}>{b["html"]} <a class="anchor" href="#{bid}" aria-label="رابط القسم">#</a></h{level}>')
        elif typ == 'paragraph':
            cls = 'reference' if bid.startswith('ref-') else 'source-paragraph'
            # English abstract and bibliographic entries remain readable LTR.
            direction = ' dir="ltr" lang="en"' if (bid.startswith('ref-') and re.match(r'^[A-Za-z]', b['text'])) or (path == 'abstract/index.html' and sid in ('P0023','P0024','P0025','P0026')) or b.get('language') == 'en' else ''
            output.append(f'<p id="{bid}" class="{cls}"{attributes}{direction}>{b["html"]}</p>')
            if sid in citation_map:
                output.append('<div class="backlinks"><span>المراجع المرتبطة:</span>' + ''.join(link(path, f'references/index.html#{r.lower()}', r.replace('REF-', 'مرجع ')) for r in citation_map[sid]) + '</div>')
            if bid in backlinks:
                output.append('<div class="backlinks"><span>مواضع الاستشهاد:</span>' + ''.join(link(path, f'{p}#{anchor}', title.split(':')[0]) for p, anchor, title in backlinks[bid]) + '</div>')
        elif typ == 'table':
            rows = b.get('rows_html', b['rows'])
            presentation = b.get('presentation')
            if presentation == 'callout':
                output.append(f'<aside class="note" id="{bid}"{attributes}>' + ''.join(f'<p>{c}</p>' for row in rows for c in row if c) + '</aside>')
            elif presentation == 'image-layout':
                # The adjacent image blocks preserve both captions from these cells.
                output.append(f'<div id="{bid}"{attributes} class="table-caption">صورتا الأسطوانة والكرة من التوثيق التطبيقي.</div>')
            else:
                metadata = sid in ('T001', 'T019', 'T020', 'T021', 'T023')
                inner = f'<div class="table-wrap" id="{bid}"{attributes}><table><caption>{escape(b["caption"])}</caption>'
                if metadata:
                    inner += '<tbody>' + ''.join('<tr><th scope="row">' + row[0] + '</th>' + ''.join(f'<td>{c}</td>' for c in row[1:]) + '</tr>' for row in rows) + '</tbody>'
                else:
                    inner += '<thead><tr>' + ''.join(f'<th scope="col">{c}</th>' for c in rows[0]) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in row) + '</tr>' for row in rows[1:]) + '</tbody>'
                inner += '</table></div>'
                if presentation == 'contents':
                    inner = '<details><summary>فهرس النسخة الورقية وأرقام صفحاتها</summary>' + inner + '</details>'
                output.append(inner)
        elif typ == 'image':
            cap = f'<figcaption>{escape(b["caption"])}</figcaption>' if 'table' in b.get('caption_source', {}) else ''
            output.append(f'<figure class="figure" id="{bid}"{attributes} data-image="{b["source_image"]}"><a href="{rel(path,b["src"])}"><img src="{rel(path,b["src"])}" alt="{escape(b["alt"],quote=True)}" width="{b["width"]}" height="{b["height"]}" loading="lazy"></a>{cap}</figure>')
    return '\n'.join(output)

NAV = [('index.html', 'الرئيسية'), ('index.html#chapters', 'الفصول'), ('appendices/index.html', 'الملاحق'), ('development/index.html', 'التطوير'), ('evidence/index.html', 'الوسائط والسجلات'), ('references/index.html', 'المراجع'), ('downloads/index.html', 'التنزيلات')]
LABELS = {'chapter': 'الفصل الأكاديمي', 'appendix': 'ملحق بحثي', 'about': 'عن البحث', 'abstract': 'ملخص البحث', 'references': 'التوثيق العلمي', 'development': 'التطوير بعد السمينار', 'versions': 'هوية الإصدارات', 'citation': 'الاستشهاد وحقوق الاستخدام', 'evidence': 'الوسائط والسجلات', 'appendices': 'دليل الملاحق'}

def header(path):
    links = ''.join(f'<a href="{rel(path,t)}"' + (' aria-current="page"' if path == t else '') + f'>{name}</a>' for t,name in NAV)
    mark = '<svg class="brand-mark" viewBox="0 0 44 44" aria-hidden="true"><path d="M22 3 39 13v19L22 42 5 32V13Z M5 13l17 10 17-10 M22 23v19 M22 3v20" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>'
    return f'<a class="skip-link" href="#main">انتقل إلى المحتوى</a><header class="site-header"><div class="container"><a class="brand" href="{rel(path,"index.html")}">{mark}<span>مختبر الهندسة بالواقع الافتراضي<small>البحث والتصميم والتوثيق التطبيقي</small></span></a><nav class="main-nav" aria-label="التنقل الرئيسي">{links}</nav></div></header>'

def footer(path):
    return '<footer class="site-footer"><div class="container"><div><p><strong>زهدي زاهدة · تصميم وتطوير مختبر الهندسة بالواقع الافتراضي</strong></p><p>الإصدار الإلكتروني 0.1.0 · 4 تشرين الأول/أكتوبر 2026</p><p>دراسة تصميم وتطوير، يتطلب قياس أثر التعلم دراسة ميدانية مستقلة.</p></div><div class="inline-links">' + link(path,'versions/index.html','سجل الإصدارات') + link(path,'citation/index.html','الاستشهاد والحقوق') + f'<a href="{REPO}">المستودع على GitHub</a><a href="{APP}">صفحة التطبيق</a>' + '</div></div></footer>'

def search(path):
    return '<div class="search-box"><label for="site-search">ابحث في الفصول والملاحق</label><input id="site-search" type="search" placeholder="مثل: التصور الفراغي، الأسطوانة، الإرشاد الصوتي" autocomplete="off" aria-controls="search-results"><div id="search-results" class="search-results" aria-live="polite"></div><p class="search-hint">ابحث بكلمتين أو أكثر للوصول إلى القسم، تعمل الروابط دون الحاجة إلى البحث.</p></div>'

def document(path, title, content, toc=None, page=None, home=False):
    canonical = SITE + path.removesuffix('index.html')
    head = f'<!doctype html>\n<html lang="ar" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{escape(title)} | مختبر الهندسة: البحث</title><meta name="description" content="موقع أكاديمي يوثق تصميم وتطوير بيئة الواقع الافتراضي للهندسة الفراغية، بفصول البحث والملاحق والوسائط والمراجع."><link rel="canonical" href="{canonical}"><link rel="stylesheet" href="{rel(path,"assets/css/site.css")}"><script defer src="{rel(path,"assets/js/site.js")}"></script></head><body data-search-index="{rel(path,"data/search-index.json")}">'
    if home:
        main = '<main id="main" class="container">' + content + '</main>'
    else:
        kind = (page or {}).get('kind', '')
        first = next((b for b in (page or {}).get('blocks', []) if b.get('id') == 'top' and b['type'] == 'heading'), None)
        h1 = first['html'] if first else escape(title)
        src = f' data-source="{first["source"]}"' if first else ''
        breadcrumb = '<ol class="breadcrumbs"><li>' + link(path,'index.html','الرئيسية') + '</li><li>' + escape(title) + '</li></ol>'
        intro = f'<header class="article-header"><span class="eyebrow">{LABELS.get(kind,"الموقع الأكاديمي")}</span><h1 id="top"{src}>{h1}</h1><div class="meta"><span>إعداد: زهدي زاهدة</span><span>نسخة مصدرية: 29 يوليو 2026</span><span>إصدار الموقع: 0.1.0</span></div></header>'
        if kind in ('development','versions','citation','downloads','appendix-new'):
            intro = intro.replace('نسخة مصدرية: 29 يوليو 2026','توثيق إلكتروني: أكتوبر 2026')
        toc = toc or []
        toc_html = '<aside class="toc" aria-label="فهرس الصفحة"><h2>في هذه الصفحة</h2><button class="toc-toggle" type="button" aria-expanded="true" aria-controls="toc-items">عرض أقسام الصفحة</button><ol id="toc-items">' + ''.join(f'<li><a href="#{escape(id)}">{escape(text)}</a></li>' for id,text in toc) + '<li>' + link(path,'index.html#chapters','جميع الفصول') + '</li><li>' + link(path,'appendices/index.html','جميع الملاحق') + '</li></ol></aside>'
        main = '<main id="main" class="container">' + breadcrumb + '<div class="layout">' + toc_html + '<article class="reading">' + intro + search(path) + content + '</article></div></main>'
    text = head + header(path) + main + footer(path) + '</body></html>\n'
    target = ROOT / path
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text,encoding='utf-8')

def cards(path, items):
    return '<div class="cards">' + ''.join(f'<a class="card" href="{rel(path,p["path"])}"><span class="eyebrow">{LABELS.get(p["kind"], "البحث")}</span><h3>{escape(p["title"])}</h3><span class="card-link">قراءة الصفحة ←</span></a>' for p in items) + '</div>'

def source_note(page):
    return '<aside class="note note--historical"><p>' + escape(page['notice']) + ' ' + link(page['path'],'development/index.html','اقرأ توثيق التطوير اللاحق') + '.</p></aside>'

def chapter_navigation(page):
    series = chapters if page['kind']=='chapter' else appendices
    index = series.index(page)
    prev = series[index-1] if index else None
    next = series[index+1] if index+1 < len(series) else None
    html = '<nav class="chapter-nav" aria-label="تسلسل القراءة">'
    html += '<a href="'+rel(page['path'],prev['path'] if prev else 'index.html#chapters')+'"><small>السابق</small>'+escape(prev['title'] if prev else 'فهرس البحث')+'</a>'
    if not next and page['kind']=='chapter':
        next={'path':'references/index.html','title':'المراجع'}
    elif not next:
        next={'path':'appendices/appendix-j/index.html','title':'الملحق (ي): تطوير المرحلة المدمجة'}
    html += '<a class="next" href="'+rel(page['path'],next['path'])+'"><small>التالي</small>'+escape(next['title'])+'</a></nav>'
    return html

def add_index(page):
    current_title = page['title']
    current_id = 'top'
    chunks = []
    def flush():
        if chunks:
            search_items.append({'title':current_title,'url':'../'+page['path']+'#'+current_id,'text':' '.join(chunks),'type':LABELS.get(page['kind'],'البحث')})
    for b in page.get('blocks',[]):
        if b['type']=='heading':
            flush();chunks=[]
            current_id=b['id'];current_title=b.get('navigation_title',b['text'])
        elif b['type']=='paragraph':chunks.append(b['text'])
        elif b['type']=='table':chunks.extend(c for row in b['rows'] for c in row)
    flush()

def build_home(page):
    path=page['path']
    hero = f'<section class="hero"><div class="hero-copy"><span class="eyebrow">من التصميم التربوي إلى التجربة الغامرة</span><h1>{TITLE}</h1><p class="lede">بحث يوثّق بناء بيئة تعليمية تفاعلية لطلبة المرحلة الثانوية، لاستكشاف المجسّمات والتحويلات الهندسية والمقاطع المستوية الناتجة عن القطع.</p><div class="meta"><span>إعداد: زهدي زاهدة</span><span>دراسة تصميم وتطوير</span><span>نسخة أكاديمية مؤرخة · تطوير متواصل</span></div><div class="inline-links">{link(path,chapters[0]["path"],"ابدأ قراءة البحث","button")}{link(path,"development/index.html","التطوير بعد السمينار","button button--secondary")}</div></div><figure class="hero-visual"><img src="assets/images/figure-i-05.jpeg" alt="لقطة من التطبيق تعرض المكعب وأدلة الوجه والحافة والرأس" width="1600" height="900"><figcaption>لقطة من التوثيق التطبيقي السابق: استكشاف الوجه والحافة والرأس.</figcaption></figure></section>'
    intro = '<div class="stats"><div><strong>5</strong><span>فصول مترابطة</span></div><div><strong>10</strong><span>ملاحق بحثية وتطويرية</span></div><div><strong>32</strong><span>مرجعًا من النسخة المصدرية</span></div><div><strong>7</strong><span>مقاطع توثيق تطبيقية</span></div></div>'
    scope = '<aside class="note"><p><strong>نطاق هذا الموقع:</strong> يحفظ البحث المرفق المؤرخ في 29 يوليو 2026، ويضيف توثيق التطوير اللاحق ودمج مشهدي التهيئة والمجسّمات والصوت. لا تتضمن الدراسة الحالية تجربة أثر على عينة من الطلبة.</p></aside>'
    catalog = section('chapters','فصول البحث',cards(path,chapters))
    extras = section('reading-paths','مسارات القراءة والتوثيق',cards(path,[page_by_path['about/index.html'],page_by_path['abstract/index.html'],{'path':'development/index.html','title':'من التصميم السابق إلى المرحلة المدمجة','kind':'development'},{'path':'evidence/index.html','title':'الصور والفيديوهات والجداول وسجل المواد','kind':'evidence'},page_by_path['appendices/index.html'],page_by_path['references/index.html']]))
    originals = section('source-contents','الفهرس المطبوع في النسخة المصدرية',source_blocks(page))
    document(path,TITLE,hero+intro+scope+search(path)+catalog+extras+originals,home=True)

def build_evidence(page):
    path=page['path']
    videos=read_data('data/videos.json',[])
    if isinstance(videos,dict):videos=videos.get('videos',videos.get('items',[]))
    gallery=read_data('data/gallery.json',[])
    if isinstance(gallery,dict):gallery=gallery.get('items',gallery.get('images',[]))
    content=source_note(page)+source_blocks(page)
    content+=section('evidence-scope','قراءة الدليل التطبيقي','<p>تعرض هذه الصفحة الوسائط المرفقة كما صنّفها سجل المواد. المقاطع واللقطات التالية توثق بنية التطبيق السابقة ومحتواه، لم تُرفق بعد لقطة أو تسجيل محدد الهوية للبناء المدمج الأحدث.</p><p>للمشهد المدمج راجع '+link(path,'appendices/appendix-j/index.html','الملحق (ي)')+'، وللتوثيق الداخلي لإصدار يوليو راجع '+link(path,'appendices/appendix-i/index.html','الملحق (ط)')+'.</p>')
    gallery_html='<div class="evidence-grid">'
    for v in videos:
        vid=v.get('id','')
        poster=v.get('poster','')
        file=v.get('path','')
        duration=v.get('duration',v.get('duration_seconds',''))
        if isinstance(duration,(int,float)):duration=f'{int(duration)//60}:{int(duration)%60:02d}'
        title=v.get('titleArabic',v.get('title_ar',v.get('title','')))
        gallery_html+=f'<article class="evidence-card" id="{vid.lower()}"><video controls preload="none" poster="{rel(path,poster)}" aria-label="{escape(title,quote=True)}"><source src="{rel(path,file)}" type="video/mp4">{link(path,file,"تحميل الفيديو")}</video><h3>{escape(title)}</h3><div class="meta"><span>{escape(vid)}</span><span>المدة: <bdi>{duration}</bdi></span><span class="status status--historical">توثيق سابق</span></div><p>المصدر: <bdi>{escape(v.get("sourceFilename",v.get("source_filename","")))}</bdi></p>{link(path,file,"فتح أو تنزيل الفيديو")}</article>'
    gallery_html+='</div><p class="table-caption">المقاطع بصوتها الأصلي. ضُغط الفيديوهان 04 و05 للنشر مع الحفاظ على الدقة والمدة والصوت، يسجل ملف بيانات الفيديو بصمتي الأصل ونسخة النشر. لم يُنجز تفريغ نصي مكافئ أو مراجعة سمعية شاملة، يُضافان في تحديث لاحق.</p>'
    content+=section('videos','مقاطع توثيق التطبيق',gallery_html)
    photo='<div class="evidence-grid">'
    for g in gallery:
        title=g.get('titleArabic',g.get('title_ar',g.get('title','')))
        image=g.get('path',g.get('src',''))
        photo+=f'<figure class="evidence-card" id="{g["id"].lower()}"><a href="{rel(path,image)}"><img src="{rel(path,image)}" alt="{escape(title,quote=True)}" loading="lazy"></a><figcaption><h3>{escape(title)}</h3><p>{escape(g.get("statusHistoricalCaption","لقطة من المواد المرفقة، لا تحدد وحدها هوية البناء الأحدث."))}</p><small>{escape(g["id"])}</small></figcaption></figure>'
    photo+='</div>'
    content+=section('images','لقطات منتقاة للمقاطع الناتجة عن القطع',photo)
    rows=[]
    for p in pages:
        for b in p['blocks']:
            if b['type']=='table':rows.append([escape(b['source']),link(path,p['path']+'#'+b['id'],b['caption']),escape({'callout':'إطار منهجي','contents':'فهرس مطبوع','image-layout':'تخطيط صور'}.get(b.get('presentation'),'جدول أو سجل')),escape(p['title'].split(':')[0])])
    content+=section('table-directory','دليل الجداول والإطارات والسجلات',table(['المعرف','العنوان والرابط','النوع','الموضع'],rows,caption='23 عنصر جدول في المستند، منها 8 جداول بحثية مرقمة'))
    inventory=read_data('data/inventory.json',{})
    records=inventory if isinstance(inventory,list) else inventory.get('records',inventory.get('items',[]))
    if not records and isinstance(inventory,dict):
        for k in ('images','videos','tables','files'):
            records.extend(dict(x,kind=k) for x in inventory.get(k,[]))
    rows=[]
    for r in records:
        rows.append([escape(str(r.get('id',''))),escape(str(r.get('kind',r.get('type','')))),escape(str(r.get('title',r.get('titleArabic',r.get('title_ar',''))))),escape(str(r.get('sourceFilename',r.get('source_filename',r.get('source',''))))),escape(str(r.get('status',r.get('availability','مادة في سجل الجرد'))))])
    inv_controls='<div class="inventory-controls"><div><label for="inventory-search">تصفية سجل المواد</label><input id="inventory-search" type="search" placeholder="ابحث بالمعرف أو اسم الملف أو النوع"></div><p class="inventory-count" id="inventory-count"></p></div>'
    content+=section('inventory','سجل المواد المرفقة',inv_controls+table(['المعرف','النوع','الوصف','المصدر','الحالة'],rows,caption='السجل يفهرس المواد، لا يعني الإدراج أن جميع الملفات نُشرت على الموقع.',id='inventory-table'))
    content+=section('pending','مواد التوثيق التي تحتاج إلى استكمال',table(['المادة','المطلوب لاستكمالها'],[[escape(x['material']),escape(x['needed'])] for x in qa.get('pending_evidence',[])]))
    toc=[('evidence-scope','نطاق الأدلة'),('videos','الفيديوهات'),('images','الصور'),('table-directory','الجداول'),('inventory','سجل المواد'),('pending','مواد الاستكمال')]
    document(path,'الوسائط والجداول وسجل المواد',content,toc,page)

def build_downloads():
    path='downloads/index.html'
    files=[('downloads/research-source-2026-07-29.docx','ملف البحث المرفق — نسخة 29 يوليو 2026 (Word)','نسخة المصدر المحدّثة بالإرشاد الصوتي، لم تُثبت مطابقتها لملف السمينار الأول.'),('downloads/research-map.docx','خريطة الفصول وخطة استكمال المواد (Word)','الخريطة التفصيلية وسجل نقاط الاستكمال.'),('downloads/research-inventory.xlsx','سجل المحتوى والوسائط (Excel)','الفصول والأقسام والصور والفيديوهات والجداول والملفات والمراجع والفجوات.'),('content/source.json','النقل المنظم للمحتوى (JSON)','437 فقرة غير فارغة و23 عنصر جدول وتسعة مواضع صور، محفوظة بمعرّفات المصدر.'),('data/inventory.json','سجل المواد المفتوح للقراءة (JSON)','بيانات وصفية لا تتضمن مسارات العمل المحلية.')]
    html='<ul class="download-list">'+''.join('<li>'+link(path,f,label)+f'<small>{escape(desc)}</small></li>' for f,label,desc in files)+'</ul>'
    content=section('research-files','ملفات البحث والسجل',html)+section('implementation-docs','وثائق التطوير', '<ul class="download-list">'+''.join('<li>'+link(path,f,t)+'</li>' for f,t in [('docs/foundations-implementation.md','توثيق تنفيذ المرحلة المدمجة'),('docs/foundations-voiceover.md','توثيق نظام الإرشاد الصوتي'),('docs/foundations-voiceover-manifest.json','سجل ملفات الصوت وأحداثها')])+'</ul><p>هذه الوثائق تصف التنفيذ والربط. ملفات Unity وملفات الصوت الأصلية ليست ضمن حزمة هذا الموقع.</p>')
    document(path,'ملفات البحث والتنزيلات',content,[('research-files','ملفات البحث'),('implementation-docs','وثائق التطوير')],{'kind':'downloads'})

def main():
    for page in pages:
        add_index(page)
        if page['path']=='index.html':build_home(page);continue
        if page['path']=='evidence/index.html':build_evidence(page);continue
        content=source_note(page)+source_blocks(page)
        toc=[(b['id'],b.get('navigation_title',b['text'])) for b in page['blocks'] if b['type']=='heading' and b['id']!='top']
        if page['kind'] in ('chapter','appendix'):content+=chapter_navigation(page)
        if page['kind']=='appendices':
            content+=section('source-appendices','ملاحق النسخة المصدرية',cards(page['path'],appendices))
            content+=section('development-appendix','الملحق الجديد للتطوير اللاحق',cards(page['path'],[{'path':'appendices/appendix-j/index.html','title':'الملحق (ي): دمج المرحلة التأسيسية والإرشاد الصوتي','kind':'appendix'}]))
            toc=[('source-appendices','الملاحق (أ–ط)'),('development-appendix','الملحق (ي)')]
        if page['kind']=='references':
            content='<aside class="note note--historical"><p>نُقلت المداخل الـ32 كما وردت في النسخة المصدرية. أُضيفت روابط إحالة وعودة لمواضع محددة في المتن. يحتاج اكتمال البيانات وصحة الروابط الخارجية إلى مراجعة مرجعية لاحقة.</p></aside>'+content
            toc=[(b['id'],b.get('text','')) for b in page['blocks'] if b['type']=='heading' and b['id']!='top']
        document(page['path'],page['title'],content,toc,page)
    editorial=read_data('content/editorial.json',{'pages':[]})
    for page in editorial['pages']:
        prefix=root_prefix(page['path'])
        content=''
        for s in page['sections']:
            html=s['html'].replace('[[ROOT]]',prefix)
            content+=section(s['id'],s['title'],html)
            clean=re.sub('<[^>]+>',' ',html)
            search_items.append({'title':s['title'],'url':'../'+page['path']+'#'+s['id'],'text':clean,'type':'توثيق التطوير' if 'appendix-j' in page['path'] or 'development' in page['path'] else 'عن الموقع'})
        document(page['path'],page['title'],content,[(s['id'],s['title']) for s in page['sections']],page)
    build_downloads()
    (ROOT/'data').mkdir(exist_ok=True)
    (ROOT/'data/search-index.json').write_text(json.dumps(search_items,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    site_pages=sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob('index.html'))
    (ROOT/'data/site-manifest.json').write_text(json.dumps({'title':TITLE,'site_version':'0.1.0','source_date':'2026-07-29','published_edition_date':'2026-10-04','pages':site_pages,'source_counts':{k:source['summary'][k] for k in ('paragraphs_nonempty_preserved','tables_preserved','image_placements_preserved','references_preserved')}},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(f'Built {len(site_pages)} pages, {len(search_items)} search sections.')

if __name__=='__main__':main()
