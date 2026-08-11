"""Generación de PDFs de listas RRPP para Floki Manager."""
from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Iterable, Mapping

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

PURPLE = colors.HexColor("#A84CFF")
PURPLE_DARK = colors.HexColor("#4A176E")
BLACK = colors.HexColor("#09070D")
DARK = colors.HexColor("#17131F")
MID = colors.HexColor("#6E6678")
LIGHT = colors.HexColor("#F7F3FB")
LINE = colors.HexColor("#D9D0E2")
GREEN = colors.HexColor("#198754")


def _safe(value: object) -> str:
    text = str(value or "").strip()
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "FlokiTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=22,
            textColor=BLACK,
            alignment=TA_LEFT,
            spaceAfter=3 * mm,
        ),
        "subtitle": ParagraphStyle(
            "FlokiSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=MID,
        ),
        "section": ParagraphStyle(
            "FlokiSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=PURPLE_DARK,
            spaceBefore=3 * mm,
            spaceAfter=2 * mm,
        ),
        "cell": ParagraphStyle(
            "FlokiCell",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=BLACK,
        ),
        "cell_bold": ParagraphStyle(
            "FlokiCellBold",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=BLACK,
        ),
        "small": ParagraphStyle(
            "FlokiSmall",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=10,
            textColor=MID,
        ),
        "footer": ParagraphStyle(
            "FlokiFooter",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=9,
            textColor=MID,
            alignment=TA_CENTER,
        ),
    }


def _page_decor(canvas, doc, event_name: str):
    canvas.saveState()
    width, height = A4
    canvas.setFillColor(BLACK)
    canvas.rect(0, height - 8 * mm, width, 8 * mm, stroke=0, fill=1)
    canvas.setFillColor(PURPLE)
    canvas.rect(0, height - 8.8 * mm, width, 0.8 * mm, stroke=0, fill=1)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MID)
    canvas.drawString(15 * mm, 9 * mm, f"Floki Manager - {event_name}")
    canvas.drawRightString(width - 15 * mm, 9 * mm, f"Página {doc.page}")
    canvas.restoreState()


def _header_story(styles, event: Mapping, order_label: str, total: int, logo_path: Path | None):
    event_name = _safe(event.get("event_name") or "Evento Floki")
    raw_event_date = str(event.get("event_date") or "")
    try:
        event_date = datetime.fromisoformat(raw_event_date[:10]).strftime("%d/%m/%Y")
    except ValueError:
        event_date = _safe(raw_event_date)
    generated = datetime.now().strftime("%d/%m/%Y %H:%M")

    title_block = [
        Paragraph("FLOKI - LISTAS DEL EVENTO", styles["title"]),
        Paragraph(
            f"<b>Evento:</b> {event_name} &nbsp;&nbsp; <b>Fecha:</b> {event_date or '-'}<br/>"
            f"<b>Orden:</b> {_safe(order_label)} &nbsp;&nbsp; <b>Total:</b> {total} personas &nbsp;&nbsp; "
            f"<b>Generado:</b> {generated}",
            styles["subtitle"],
        ),
    ]
    if logo_path and logo_path.exists():
        logo = Image(str(logo_path), width=24 * mm, height=24 * mm)
        header = Table([[logo, title_block]], colWidths=[30 * mm, 150 * mm])
        header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (0, 0), "CENTER"),
            ("BACKGROUND", (0, 0), (0, 0), BLACK),
            ("BOX", (0, 0), (0, 0), 0.6, PURPLE),
            ("LEFTPADDING", (0, 0), (0, 0), 2),
            ("RIGHTPADDING", (0, 0), (0, 0), 2),
            ("TOPPADDING", (0, 0), (0, 0), 2),
            ("BOTTOMPADDING", (0, 0), (0, 0), 2),
            ("LEFTPADDING", (1, 0), (1, 0), 8),
            ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ("TOPPADDING", (1, 0), (1, 0), 0),
            ("BOTTOMPADDING", (1, 0), (1, 0), 0),
        ]))
        return [header, Spacer(1, 5 * mm)]
    return title_block + [Spacer(1, 4 * mm)]


def _table(data, widths, repeat_rows=1):
    table = Table(data, colWidths=widths, repeatRows=repeat_rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.35, LINE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table


def build_lists_pdf(
    event: Mapping,
    rows: Iterable[Mapping],
    order: str = "name",
    logo_path: Path | None = None,
) -> bytes:
    """Devuelve el PDF como bytes.

    Genera una unica version: promotores A-Z, personas A-Z dentro de cada lista,
    CUMPLEAÑOS después de los promotores, PROMOS casi al final y LISTA COMÚN al final. El parametro order se conserva solo por compatibilidad.
    """
    records = [dict(row) for row in rows]
    styles = _styles()
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=15 * mm,
        bottomMargin=16 * mm,
        title=f"Listas - {event.get('event_name') or 'Floki'}",
        author="Floki Manager",
    )
    event_name = str(event.get("event_name") or "Evento Floki")
    story = []

    order = "promoter"
    order_label = "Promotores A-Z - Cumpleaños - PROMOS - Lista común"
    story.extend(_header_story(styles, event, order_label, len(records), logo_path))

    if not records:
        story.append(Paragraph("No hay personas cargadas para este evento.", styles["subtitle"]))
    else:
        records.sort(key=lambda row: (
            3 if row.get("is_common") else (2 if row.get("is_promo") else (1 if row.get("is_birthday") else 0)),
            str(row.get("promoter_name") or "").casefold(),
            str(row.get("guest_name") or "").casefold(),
        ))
        groups: dict[tuple[str, bool, bool], list[dict]] = {}
        for row in records:
            key = (str(row.get("promoter_name") or "LISTA COMÚN"), bool(row.get("is_common")), bool(row.get("is_promo")), bool(row.get("is_birthday")))
            groups.setdefault(key, []).append(row)

        for group_index, ((promoter_name, is_common, is_promo, is_birthday), guests) in enumerate(groups.items()):
            guests.sort(key=lambda row: str(row.get("guest_name") or "").casefold())
            heading = f"{promoter_name} - {len(guests)} {'persona' if len(guests) == 1 else 'personas'}"
            if is_common:
                note = "Lista común - última sección - FREE válido hasta las 03:30"
            elif is_promo:
                note = "PROMO/PROMOS - sin QR - FREE válido hasta las 03:30"
            elif is_birthday:
                birthday_name = str(guests[0].get("birthday_person_name") or promoter_name.replace("CUMPLEAÑOS - ", "")).strip()
                birth_date = str(guests[0].get("birthday_date_of_birth") or "").strip()
                try:
                    birth_date = datetime.fromisoformat(birth_date[:10]).strftime("%d/%m/%Y")
                except ValueError:
                    pass
                birthday_meta = f" · Nacimiento: {birth_date}" if birth_date else ""
                note = (
                    f"Cumpleañero/a: {birthday_name}{birthday_meta} · Máximo 10 personas · "
                    "FREE hasta 03:30 · 50% OFF en la carta hasta 03:00 · 1 Champagne + 2 energizantes al ingresar 5 o más"
                )
            else:
                note = "Lista de promotor - FREE válido hasta las 03:30"
            block = [
                Paragraph(_safe(heading), styles["section"]),
                Paragraph(_safe(note), styles["small"]),
                Spacer(1, 1.5 * mm),
            ]
            data = [["#", "Nombre", "Estado"]]
            for index, row in enumerate(guests, 1):
                status = "Ingresó" if row.get("checkin_id") else "Pendiente"
                data.append([
                    str(index),
                    Paragraph(_safe(row.get("guest_name")), styles["cell_bold"]),
                    Paragraph(status, styles["cell"]),
                ])
            block.append(_table(data, [12 * mm, 132 * mm, 34 * mm]))
            story.append(KeepTogether(block[:3]))
            story.append(block[3])
            if group_index < len(groups) - 1:
                story.append(Spacer(1, 5 * mm))

    doc.build(
        story,
        onFirstPage=lambda canvas, document: _page_decor(canvas, document, event_name),
        onLaterPages=lambda canvas, document: _page_decor(canvas, document, event_name),
    )
    return output.getvalue()
