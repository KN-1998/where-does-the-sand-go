"""Read-only PDF/PNG rendering assets for manual QA (Pillow, pypdf, Poppler)."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import subprocess
from PIL import Image,ImageDraw
from pypdf import PdfReader


def render(job):
    pdf,out=job
    reader=PdfReader(pdf)
    if len(reader.pages)!=1:raise RuntimeError(f'Expected one page: {pdf}')
    subprocess.run(['pdftoppm','-f','1','-singlefile','-r','110','-png',str(pdf),str(out)],
                   check=True,capture_output=True)
    png=out.with_suffix('.png')
    with Image.open(png) as im:size=im.size
    text=reader.pages[0].extract_text() or ''
    raster=pdf.name.startswith(('F1_','F13_','F14_'))
    if raster and not list(reader.pages[0].images):raise RuntimeError(f'Missing heatmap raster: {pdf}')
    if not raster and len(text)<40:raise RuntimeError(f'Missing vector text: {pdf}')
    return {'name':pdf.name,'pages':1,'sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),
            'render_size':size,'text_characters':len(text),'content':'300dpi raster heatmap' if raster else 'vector chart'}


def sheets(paths,folder,prefix):
    saved=[]
    for begin in range(0,len(paths),6):
        batch=paths[begin:begin+6];sheet=Image.new('RGB',(1600,1710),'white');draw=ImageDraw.Draw(sheet)
        for index,path in enumerate(batch):
            with Image.open(path) as source:
                tile=source.convert('RGB');tile.thumbnail((780,525))
            x=(index%2)*800+(800-tile.width)//2;y=(index//2)*570+30
            sheet.paste(tile,(x,y));draw.text(((index%2)*800+12,(index//2)*570+6),path.stem,fill='black')
        dest=folder/f'{prefix}_{begin//6+1}.png';sheet.save(dest);saved.append(dest.name)
    return saved


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);a=p.parse_args();root=Path(a.root)
    folder=root/'validation';renders=folder/'pdf_render';renders.mkdir(parents=True,exist_ok=True)
    order=lambda path:int(re.match(r'F(\d+)',path.name).group(1))
    pdfs=sorted((root/'figures').glob('*.pdf'),key=order)
    pngs=sorted((root/'figures').glob('*.png'),key=order)
    if len(pdfs)!=17 or [p.stem for p in pdfs]!=[p.stem for p in pngs]:raise RuntimeError('Expected 17 paired figures')
    with ThreadPoolExecutor(max_workers=3) as pool:
        metadata=list(pool.map(render,[(pdf,renders/pdf.stem) for pdf in pdfs]))
    png_meta=[]
    for path in pngs:
        with Image.open(path) as im:im.verify()
        png_meta.append({'name':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    contacts=sheets([renders/(p.stem+'.png') for p in pdfs],folder,'PDF_contact')
    contacts+=sheets(pngs,folder,'PNG_contact')
    (folder/'render_QA_metadata.json').write_text(json.dumps({'pdf':metadata,'png':png_meta,'contacts':contacts,
        'status':'RENDERED_PENDING_VISUAL_INSPECTION'},indent=2),encoding='utf-8')
    print('Rendered',len(metadata),'PDFs; generated',len(contacts),'contact sheets. Manual inspection required.')


if __name__=='__main__':main()
