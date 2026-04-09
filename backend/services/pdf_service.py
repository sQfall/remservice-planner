import os
from datetime import datetime, timedelta
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

FONT_NAME = "DejaVuSans"
FONT_SIZE = 10
TITLE_SIZE = 16
HEADER_SIZE = 12


_REGISTERED_FONT: str | None = None


def _register_font() -> str:
    """Зарегистрировать кириллический шрифт DejaVu."""
    global _REGISTERED_FONT
    if _REGISTERED_FONT is not None:
        return _REGISTERED_FONT

    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        os.path.join(os.path.dirname(__file__), "fonts", "DejaVuSans.ttf"),
        # Windows — DejaVu
        r"C:\Windows\Fonts\DejaVuSans.ttf",
        # Windows — Arial (поддерживает кириллицу)
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\ARIAL.TTF",
    ]

    for path in font_paths:
        if os.path.exists(path):
            pdfmetrics.registerFont(TTFont(FONT_NAME, path))
            _REGISTERED_FONT = FONT_NAME
            return _REGISTERED_FONT

    # Fallback на Helvetica (без кириллицы)
    _REGISTERED_FONT = "Helvetica"
    return _REGISTERED_FONT


def _format_duration(minutes: int) -> str:
    """Форматировать минуты в Ч:ММ."""
    h = minutes // 60
    m = minutes % 60
    return f"{h}:{m:02d}"


def _format_distance(meters: float) -> str:
    """Форматировать метры в км."""
    return f"{meters / 1000:.1f}"


def _styled_table(data, col_widths=None):
    """Создать таблицу с рамками."""
    table = Table(data, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("FONTSIZE", (0, 0), (-1, -1), FONT_SIZE),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return table


def _header_table(data, col_widths=None):
    """Таблица заголовка без рамок."""
    table = Table(data, colWidths=col_widths)
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
                ("ALIGN", (0, 0), (0, -1), "RIGHT"),
                ("ALIGN", (1, 0), (1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def generate_route_sheet_pdf(brigade_data: dict) -> bytes:
    """Сгенерировать маршрутный лист в PDF.

    brigade_data: dict с ключами:
        date: datetime
        brigade_name: str
        specialization: str
        vehicle_plate: str
        vehicle_type: str
        members: list[dict(full_name, role)]
        route_points: list[dict(sequence, arrival_time, address, contact_person, phone, work_type, estimated_duration)]
        total_distance: float (метры)
        total_duration: int (минуты)
    """
    font_name = _register_font()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = getSampleStyleSheet()

    # Заголовок
    title_style = ParagraphStyle(
        "TitleCustom",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=TITLE_SIZE,
        alignment=TA_CENTER,
        spaceAfter=5 * mm,
    )

    subtitle_style = ParagraphStyle(
        "SubtitleCustom",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=HEADER_SIZE,
        alignment=TA_CENTER,
        spaceAfter=5 * mm,
    )

    elements = []

    # Заголовок документа
    plan_date = brigade_data["date"]
    date_str = plan_date.strftime("%d.%m.%Y") if isinstance(plan_date, datetime) else str(plan_date)

    elements.append(Paragraph("МАРШРУТНЫЙ ЛИСТ", title_style))
    elements.append(Paragraph(f"на {date_str}", subtitle_style))
    elements.append(Spacer(1, 5 * mm))

    # Информация о бригаде
    brigade_info = [
        ["Бригада:", brigade_data.get("brigade_name", "")],
        ["Специализация:", brigade_data.get("specialization", "")],
        ["Автомобиль:", f"{brigade_data.get('vehicle_type', '')} {brigade_data.get('vehicle_plate', '')}"],
    ]
    elements.append(_header_table(brigade_info, col_widths=[100 * mm, 70 * mm]))
    elements.append(Spacer(1, 5 * mm))

    # Состав бригады
    members = brigade_data.get("members", [])
    if members:
        members_header = [
            [Paragraph("<b>Состав бригады</b>", ParagraphStyle("Bold", fontName=font_name, fontSize=FONT_SIZE))]
        ]
        members_table = Table(members_header, colWidths=[10 * cm])
        members_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(members_table)

        members_data = [["ФИО", "Должность"]]
        for m in members:
            members_data.append([m.get("full_name", ""), m.get("role", "")])

        members_tbl = _styled_table(members_data, col_widths=[100 * mm, 70 * mm])
        # Стиль заголовка
        style_additions = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), font_name),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ]
        members_tbl.setStyle(TableStyle(style_additions))
        elements.append(members_tbl)
        elements.append(Spacer(1, 5 * mm))

    # Маршрут
    route_points = brigade_data.get("route_points", [])
    if route_points:
        route_header = [
            [Paragraph("<b>Маршрут</b>", ParagraphStyle("BoldRoute", fontName=font_name, fontSize=FONT_SIZE))]
        ]
        route_header_table = Table(route_header, colWidths=[170 * mm])
        route_header_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(route_header_table)

        route_data = [
            [
                Paragraph("<b>№</b>", ParagraphStyle("BN", fontName=font_name, fontSize=FONT_SIZE)),
                Paragraph("<b>Время</b>", ParagraphStyle("BT", fontName=font_name, fontSize=FONT_SIZE)),
                Paragraph("<b>Окно</b>", ParagraphStyle("BWn", fontName=font_name, fontSize=FONT_SIZE)),
                Paragraph("<b>Адрес</b>", ParagraphStyle("BA", fontName=font_name, fontSize=FONT_SIZE)),
                Paragraph("<b>Клиент</b>", ParagraphStyle("BC", fontName=font_name, fontSize=FONT_SIZE)),
                Paragraph("<b>Телефон</b>", ParagraphStyle("BP", fontName=font_name, fontSize=FONT_SIZE)),
                Paragraph("<b>Вид работ</b>", ParagraphStyle("BW", fontName=font_name, fontSize=FONT_SIZE)),
                Paragraph("<b>Длит.</b>", ParagraphStyle("BD", fontName=font_name, fontSize=FONT_SIZE)),
            ]
        ]

        for point in route_points:
            arrival_time = point.get("arrival_time")
            time_str = ""
            if arrival_time:
                if isinstance(arrival_time, datetime):
                    time_str = arrival_time.strftime("%H:%M")
                else:
                    time_str = str(arrival_time)

            # Форматируем временное окно
            tw_start = point.get("time_window_start")
            tw_end = point.get("time_window_end")
            if tw_start and tw_end:
                # tw_start/tw_end — datetime.time или строки
                if isinstance(tw_start, datetime):
                    window_str = tw_start.strftime("%H:%M") + "–" + tw_end.strftime("%H:%M")
                elif isinstance(tw_start, str):
                    window_str = tw_start[:5] + "–" + tw_end[:5]
                else:
                    window_str = tw_start.strftime("%H:%M") + "–" + tw_end.strftime("%H:%M")
            else:
                window_str = "—"

            est_duration = point.get("estimated_duration") or 60
            route_data.append(
                [
                    str(point.get("sequence", "")),
                    time_str,
                    Paragraph(window_str, ParagraphStyle("Win", fontName=font_name, fontSize=FONT_SIZE - 1)),
                    Paragraph(point.get("address", ""), ParagraphStyle("Addr", fontName=font_name, fontSize=FONT_SIZE)),
                    Paragraph(point.get("contact_person", ""), ParagraphStyle("CP", fontName=font_name, fontSize=FONT_SIZE)),
                    Paragraph(point.get("phone", ""), ParagraphStyle("Ph", fontName=font_name, fontSize=FONT_SIZE)),
                    point.get("work_type", ""),
                    f"{est_duration} мин",
                ]
            )

        col_widths = [9 * mm, 13 * mm, 16 * mm, 40 * mm, 27 * mm, 19 * mm, 20 * mm, 16 * mm]
        route_tbl = _styled_table(route_data, col_widths=col_widths)
        hdr_style = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("ALIGN", (7, 0), (7, -1), "CENTER"),
            ("ALIGN", (1, 0), (1, -1), "CENTER"),
            ("ALIGN", (2, 0), (2, -1), "CENTER"),
        ]
        route_tbl.setStyle(TableStyle(hdr_style))
        elements.append(route_tbl)
        elements.append(Spacer(1, 5 * mm))

    # Итого — УДАЛЕНО по запросу пользователя

    # Подпись бригадира
    signature_style = ParagraphStyle(
        "Signature",
        fontName=font_name,
        fontSize=FONT_SIZE,
        alignment=TA_LEFT,
    )
    elements.append(Paragraph("Бригадир: _______________ / _______________", signature_style))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph("Дата: _______________", signature_style))

    doc.build(elements)
    buffer.seek(0)
    return buffer.getvalue()
