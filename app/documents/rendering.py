"""Consistent PDF layout for synthetic sources and scoped handoff documents."""

import re
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle


def render(text, path, title, source_id="PROJECT GUIDE"):
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    styles["BodyText"].allowWidows = 0
    styles["BodyText"].allowOrphans = 0
    styles["Title"].textColor = colors.HexColor("#173e37")
    styles["Heading2"].keepWithNext = True
    story = [
        Paragraph(escape(title), styles["Title"]),
        Paragraph(
            "Customer Case Intelligence | Fictional demonstration", styles["Normal"]
        ),
        Spacer(1, 18),
    ]
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
        lines = block.strip().splitlines()
        if not lines:
            continue
        if lines[0].lstrip().startswith("|"):
            rows = []
            for line in lines:
                if re.fullmatch(r"[\s|:\-]+", line):
                    continue
                rows.append(
                    [
                        Paragraph(escape(cell.strip()), styles["BodyText"])
                        for cell in line.strip().strip("|").split("|")
                    ]
                )
            if rows:
                n = max(map(len, rows))
                rows = [r + [""] * (n - len(r)) for r in rows]
                table = Table(
                    rows,
                    colWidths=([115, 353] if n == 2 else [468 / n] * n),
                    repeatRows=1,
                    hAlign="LEFT",
                )
                table.setStyle(
                    TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e3eee9")),
                            ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#b8c8c1")),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 5),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                        ]
                    )
                )
                story.extend([table, Spacer(1, 10)])
        else:
            if lines[0].startswith("#"):
                story.append(
                    Paragraph(escape(lines.pop(0).lstrip("# ")), styles["Heading2"])
                )
            if lines:
                clean = "<br/>".join(
                    escape(line.replace("**", "").replace("`", "")) for line in lines
                )
                story.append(Paragraph(clean, styles["BodyText"]))
            story.append(Spacer(1, 6))

    def footer(c, d):
        c.setFont("Helvetica", 8)
        c.setFillColor(colors.HexColor("#51645c"))
        c.drawString(
            48, 28, f"{source_id} | Synthetic / reference material | Page {d.page}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    SimpleDocTemplate(
        str(path),
        pagesize=(612, 792),
        rightMargin=72,
        leftMargin=72,
        topMargin=48,
        bottomMargin=48,
        title=title,
        author="Customer Case Intelligence",
    ).build(story, onFirstPage=footer, onLaterPages=footer)
