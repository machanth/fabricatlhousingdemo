"""Render the manual locally; no cloud writes, document uploads or lab deployment."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET
import zipfile

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
import markdown
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
OUT = DOCS / "downloads"
STEM = "ATL-Housing-Workshop-Manual"
REPOSITORY = "https://github.com/machanth/fabricatlhousingdemo/blob/machanth-atl-housing-fabric-build/docs/"
CSS = """
@page {size:A4}
* {box-sizing:border-box}
body {font:14px/1.45 "Segoe UI",Arial,sans-serif;color:#243746;margin:0}
h1 {font-size:40px;color:#007f79;margin:24mm 0 8mm;line-height:1.15}
h2 {font-size:25px;color:#133b55;margin:9mm 0 4mm;line-height:1.25}
h2[id^="m1"],h2[id^="m2"],h2[id^="m3"],h2[id^="m4"],h2[id^="m5"],
h2[id^="m6"],h2[id^="m7"],h2[id^="m8"],h2[id^="m9"],
h2[id^="final-attendee"],h2[id^="troubleshooting"],h2[id^="asset-index"]
{break-before:page}
h3 {font-size:18px;color:#007f79;margin:6mm 0 3mm}
h1,h2,h3 {break-after:avoid}
p {margin:2.5mm 0;orphans:3;widows:3}
li {padding-left:1mm;margin:1.5mm 0;break-inside:avoid}
ol,ul {padding-left:6mm}
table {border-collapse:collapse;table-layout:fixed;width:100%;margin:4mm 0;font-size:12px}
th,td {border:1px solid #c8d7dc;text-align:left;vertical-align:top;padding:2mm;overflow-wrap:anywhere}
th {background:#007f79;color:white;font-weight:600}
tr {break-inside:avoid}
thead {display:table-header-group}
a {color:#007f79;text-decoration:underline;overflow-wrap:anywhere}
code {font:11.5px Consolas,monospace;background:#eef3f6;overflow-wrap:anywhere}
pre {background:#eef3f6;border-left:3px solid #007f79;padding:3mm;
     white-space:pre-wrap;overflow-wrap:anywhere;break-inside:avoid}
pre code {background:none}
blockquote {border-left:4px solid #d88a00;background:#fff7e6;padding:2mm 4mm;margin:5mm 0}
figure {margin:5mm 0;break-inside:avoid}
figure img {display:block;max-height:155mm;max-width:100%;height:auto;
            object-fit:contain;object-position:left;border:1px solid #c8d7dc}
figcaption {font-size:11.5px;color:#526b78;margin-top:2mm}
.cover {min-height:230mm;break-after:page}
.contents {break-after:page}
.contents li {margin:2mm 0}
@media screen {body {max-width:900px;margin:25px auto;padding:24px}}
"""


def parse_manual():
    source = (DOCS / "workshop-attendee-guide.md").read_text(encoding="utf-8")
    html = markdown.markdown(source, extensions=["tables", "fenced_code", "sane_lists", "toc"],
                             output_format="xhtml")
    tree = ET.fromstring("<div>" + html + "</div>")
    children = list(tree)
    for index, node in enumerate(children):
        image = node.find("img") if node.tag == "p" else None
        if image is None:
            continue
        figure = ET.Element("figure")
        figure.append(deepcopy(image))
        following = children[index + 1] if index + 1 < len(children) else None
        if following is not None and following.tag == "p" and following.find("em") is not None:
            caption = ET.SubElement(figure, "figcaption")
            caption.text = "".join(following.itertext())
            tree.remove(following)
        position = list(tree).index(node)
        tree.remove(node)
        tree.insert(position, figure)
    for node in tree.iter():
        target = node.get("src") if node.tag == "img" else node.get("href") if node.tag == "a" else None
        if target and not re.match(r"^(https?:|#)", target):
            path = DOCS.joinpath(*target.split("/"))
            if not path.is_file():
                raise FileNotFoundError(f"Broken manual link: {target}")
    return tree


def section_parts(tree):
    nodes = list(tree)
    split = next(i for i, n in enumerate(nodes)
                 if n.tag == "h2" and "".join(n.itertext()) == "How to use this workbook")
    return nodes[:split], nodes[split:]


def html_document(tree, *, assets_prefix="", repository_links=False):
    tree = deepcopy(tree)
    for node in tree.iter():
        if node.tag == "img":
            node.set("src", assets_prefix + node.get("src"))
        elif node.tag == "a":
            href = node.get("href", "")
            if href and not re.match(r"^(https?:|#)", href):
                node.set("href", (REPOSITORY if repository_links else assets_prefix) + href)
    cover, body = section_parts(tree)
    contents = "".join(
        f'<li><a href="#{n.get("id")}">{"".join(n.itertext())}</a></li>'
        for n in body if n.tag == "h2")
    serialize = lambda nodes: "".join(ET.tostring(n, encoding="unicode", method="html") for n in nodes)
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{STEM}</title><style>{CSS}</style></head><body>"
            f'<section class="cover">{serialize(cover)}</section>'
            f'<nav class="contents"><h2>Module index</h2><ol>{contents}</ol></nav>'
            f"{serialize(body)}</body></html>")


def append_bookmark(paragraph, name, ident):
    start = OxmlElement("w:bookmarkStart")
    start.set(qn("w:id"), str(ident))
    start.set(qn("w:name"), bookmark_name(name))
    end = OxmlElement("w:bookmarkEnd")
    end.set(qn("w:id"), str(ident))
    paragraph._p.insert(0, start)
    paragraph._p.append(end)


def bookmark_name(name):
    return re.sub(r"[^A-Za-z0-9_]", "_", name)[:40]


def hyperlink(paragraph, text, target):
    link = OxmlElement("w:hyperlink")
    if target.startswith("#"):
        link.set(qn("w:anchor"), bookmark_name(target[1:]))
    else:
        from docx.opc.constants import RELATIONSHIP_TYPE
        relation = paragraph.part.relate_to(target, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
        link.set(qn("r:id"), relation)
    run = OxmlElement("w:r")
    properties = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "007F79")
    properties.append(color)
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    properties.append(underline)
    run.append(properties)
    content = OxmlElement("w:t")
    content.text = text
    run.append(content)
    link.append(run)
    paragraph._p.append(link)


def inline(paragraph, node, *, bold=False, italic=False, code=False):
    def text_run(text):
        if text:
            run = paragraph.add_run(text)
            run.bold, run.italic = bold, italic
            if code:
                run.font.name = "Consolas"
                run.font.size = Pt(9)
    text_run(node.text)
    for child in node:
        if child.tag == "a":
            target = child.get("href", "")
            if target and not re.match(r"^(https?:|#)", target):
                target = REPOSITORY + target
            hyperlink(paragraph, "".join(child.itertext()), target)
        elif child.tag == "br":
            paragraph.add_run().add_break()
        else:
            inline(paragraph, child, bold=bold or child.tag == "strong",
                   italic=italic or child.tag == "em", code=code or child.tag == "code")
        text_run(child.tail)


def numbered_list_id(document, start):
    numbering = document.part.numbering_part.element
    existing = [int(n.get(qn("w:abstractNumId"))) for n in numbering.findall(qn("w:abstractNum"))]
    abstract_id = max(existing, default=-1) + 1
    abstract = OxmlElement("w:abstractNum")
    abstract.set(qn("w:abstractNumId"), str(abstract_id))
    level = OxmlElement("w:lvl")
    level.set(qn("w:ilvl"), "0")
    for tag, value in (("start", "1"), ("numFmt", "decimal"), ("lvlText", "%1.")):
        element = OxmlElement("w:" + tag)
        element.set(qn("w:val"), value)
        level.append(element)
    props = OxmlElement("w:pPr")
    indent = OxmlElement("w:ind")
    indent.set(qn("w:left"), "360")
    indent.set(qn("w:hanging"), "360")
    props.append(indent)
    level.append(props)
    abstract.append(level)
    first_num = next((i for i, child in enumerate(numbering) if child.tag == qn("w:num")),
                     len(numbering))
    numbering.insert(first_num, abstract)
    num = numbering.add_num(abstract_id)
    num.add_lvlOverride(0).add_startOverride(start)
    return num.numId


def build_word(tree):
    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Inches(8.27), Inches(11.69)
    section.top_margin, section.bottom_margin = Inches(.7), Inches(.65)
    section.left_margin = section.right_margin = Inches(.65)
    section.header.paragraphs[0].text = "ATL HOUSING  |  MANUAL FABRIC WORKSHOP"
    section.header.paragraphs[0].style = document.styles["Caption"]
    footer = section.footer.paragraphs[0]
    footer.add_run("Attendee workbook  |  November 2026                                      ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    normal = document.styles["Normal"]
    normal.font.name, normal.font.size = "Calibri", Pt(10)
    normal.paragraph_format.space_after = Pt(6)
    for name in ("Heading 1", "Heading 2", "Heading 3"):
        document.styles[name].font.color.rgb = RGBColor.from_string("007F79")
    document.styles["Caption"].font.size = Pt(9)
    document.core_properties.title = "ATL Housing: manual Fabric workshop"
    document.core_properties.subject = "Click-by-click attendee workbook with original UI screenshots"

    def block(node):
        if node.tag in ("h1", "h2", "h3"):
            level = int(node.tag[1])
            heading = document.add_heading("".join(node.itertext()), level=level)
            if level == 1:
                heading.runs[0].font.size = Pt(28)
            ident = node.get("id")
            if ident:
                append_bookmark(heading, ident, len(document.paragraphs))
            if node.tag == "h2" and re.match(r"^(M\d+\.|Final attendee|Troubleshooting|Asset index)",
                                            heading.text):
                heading.paragraph_format.page_break_before = True
        elif node.tag == "p":
            inline(document.add_paragraph(), node)
        elif node.tag in ("ol", "ul"):
            list_id = numbered_list_id(document, int(node.get("start", "1"))) if node.tag == "ol" else None
            for item in node:
                paragraph = document.add_paragraph(style="List Paragraph" if list_id else "List Bullet")
                if list_id:
                    props = paragraph._p.get_or_add_pPr()
                    number = OxmlElement("w:numPr")
                    level = OxmlElement("w:ilvl")
                    level.set(qn("w:val"), "0")
                    num = OxmlElement("w:numId")
                    num.set(qn("w:val"), str(list_id))
                    number.extend([level, num])
                    props.append(number)
                inline(paragraph, item)
        elif node.tag == "table":
            rows = node.findall(".//tr")
            table = document.add_table(rows=0, cols=len(rows[0]))
            table.style = "Light Shading Accent 1"
            for index, row in enumerate(rows):
                cells = table.add_row().cells
                for cell, value in zip(cells, row):
                    paragraph = cell.paragraphs[0]
                    inline(paragraph, value, bold=index == 0)
                    for run in paragraph.runs:
                        run.font.size = Pt(9.5)
                if index == 0:
                    repeat = OxmlElement("w:tblHeader")
                    table.rows[-1]._tr.get_or_add_trPr().append(repeat)
            document.add_paragraph()
        elif node.tag == "pre":
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.keep_together = True
            run = paragraph.add_run("".join(node.itertext()))
            run.font.name, run.font.size = "Consolas", Pt(8.5)
        elif node.tag == "blockquote":
            for child in node:
                paragraph = document.add_paragraph(style="Intense Quote")
                inline(paragraph, child)
        elif node.tag == "figure":
            image = node.find("img")
            path = DOCS.joinpath(*image.get("src").split("/"))
            width, height = struct.unpack(">II", path.read_bytes()[16:24])
            scale = min(6.7 / width, 4.9 / height)
            paragraph = document.add_paragraph()
            paragraph.paragraph_format.keep_with_next = True
            paragraph.add_run().add_picture(str(path), width=Inches(width * scale))
            caption = node.find("figcaption")
            if caption is not None:
                document.add_paragraph("".join(caption.itertext()), style="Caption")
        else:
            raise RuntimeError(f"Unsupported Markdown output element: {node.tag}")

    cover, body = section_parts(tree)
    for node in cover:
        block(node)
    document.add_page_break()
    document.add_heading("Module index", level=1)
    for node in body:
        if node.tag == "h2":
            hyperlink(document.add_paragraph(), "".join(node.itertext()), "#" + node.get("id"))
    document.add_page_break()
    for node in body:
        block(node)
    document.save(OUT / (STEM + ".docx"))


def build_pdf(tree):
    print_html = OUT / ".workshop-print.html"
    print_html.write_text(html_document(tree, assets_prefix="../", repository_links=True), encoding="utf-8")
    try:
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(channel="msedge", headless=True)
            try:
                page = browser.new_page()
                page.goto(print_html.as_uri(), wait_until="networkidle")
                page.evaluate("document.fonts.ready")
                if page.locator("img").evaluate_all(
                    "(images) => images.some(i => !i.complete || i.naturalWidth === 0)"
                ):
                    raise RuntimeError("A screenshot did not load for PDF printing.")
                page.pdf(
                    path=str(OUT / (STEM + ".pdf")), format="A4", print_background=True,
                    margin={"top": "16mm", "bottom": "18mm", "left": "14mm", "right": "14mm"},
                    display_header_footer=True, header_template="<div></div>",
                    footer_template='<div style="font:8px Arial;width:100%;text-align:center;'
                                    'color:#526b78">ATL Housing | Manual workshop | '
                                    '<span class="pageNumber"></span> / '
                                    '<span class="totalPages"></span></div>')
            finally:
                browser.close()
    finally:
        print_html.unlink(missing_ok=True)


def build_bundle(tree, source_data):
    files = {}
    for extension in ("docx", "pdf"):
        path = OUT / (STEM + "." + extension)
        files[path.name] = path.read_bytes()
    files["workshop-attendee-guide.md"] = (DOCS / "workshop-attendee-guide.md").read_bytes()
    files["workshop-attendee-guide.html"] = html_document(tree).encode()
    for path in (DOCS / "workshop-assets").rglob("*"):
        if path.is_file():
            files[path.relative_to(DOCS).as_posix()] = path.read_bytes()
    for image in tree.iter("img"):
        name = image.get("src")
        files[name] = DOCS.joinpath(*name.split("/")).read_bytes()
    expected = {f"{kind}_{month}.xlsx" for kind in ("UnitAvailability", "SupportiveHousing")
                for month in range(202501, 202513)}
    workbooks = list((source_data / "excel").glob("*.xlsx"))
    if {p.name for p in workbooks} != expected:
        raise RuntimeError("Distribution requires exactly the 24 approved original workbooks.")
    for path in workbooks:
        if not zipfile.is_zipfile(path):
            raise RuntimeError(f"Original is not readable OOXML: {path.name}")
        files["data/excel/" + path.name] = path.read_bytes()
    for name in ("answer_key.csv", "dq_manifest.csv", "row_counts.csv", "run_manifest.json"):
        files["data/controls/" + name] = (source_data / name).read_bytes()
    manifest = {name: {"bytes": len(data), "sha256": sha256(data).hexdigest()}
                for name, data in sorted(files.items())}
    files["pack-manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    delivery = ROOT / ".state" / "workshop-delivery"
    delivery.mkdir(parents=True, exist_ok=True)
    path = delivery / "ATL-Housing-Manual-Workshop-Pack.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as bundle:
        for name, data in files.items():
            bundle.writestr(name, data)
    print(f"Private offline pack: {path} ({len(files)} entries, original Excel bytes unchanged)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-data", type=Path,
                        help="Optional approved original out folder; enables private offline ZIP packaging.")
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    tree = parse_manual()
    build_word(tree)
    build_pdf(tree)
    (OUT / "workshop-attendee-guide.html").write_text(
        html_document(tree, assets_prefix="../"), encoding="utf-8")
    if args.source_data:
        build_bundle(tree, args.source_data)
    print("Created Word, PDF and local HTML. No Fabric items were created or changed.")


if __name__ == "__main__":
    main()
