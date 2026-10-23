"""Set project-author properties without changing document content or image pixels."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile

AUTHOR = 'Paco'


def png_properties(author=AUTHOR):
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    info = PngInfo(); info.add_text('Author', author)
    exif = Image.Exif(); exif[315] = author
    exif[40093] = (author + chr(0)).encode('utf-16le')
    return dict(pnginfo=info, exif=exif.tobytes())


def office_xml(data, author, core, counts=None):
    from defusedxml.minidom import parseString
    doc = parseString(data)
    if core:
        doc.documentElement.setAttribute('xmlns:dc','http://purl.org/dc/elements/1.1/')
        doc.documentElement.setAttribute('xmlns:cp','http://schemas.openxmlformats.org/package/2006/metadata/core-properties')
        for ns, name, tag in (
            ('http://purl.org/dc/elements/1.1/', 'creator', 'dc:creator'),
            ('http://schemas.openxmlformats.org/package/2006/metadata/core-properties',
             'lastModifiedBy', 'cp:lastModifiedBy'),
        ):
            found = doc.getElementsByTagNameNS(ns, name)
            if found:
                element = found[0]
            else:
                element = doc.createElementNS(ns, tag); doc.documentElement.appendChild(element)
            for child in list(element.childNodes):
                element.removeChild(child)
            element.appendChild(doc.createTextNode(author))
    else:
        for name in ('Application', 'AppVersion', 'PresentationFormat'):
            for element in list(doc.getElementsByTagNameNS('*',name)):
                element.parentNode.removeChild(element)
        for name,value in (counts or {}).items():
            for element in doc.getElementsByTagNameNS('*',name):
                for child in list(element.childNodes):
                    element.removeChild(child)
                element.appendChild(doc.createTextNode(str(value)))
    return doc.toxml(encoding='utf-8')


def office_package(data, author=AUTHOR):
    from defusedxml.minidom import parseString
    source = io.BytesIO(data); output = io.BytesIO()
    with zipfile.ZipFile(source) as zin, zipfile.ZipFile(output, 'w') as zout:
        missing_core='docProps/core.xml' not in zin.namelist()
        counts=dict(Slides=sum(bool(re.fullmatch(r'ppt/slides/slide\d+\.xml',n)) for n in zin.namelist()),
                    Notes=sum(bool(re.fullmatch(r'ppt/notesSlides/notesSlide\d+\.xml',n)) for n in zin.namelist()))
        def register(payload, relationships=False):
            doc=parseString(payload)
            if relationships:
                node=doc.createElementNS(doc.documentElement.namespaceURI,'Relationship')
                node.setAttribute('Id','rIdAuthorProperties')
                node.setAttribute('Type','http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties')
                node.setAttribute('Target','docProps/core.xml')
            else:
                node=doc.createElementNS(doc.documentElement.namespaceURI,'Override')
                node.setAttribute('PartName','/docProps/core.xml')
                node.setAttribute('ContentType','application/vnd.openxmlformats-package.core-properties+xml')
            doc.documentElement.appendChild(node)
            return doc.toxml(encoding='utf-8')
        for entry in zin.infolist():
            payload = zin.read(entry.filename)
            if missing_core and entry.filename=='[Content_Types].xml':
                payload=register(payload)
            elif missing_core and entry.filename=='_rels/.rels':
                payload=register(payload,True)
            elif entry.filename=='docProps/core.xml':
                payload=office_xml(payload,author,True)
            elif entry.filename=='docProps/app.xml':
                payload=office_xml(payload,author,False,counts)
            elif entry.filename.startswith('ppt/embeddings/') and entry.filename.endswith('.xlsx'):
                payload=office_package(payload,author)
            zout.writestr(entry,payload)
        if missing_core:
            core=b'<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties"/>'
            zout.writestr('docProps/core.xml',office_xml(core,author,True))
            if '_rels/.rels' not in zin.namelist():
                rel=b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'
                zout.writestr('_rels/.rels',register(rel,True))
    return output.getvalue()


def apply(path, author=AUTHOR):
    before=path.read_bytes(); suffix=path.suffix.lower()
    if suffix in ('.pptx','.xlsx','.docx'):
        result=office_package(before,author)
    elif suffix=='.png':
        from PIL import Image
        image=Image.open(io.BytesIO(before)); pixels=image.tobytes()
        output=io.BytesIO()
        image.save(output,format='PNG',dpi=image.info.get('dpi',(300,300)),**png_properties(author))
        result=output.getvalue()
        assert Image.open(io.BytesIO(result)).tobytes()==pixels
    elif suffix=='.pdf':
        from pypdf import PdfReader, PdfWriter
        reader=PdfReader(io.BytesIO(before)); writer=PdfWriter(clone_from=reader)
        properties=dict(reader.metadata or {})
        properties.update({'/Author':author,'/Creator':'','/Producer':''})
        writer.add_metadata({k:str(v) for k,v in properties.items()})
        output=io.BytesIO(); writer.write(output); result=output.getvalue()
    elif suffix=='.svg':
        # Matplotlib's metadata block is separate from the drawing geometry.
        from xml.sax.saxutils import escape
        text=before.decode('utf-8')
        creator='<dc:creator><cc:Agent><dc:title>'+escape(author)+'</dc:title></cc:Agent></dc:creator>'
        if '<dc:creator>' in text:
            text=re.sub(r'<dc:creator>.*?</dc:creator>',creator,text,flags=re.S)
        else:
            raise ValueError(f'No supported SVG creator metadata: {path}')
        result=('\n'.join(line.rstrip() for line in text.splitlines())+'\n').encode('utf-8')
    else:
        raise ValueError(f'No standard author property supported: {path}')
    if result!=before:
        path.write_bytes(result)
    return dict(file=path.as_posix(),author=author,changed=result!=before,
                sha256=hashlib.sha256(result).hexdigest())


def inspect(path, author=AUTHOR):
    suffix=path.suffix.lower()
    if suffix in ('.pptx','.xlsx','.docx'):
        from defusedxml.minidom import parseString
        with zipfile.ZipFile(path) as z:
            d=parseString(z.read('docProps/core.xml'))
            for ns,name in [('http://purl.org/dc/elements/1.1/','creator'),
                            ('http://schemas.openxmlformats.org/package/2006/metadata/core-properties','lastModifiedBy')]:
                assert d.getElementsByTagNameNS(ns,name)[0].firstChild.data==author
            app=z.read('docProps/app.xml').decode() if 'docProps/app.xml' in z.namelist() else ''
            assert 'Artifact' not in app and 'OpenAI' not in app and 'Walnut' not in app
            if app:
                assert not parseString(app).getElementsByTagNameNS('*','Application')
            for name in z.namelist():
                if name.startswith('ppt/embeddings/') and name.endswith('.xlsx'):
                    with zipfile.ZipFile(io.BytesIO(z.read(name))) as book:
                        d=parseString(book.read('docProps/core.xml'))
                        assert d.getElementsByTagNameNS('http://purl.org/dc/elements/1.1/','creator')[0].firstChild.data==author
    elif suffix=='.png':
        from PIL import Image
        im=Image.open(path)
        assert im.info.get('Author')==author and im.getexif().get(315)==author
        assert im.getexif().get(40093).decode('utf-16le').rstrip(chr(0))==author
        assert not im.info.get('Software')
    elif suffix=='.pdf':
        from pypdf import PdfReader
        meta=PdfReader(path).metadata
        assert meta.author==author and not meta.creator and not meta.producer
    elif suffix=='.svg':
        from defusedxml import ElementTree
        root=ElementTree.parse(path).getroot()
        creator=root.find('.//{http://purl.org/dc/elements/1.1/}creator')
        assert creator is not None and author in ''.join(creator.itertext())


def main():
    p=argparse.ArgumentParser()
    p.add_argument('paths',nargs='*',type=Path)
    p.add_argument('--author',default=AUTHOR)
    p.add_argument('--check',action='store_true')
    p.add_argument('--report',type=Path)
    args=p.parse_args()
    paths=args.paths or [*Path('figures').rglob('*.svg'),*Path('figures').rglob('*.png'),
                        *Path('figures').rglob('*.pdf'),
                        *Path('results/qa').glob('figures-*.png')]
    rows=[]
    for path in sorted(paths):
        if not args.check:
            rows.append(apply(path,args.author))
        inspect(path,args.author)
        if args.check:
            rows.append(dict(file=path.as_posix(),author=args.author,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    if args.report:
        args.report.write_text(json.dumps(dict(author=args.author,checked=len(paths),
            scope='Project-authored exports; source-file authorship is recorded in Git',files=rows),indent=2)+chr(10))
    print(f'PASS: {len(paths)} supported files have author {args.author}; image pixels and document data preserved.')


if __name__=='__main__':
    main()
