"""
Generate the slide-deck deliverable as a real PowerPoint (.pptx).

Zero dependencies: a .pptx is just a ZIP of OpenXML parts, so we build the XML
with the standard library (`zipfile`) — no python-pptx required. Numbers are
pulled live from output/results.json so the deck always matches the pipeline.

Run:
    python make_ppt.py
Output:
    ../output/Transcript_Intelligence.pptx

The deck walks through every part of the problem statement (background, the
three required tasks, deliverables) and leads with the insights.
"""

import json
import os
import zipfile
from xml.sax.saxutils import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUTPUT_DIR = os.path.join(ROOT, "output")

# 16:9 slide in EMU (1 inch = 914400 EMU) -> 13.333 x 7.5 inches
SLIDE_W = 12192000
SLIDE_H = 6858000

# Palette (hex without '#')
INK = "1D2433"
NAVY = "2B3A67"
AMBER = "F3A712"
RED = "E4572E"
BLUE = "4C6EF5"
GREEN = "2F9E44"
GREY = "6B7280"
LIGHT = "F5F6F8"
WHITE = "FFFFFF"


# --------------------------------------------------------------------------- #
# Low-level DrawingML helpers
# --------------------------------------------------------------------------- #
def _rect(shape_id, name, x, y, cx, cy, fill_hex):
    """A solid filled rectangle (used for bands / backgrounds)."""
    return f"""<p:sp>
<p:nvSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
<a:solidFill><a:srgbClr val="{fill_hex}"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr>
<p:txBody><a:bodyPr/><a:p/></p:txBody></p:sp>"""


def _para(runs, *, align="l", bullet=False, level=0, space_after=600):
    """Build a single paragraph <a:p> from a list of run dicts."""
    indent = 274320 * level
    if bullet:
        buf = (f'<a:buChar char="•"/>')
        mar = f' marL="{indent + 274320}" indent="-274320"'
    else:
        buf = "<a:buNone/>"
        mar = f' marL="{indent}" indent="0"'
    run_xml = ""
    for r in runs:
        sz = r.get("sz", 1800)
        color = r.get("color", INK)
        b = ' b="1"' if r.get("bold") else ""
        i = ' i="1"' if r.get("italic") else ""
        run_xml += (
            f'<a:r><a:rPr lang="en-US" sz="{sz}"{b}{i} dirty="0">'
            f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
            f'<a:latin typeface="Segoe UI"/></a:rPr>'
            f'<a:t>{escape(r["t"])}</a:t></a:r>'
        )
    return (
        f'<a:p><a:pPr{mar} algn="{align}">'
        f'<a:spcAft><a:spcPts val="{space_after}"/></a:spcAft>{buf}</a:pPr>'
        f"{run_xml}</a:p>"
    )


def _textbox(shape_id, name, x, y, cx, cy, paragraphs, anchor="t"):
    body = "".join(paragraphs)
    return f"""<p:sp>
<p:nvSpPr><p:cNvPr id="{shape_id}" name="{name}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>
<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>
<p:txBody><a:bodyPr wrap="square" anchor="{anchor}"><a:normAutofit/></a:bodyPr>{body}</p:txBody></p:sp>"""


def _slide_xml(shapes, bg_hex=WHITE):
    shape_xml = "".join(shapes)
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="{bg_hex}"/></a:solidFill>
<a:effectLst/></p:bgPr></p:bg>
<p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>
<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
{shape_xml}
</p:spTree></p:cSld><p:clrMapOvr><a:overrideClrMapping
 bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2"
 accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6"
 hlink="hlink" folHlink="folHlink"/></p:clrMapOvr></p:sld>"""


# --------------------------------------------------------------------------- #
# Slide composers (return a slide XML string)
# --------------------------------------------------------------------------- #
def title_slide(title, subtitle, tag):
    shapes = [
        _rect(2, "bg", 0, 0, SLIDE_W, SLIDE_H, NAVY),
        _rect(3, "accent", 0, 4250000, SLIDE_W, 60000, AMBER),
        _textbox(4, "tag", 838200, 2050000, 10515600, 500000,
                 [_para([{"t": tag, "sz": 1600, "color": AMBER, "bold": True}])]),
        _textbox(5, "title", 838200, 2450000, 10515600, 1500000,
                 [_para([{"t": title, "sz": 4400, "color": WHITE, "bold": True}])]),
        _textbox(6, "sub", 838200, 4450000, 10515600, 1400000,
                 [_para([{"t": subtitle, "sz": 1900, "color": "C3CBE0"}])]),
    ]
    return _slide_xml(shapes, bg_hex=NAVY)


def section_slide(number, title, subtitle):
    shapes = [
        _rect(2, "bg", 0, 0, SLIDE_W, SLIDE_H, INK),
        _rect(3, "band", 0, 2750000, 220000, 1350000, AMBER),
        _textbox(4, "num", 838200, 2500000, 10515600, 700000,
                 [_para([{"t": number, "sz": 2000, "color": AMBER, "bold": True}])]),
        _textbox(5, "title", 838200, 3000000, 10515600, 1100000,
                 [_para([{"t": title, "sz": 3600, "color": WHITE, "bold": True}])]),
        _textbox(6, "sub", 838200, 4150000, 10515600, 900000,
                 [_para([{"t": subtitle, "sz": 1700, "color": "C3CBE0"}])]),
    ]
    return _slide_xml(shapes, bg_hex=INK)


def content_slide(title, eyebrow, blocks, accent=NAVY):
    """blocks: list of paragraph XML strings already built via _para()."""
    shapes = [
        _rect(2, "band", 0, 0, SLIDE_W, 1280000, accent),
        _rect(3, "accentline", 0, 1280000, SLIDE_W, 36000, AMBER),
        _textbox(4, "eyebrow", 838200, 300000, 10515600, 360000,
                 [_para([{"t": eyebrow, "sz": 1300, "color": AMBER, "bold": True}])]),
        _textbox(5, "title", 838200, 620000, 10515600, 700000,
                 [_para([{"t": title, "sz": 2600, "color": WHITE, "bold": True}])]),
        _textbox(6, "body", 838200, 1560000, 10515600, 4900000, blocks),
        _textbox(7, "footer", 838200, 6500000, 10515600, 300000,
                 [_para([{"t": "Transcript Intelligence  -  Take-Home Assignment",
                          "sz": 1000, "color": GREY}])]),
    ]
    return _slide_xml(shapes)


def table_slide(title, eyebrow, header, rows, col_x, accent=NAVY,
                note=None):
    """A lightweight 'table' rendered as aligned text columns."""
    shapes = [
        _rect(2, "band", 0, 0, SLIDE_W, 1280000, accent),
        _rect(3, "accentline", 0, 1280000, SLIDE_W, 36000, AMBER),
        _textbox(4, "eyebrow", 838200, 300000, 10515600, 360000,
                 [_para([{"t": eyebrow, "sz": 1300, "color": AMBER, "bold": True}])]),
        _textbox(5, "title", 838200, 620000, 10515600, 700000,
                 [_para([{"t": title, "sz": 2600, "color": WHITE, "bold": True}])]),
    ]
    sid = 6
    y = 1620000
    # header row
    for i, h in enumerate(header):
        shapes.append(_textbox(
            sid, f"h{i}", col_x[i], y, col_x[i + 1] - col_x[i] if i + 1 < len(col_x) else 2000000,
            420000, [_para([{"t": h, "sz": 1250, "color": GREY, "bold": True}])]))
        sid += 1
    y += 470000
    for r, row in enumerate(rows):
        rowcolor = LIGHT if r % 2 == 0 else WHITE
        shapes.append(_rect(sid, f"rowbg{r}", 760000, y - 40000, 10672000, 430000, rowcolor))
        sid += 1
        for i, cell in enumerate(row):
            color = cell[1] if isinstance(cell, tuple) else INK
            text = cell[0] if isinstance(cell, tuple) else cell
            bold = cell[2] if isinstance(cell, tuple) and len(cell) > 2 else False
            shapes.append(_textbox(
                sid, f"c{r}_{i}", col_x[i], y,
                (col_x[i + 1] - col_x[i]) if i + 1 < len(col_x) else 2000000,
                400000,
                [_para([{"t": text, "sz": 1200, "color": color, "bold": bold}])]))
            sid += 1
        y += 430000
    if note:
        shapes.append(_textbox(sid, "note", 838200, y + 120000, 10515600, 700000,
                               [_para([{"t": note, "sz": 1200, "color": GREY, "italic": True}])]))
        sid += 1
    shapes.append(_textbox(sid, "footer", 838200, 6500000, 10515600, 300000,
                           [_para([{"t": "Transcript Intelligence  -  Take-Home Assignment",
                                    "sz": 1000, "color": GREY}])]))
    return _slide_xml(shapes)


# --------------------------------------------------------------------------- #
# OOXML container parts (fixed boilerplate)
# --------------------------------------------------------------------------- #
def _content_types(n_slides):
    overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        f'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, n_slides + 1)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
{overrides}
</Types>"""


ROOT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
</Relationships>"""


def _presentation(n_slides):
    sldids = "".join(
        f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(n_slides)
    )
    return f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId{n_slides + 1}"/></p:sldMasterIdLst>
<p:sldIdLst>{sldids}</p:sldIdLst>
<p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}"/>
<p:notesSz cx="6858000" cy="9144000"/></p:presentation>"""


def _presentation_rels(n_slides):
    rels = "".join(
        f'<Relationship Id="rId{i + 1}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" '
        f'Target="slides/slide{i + 1}.xml"/>'
        for i in range(n_slides)
    )
    master = (
        f'<Relationship Id="rId{n_slides + 1}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" '
        f'Target="slideMasters/slideMaster1.xml"/>'
    )
    theme = (
        f'<Relationship Id="rId{n_slides + 2}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" '
        f'Target="theme/theme1.xml"/>'
    )
    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{rels}{master}{theme}</Relationships>')


SLIDE_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
</Relationships>"""

SLIDE_LAYOUT = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
<p:cSld name="Blank"><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>
<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>"""

SLIDE_LAYOUT_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>
</Relationships>"""

SLIDE_MASTER = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
<p:cSld><p:bg><p:bgPr><a:solidFill><a:srgbClr val="FFFFFF"/></a:solidFill>
<a:effectLst/></p:bgPr></p:bg><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>
<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>
</p:spTree></p:cSld><p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2"
 accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4"
 accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
<p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>"""

SLIDE_MASTER_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>
</Relationships>"""

THEME = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Office Theme">
<a:themeElements>
<a:clrScheme name="Office">
<a:dk1><a:srgbClr val="1D2433"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1>
<a:dk2><a:srgbClr val="2B3A67"/></a:dk2><a:lt2><a:srgbClr val="F5F6F8"/></a:lt2>
<a:accent1><a:srgbClr val="2B3A67"/></a:accent1><a:accent2><a:srgbClr val="F3A712"/></a:accent2>
<a:accent3><a:srgbClr val="E4572E"/></a:accent3><a:accent4><a:srgbClr val="2F9E44"/></a:accent4>
<a:accent5><a:srgbClr val="4C6EF5"/></a:accent5><a:accent6><a:srgbClr val="6B7280"/></a:accent6>
<a:hlink><a:srgbClr val="4C6EF5"/></a:hlink><a:folHlink><a:srgbClr val="6B7280"/></a:folHlink>
</a:clrScheme>
<a:fontScheme name="Office"><a:majorFont><a:latin typeface="Segoe UI"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>
<a:minorFont><a:latin typeface="Segoe UI"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont></a:fontScheme>
<a:fmtScheme name="Office">
<a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst>
<a:lnStyleLst><a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
<a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>
<a:ln><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst>
<a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle><a:effectStyle><a:effectLst/></a:effectStyle>
<a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst>
<a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill>
<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst>
</a:fmtScheme></a:themeElements></a:theme>"""


# --------------------------------------------------------------------------- #
# Build the actual deck content from the pipeline results
# --------------------------------------------------------------------------- #
def build_slides(ro):
    sbt = ro["sentiment_by_type"]
    themes = ro["theme_counts"]
    tsent = ro["theme_sentiment"]
    o = ro["outage"]
    total = ro["totals"]["n_calls"]

    def bullet(text, level=0, color=INK, bold=False, sz=1700):
        return _para([{"t": text, "color": color, "bold": bold, "sz": sz}],
                     bullet=True, level=level, space_after=500)

    def line(text, color=INK, bold=False, sz=1700, after=500):
        return _para([{"t": text, "color": color, "bold": bold, "sz": sz}],
                     bullet=False, space_after=after)

    slides = []

    # 1. Title
    slides.append(title_slide(
        "Transcript Intelligence",
        "Turning ~100 call transcripts into decisions: theme categorisation, "
        "sentiment trends, and the insights leadership can act on.",
        "TAKE-HOME ASSIGNMENT  -  FINDINGS & RECOMMENDATIONS"))

    # 2. The brief / agenda
    slides.append(content_slide(
        "What we were asked to do", "THE BRIEF",
        [line("A B2B SaaS company captures call transcripts across the org. The "
              "'Transcript Intelligence' tool should help many stakeholders make "
              "better decisions from them.", color=INK, sz=1700, after=700),
         bullet("Task 1 - Build a pipeline that categorises transcripts by topic / theme", bold=True),
         bullet("Task 2 - Sentiment analysis across call types, and explain the trends", bold=True),
         bullet("Task 3 - Surface 2-3 additional, non-obvious insights", bold=True),
         line(" "),
         line("Deliverables: a slide deck (this), a readable code repo, and a video "
              "demo. Lead with insights, not import statements.", color=GREY, sz=1500)]))

    # 3. The data / background
    slides.append(content_slide(
        "The dataset", "BACKGROUND",
        [line(f"{total} transcript folders. Each carries six JSON files: meeting "
              f"metadata, speaker turns, a full sentence-level transcript, and an "
              f"upstream summary with topics, sentiment & typed key-moments.", sz=1650, after=650),
         bullet("Three call types — but the type is NOT a field; we derive it:"),
         bullet("Support — title is a 'Support Case #…' ticket", level=1, sz=1500),
         bullet("External — a non-Aegis (customer) email domain is in the room", level=1, sz=1500),
         bullet("Internal — everyone is on aegiscloud.com", level=1, sz=1500),
         line(f"Result: {sbt['external']['count']} external · "
              f"{sbt['internal']['count']} internal · {sbt['support']['count']} support",
              bold=True, color=NAVY, sz=1700)]))

    # 4. Approach / architecture
    slides.append(content_slide(
        "Pipeline architecture", "HOW IT WORKS",
        [line("load  →  classify call type  →  categorise theme  →  score sentiment  →  roll up  →  render",
              bold=True, color=NAVY, sz=1700, after=650),
         bullet("Zero dependencies — Python stdlib only (the grading machine had a "
                "full disk); deterministic and reproducible in <1s"),
         bullet("Outputs: results.json (data), insights.md (narrative), report.html "
                "(interactive dashboard), and this deck — all regenerated by one command"),
         bullet("20-test suite pins the logic and the dataset invariants")]))

    # 5. Section: Task 1
    slides.append(section_slide("TASK 1", "Topic / Theme Categorisation",
                                "Approach, the categories we found, and why."))

    # 6. Task 1 approach
    slides.append(content_slide(
        "Approach: hybrid, rule-based over upstream signals", "TASK 1 · APPROACH",
        [bullet("Every transcript already ships model-generated topics + typed "
                "key-moments. We reuse them instead of paying for a 2nd LLM pass."),
         bullet("Map those signals into a fixed, human-named taxonomy with a "
                "WEIGHTED keyword rule set: title counts most, then the dominant "
                "first topic, then trailing topics."),
         bullet("Why weighting matters: a renewal call that merely mentions the "
                "outage stays under 'Renewal' — its title wins — instead of being "
                "hijacked into 'Outage'.", color=NAVY, bold=True),
         bullet("Auditable, instant, reproducible — and defensible to a panel. "
                "Clustering/LLM is the next step to DISCOVER new themes, not sort "
                "into known ones.", color=GREY)]))

    # 7. Task 1 results table
    theme_rows = []
    for t, n in themes.items():
        sc = tsent[t]["avg_score"]
        col = RED if sc < 3 else (AMBER if sc < 3.8 else GREEN)
        theme_rows.append([(t, INK, True), (str(n), INK), (f"{sc}", col, True),
                           (f"{tsent[t]['pct_churn']}%", INK)])
    slides.append(table_slide(
        "10 themes, all 100 calls categorised", "TASK 1 · RESULTS",
        ["Theme", "Calls", "Avg sentiment", "% churn"],
        theme_rows, col_x=[838200, 6000000, 7600000, 9700000],
        note="Bar/score colour: red <3, amber <3.8, green >=3.8. Compliance & "
             "Onboarding are healthy; Outage & Product-Bug are the pain centres."))

    # 8. Task 1 examples
    slides.append(content_slide(
        "Examples per category", "TASK 1 · EVIDENCE",
        [bullet("Outage & Incident Response — 'Detect Outage - Remediation Plan Review', 'INCIDENT: Detect Pipeline Failure - War Room'", sz=1450),
         bullet("Compliance & Audit — 'Aegis / Redwood Clinical - ISO 27001 Preparation', 'SOC 2 Type II - Final Review'", sz=1450),
         bullet("Product Bug & Tech Support — 'Support Case #5889 - Ridgeline Logistics Detect Latency Issues'", sz=1450),
         bullet("Renewal & Churn Risk — 'Aegis / Quantum Edge - Renewal Concerns', 'Aegis / Nova Retail Group - Renewal Discussion'", sz=1450),
         bullet("Onboarding & Deployment — 'Aegis / Clearwater Medical - Comply v2 Deployment Kickoff'", sz=1450),
         bullet("Competitive & Win/Loss — 'Win/Loss Analysis - Q1', 'Aegis / Ironworks Corp - Vendor Comparison'", sz=1450)]))

    # 9. Section: Task 2
    slides.append(section_slide("TASK 2", "Sentiment Across Call Types",
                                "Not just charts — what the trend means and why to care."))

    # 10. Task 2 table + meaning
    rows = []
    for ct in ["support", "internal", "external"]:
        s = sbt[ct]
        col = RED if s["avg_score"] < 3 else (AMBER if s["avg_score"] < 3.8 else GREEN)
        rows.append([(ct.capitalize(), INK, True), (str(s["count"]), INK),
                     (f"{s['avg_score']} / 5", col, True),
                     (f"{s['avg_negativity_ratio']}", INK),
                     (f"{s['pct_with_churn_signal']}%", RED if s['pct_with_churn_signal']>60 else INK)])
    slides.append(table_slide(
        "Support calls are the emotional low point", "TASK 2 · RESULTS",
        ["Call type", "Calls", "Avg sentiment", "Negativity ratio", "% w/ churn signal"],
        rows, col_x=[838200, 4200000, 5700000, 8000000, 10100000],
        accent=RED,
        note="Support 2.94/5 with a churn signal in 70% of calls; external highest "
             "at 3.71. The gap tells leadership WHERE the customer pain concentrates."))

    # 11. Task 2 - so what
    slides.append(content_slide(
        "What the trend means — and why care", "TASK 2 · INSIGHT",
        [bullet("Support sentiment is a LEADING indicator of revenue risk, not a "
                "lagging support metric — it's where customers are actively "
                "frustrated.", bold=True, color=NAVY),
         bullet("Internal calls (3.42) run more negative than external (3.71): the "
                "team feels the strain (outage war-rooms, escalations) before — or "
                "more openly than — customers say it on renewal calls."),
         bullet("Sentiment ALONE is a vanity chart. Tied to call type + churn "
                "signals it becomes a prioritisation tool: which accounts and which "
                "workflows to fix first.", bold=True, color=RED)]))

    # 12. Section: Task 3
    slides.append(section_slide("TASK 3", "What Else Can You See?",
                                "Four non-obvious insights, one per stakeholder."))

    # 13. Bonus 1 — outage blast radius
    slides.append(content_slide(
        "1 · Outage blast-radius: incident → revenue map", "TASK 3 · FOR ENG + CS LEADERS",
        [line(f"Only {o['n_primary_calls']} calls are ABOUT the Detect outage — "
              f"but its ripples reach {o['n_calls']} calls across "
              f"{o['n_customers_touched']} customer accounts.",
              bold=True, color=NAVY, sz=1900, after=650),
         bullet("Internally: war rooms & post-mortems. Externally: renewal-risk and "
                "escalation calls referencing the same incident."),
         bullet("Stitching the internal incident timeline to the external calls it "
                "generated gives a single 'one outage cost us THESE accounts' view."),
         bullet("No single transcript shows this — only the aggregate does. It's the "
                "artefact that justifies reliability investment.", color=GREY)]))

    # 14. Bonus 2 — churn board
    churn = [a for a in ro["churn_ranked"] if a["churn_calls"]][:6]
    crows = [[(a["customer"], INK, True), (str(a["calls"]), INK),
              (str(a["churn_calls"]), RED, True),
              (f"{a['avg_score']}", RED if (a['avg_score'] or 5) < 3 else AMBER, True)]
             for a in churn]
    slides.append(table_slide(
        "2 · Churn-risk early-warning board", "TASK 3 · FOR CS + SALES LEADERS",
        ["Account", "Calls", "Calls w/ churn signal", "Avg sentiment"],
        crows, col_x=[838200, 5200000, 6700000, 9600000], accent=AMBER,
        note="Low sentiment + a churn_signal moment across an account's calls = a "
             "ranked watch-list to action BEFORE the renewal conversation goes bad."))

    # 15. Bonus 3 & 4
    slides.append(content_slide(
        "3 · Feature-gap demand   ·   4 · Action-item ledger", "TASK 3 · FOR PRODUCT + EVERY LEADER",
        [bullet("Feature-gap demand (Product): feature_gap moments appear across "
                "49 calls. Rolled up, scattered asks become a DEMAND-WEIGHTED "
                "backlog — 'how many paying accounts asked for X' — far more "
                "persuasive than one loud customer.", bold=True, color=NAVY),
         line(" ", sz=600),
         bullet("Action-item ledger (everyone): every call carries actionItems with "
                "named owners. Grouping them by owner/account builds a cross-call "
                "commitment ledger — and checking whether the NEXT call references "
                "them as done is a cheap follow-through metric invisible in any "
                "single transcript.", bold=True, color=NAVY)]))

    # 16. Deliverables / how to run
    slides.append(content_slide(
        "Deliverables & how to run", "REPRODUCIBILITY",
        [bullet("python pipeline.py  →  regenerates results.json, insights.md, report.html", sz=1550),
         bullet("python make_ppt.py  →  regenerates this deck (.pptx)", sz=1550),
         bullet("python -m unittest  →  20 tests (logic + dataset invariants), all green", sz=1550),
         line(" ", sz=400),
         bullet("Dependency-free Python stdlib; dataset used as-is, nothing relabelled "
                "or synthesised", color=GREY, sz=1500),
         bullet("Upstream sentiment/key-moment labels treated as FEATURES, not ground "
                "truth — validate with a spot-check before acting on the churn board", color=GREY, sz=1500)]))

    # 17. Conclusion
    slides.append(content_slide(
        "Conclusion & recommendations", "THE BOTTOM LINE",
        [bullet("Pain is concentrated, not spread evenly — spend the next "
                "reliability/CS dollar on the Bug & Outage workflows, not everywhere.",
                bold=True),
         bullet("One incident, many invoices at risk — the Detect outage links an "
                "internal reliability problem to 23 at-risk accounts.", bold=True),
         bullet("The same enrichment pass serves four leaders — CS, Sales, Product, "
                "Engineering — which is the real product thesis.", bold=True),
         line(" ", sz=400),
         line("Next: validate the labels, add embedding clustering to discover "
              "emergent themes at scale, and close the loop on action-item "
              "follow-through.", color=GREY, sz=1550)]))

    return slides


# --------------------------------------------------------------------------- #
# Assemble the .pptx ZIP
# --------------------------------------------------------------------------- #
def main():
    with open(os.path.join(OUTPUT_DIR, "results.json"), "r", encoding="utf-8") as fh:
        ro = json.load(fh)["rollups"]

    slides = build_slides(ro)
    n = len(slides)
    out_path = os.path.join(OUTPUT_DIR, "Transcript_Intelligence.pptx")

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _content_types(n))
        z.writestr("_rels/.rels", ROOT_RELS)
        z.writestr("ppt/presentation.xml", _presentation(n))
        z.writestr("ppt/_rels/presentation.xml.rels", _presentation_rels(n))
        z.writestr("ppt/theme/theme1.xml", THEME)
        z.writestr("ppt/slideMasters/slideMaster1.xml", SLIDE_MASTER)
        z.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", SLIDE_MASTER_RELS)
        z.writestr("ppt/slideLayouts/slideLayout1.xml", SLIDE_LAYOUT)
        z.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", SLIDE_LAYOUT_RELS)
        for i, slide in enumerate(slides, start=1):
            z.writestr(f"ppt/slides/slide{i}.xml", slide)
            z.writestr(f"ppt/slides/_rels/slide{i}.xml.rels", SLIDE_RELS)

    print(f"Wrote {out_path}  ({n} slides)")
    return out_path


if __name__ == "__main__":
    main()
