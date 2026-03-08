"""
pdf_engine.py
PDF generation logic for tent-card nametags.
Adapted from generate_nametags.py — generates to a BytesIO buffer
so Streamlit can serve it as a download without writing to disk.
"""

import io
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas

# ── page & layout ─────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = letter          # 612 x 792 pt
QUARTER        = PAGE_H / 4     # 198 pt  (~2.75 in)

H_MARGIN  = 18   # pt left/right margin inside Q2
V_PADDING = 12   # pt top/bottom padding inside Q2

# ── text sizing ───────────────────────────────────────────────────────────────
FIRST_LAST_RATIO = 0.60   # last name is 60 % of first name size
LINE_GAP_RATIO   = 0.20   # gap between lines = 20 % of first name size
MAX_FIRST_SIZE   = 160    # starting (maximum) font size for first name

# ── fold line style ───────────────────────────────────────────────────────────
FOLD_COLOR      = colors.HexColor("#999999")
FOLD_WIDTH      = 0.6
FOLD_DASH       = [8, 5]
FOLD_LABEL_SIZE = 7
FOLD_LABEL      = "fold"


def _best_font_size(c: canvas.Canvas, text: str, font: str,
                    max_w: float, start_size: float) -> float:
    """Largest integer font size where text fits within max_w."""
    size = start_size
    while size > 6:
        if c.stringWidth(text, font, size) <= max_w:
            return size
        size -= 0.5
    return 6


def _compute_sizes(c: canvas.Canvas,
                   first: str, last: str,
                   max_w: float, max_h: float) -> tuple[float, float]:
    font = "Helvetica-Bold"
    fs = _best_font_size(c, first, font, max_w, MAX_FIRST_SIZE)
    ls = _best_font_size(c, last,  font, max_w, fs * FIRST_LAST_RATIO)

    def block_h(f, l):
        return f + f * LINE_GAP_RATIO + l

    if block_h(fs, ls) > max_h:
        total_ratio = 1 + LINE_GAP_RATIO + FIRST_LAST_RATIO
        fs = min(fs, max_h / total_ratio)
        ls = fs * FIRST_LAST_RATIO
        fs = _best_font_size(c, first, font, max_w, fs)
        ls = _best_font_size(c, last,  font, max_w, fs * FIRST_LAST_RATIO)

    return fs, ls


def _draw_name_quarter(c: canvas.Canvas, first: str, last: str) -> None:
    """Draw the name block centred in Q2 (y = 2*QUARTER to 3*QUARTER)."""
    font   = "Helvetica-Bold"
    q2_bot = 2 * QUARTER
    q2_top = 3 * QUARTER
    q2_h   = QUARTER
    cx     = PAGE_W / 2

    max_w = PAGE_W - 2 * H_MARGIN
    max_h = q2_h   - 2 * V_PADDING

    fs, ls = _compute_sizes(c, first, last, max_w, max_h)
    gap    = fs * LINE_GAP_RATIO

    block_h   = fs + gap + ls
    block_bot = q2_bot + (q2_h - block_h) / 2

    # Last name (lower)
    c.setFont(font, ls)
    c.setFillColor(colors.black)
    lw = c.stringWidth(last, font, ls)
    c.drawString(cx - lw / 2, block_bot, last)

    # First name (above last name)
    c.setFont(font, fs)
    fw = c.stringWidth(first, font, fs)
    c.drawString(cx - fw / 2, block_bot + ls + gap, first)


def _draw_fold_lines(c: canvas.Canvas) -> None:
    """Draw three dashed fold lines at Q boundaries."""
    c.saveState()
    c.setStrokeColor(FOLD_COLOR)
    c.setLineWidth(FOLD_WIDTH)
    c.setDash(*FOLD_DASH)
    c.setFont("Helvetica", FOLD_LABEL_SIZE)
    c.setFillColor(FOLD_COLOR)

    for i in (1, 2, 3):
        y = i * QUARTER
        c.line(0, y, PAGE_W, y)
        c.setDash()
        label_x = PAGE_W - c.stringWidth(FOLD_LABEL, "Helvetica", FOLD_LABEL_SIZE) - 4
        c.drawString(label_x, y + 2, FOLD_LABEL)
        c.setDash(*FOLD_DASH)

    c.restoreState()


def generate_pdf_bytes(students: list[tuple[str, str]]) -> bytes:
    """
    Generate nametag PDF for a list of (first_name, last_name) tuples.
    Returns the PDF as bytes (suitable for st.download_button).
    """
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)

    for first, last in students:
        _draw_name_quarter(c, first, last)
        _draw_fold_lines(c)
        c.showPage()

    c.save()
    return buffer.getvalue()
