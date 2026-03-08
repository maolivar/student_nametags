"""
generate_nametags.py
Creates tent-card name tags from lista_nametags.xlsx.
One student per page (letter, portrait). Each page is folded into 4 equal
quarters to form a triangular tent stand.

    Q1  ← blank back flap (glue to Q4)
   ----  fold
    Q2  ← FRONT FACE: first name (large) + last name (smaller)
   ----  fold
    Q3  ← BASE (sits on the table)
   ----  fold
    Q4  ← blank back face

Usage:
    python generate_nametags.py
"""

import os
import openpyxl
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas

# ── page & layout ─────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = letter          # 612 x 792 pt
QUARTER        = PAGE_H / 4     # 198 pt  (~2.75 in)

H_MARGIN = 18   # pt left/right margin inside Q2
V_PADDING = 12  # pt top/bottom padding inside Q2

# ── text sizing ───────────────────────────────────────────────────────────────
FIRST_LAST_RATIO = 0.60   # last name is 60 % of first name size
LINE_GAP_RATIO   = 0.20   # gap between lines = 20 % of first name size
MAX_FIRST_SIZE   = 160    # starting (maximum) font size for first name

# ── fold line style ───────────────────────────────────────────────────────────
FOLD_COLOR = colors.HexColor("#999999")
FOLD_WIDTH = 0.6
FOLD_DASH  = [8, 5]
FOLD_LABEL_SIZE = 7
FOLD_LABEL = "fold"

# ── files ─────────────────────────────────────────────────────────────────────
INPUT_FILE  = "lista_nametags.xlsx"
OUTPUT_FILE = "nametags.pdf"
# ─────────────────────────────────────────────────────────────────────────────


def read_students(path: str) -> list[tuple[str, str]]:
    wb = openpyxl.load_workbook(path)
    ws = wb.active
    students = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        nombre, apellido = row[0], row[1]
        if nombre and apellido:
            students.append((str(nombre).strip(), str(apellido).strip()))
    return students


def best_font_size(c: canvas.Canvas, text: str, font: str,
                   max_w: float, start_size: float) -> float:
    """Largest integer font size where text fits within max_w."""
    size = start_size
    while size > 6:
        if c.stringWidth(text, font, size) <= max_w:
            return size
        size -= 0.5
    return 6


def compute_sizes(c: canvas.Canvas,
                  first: str, last: str,
                  max_w: float, max_h: float) -> tuple[float, float]:
    """
    Return (first_size, last_size) maximising first_size subject to:
      - both names fit horizontally in max_w
      - the stacked text block fits vertically in max_h
      - last_size == first_size * FIRST_LAST_RATIO (unless last name is long)
    """
    font = "Helvetica-Bold"

    # Step 1: fit first name horizontally
    fs = best_font_size(c, first, font, max_w, MAX_FIRST_SIZE)

    # Step 2: derive last name size, then fit it horizontally too
    ls = best_font_size(c, last, font, max_w, fs * FIRST_LAST_RATIO)

    # Step 3: check total block height and scale down if needed
    # block = fs + gap + ls   where gap = fs * LINE_GAP_RATIO
    def block_h(f, l):
        return f + f * LINE_GAP_RATIO + l

    if block_h(fs, ls) > max_h:
        # scale factor so block fits
        # block_h ≈ fs * (1 + LINE_GAP_RATIO + FIRST_LAST_RATIO)
        total_ratio = 1 + LINE_GAP_RATIO + FIRST_LAST_RATIO
        fs = min(fs, max_h / total_ratio)
        ls = fs * FIRST_LAST_RATIO
        # re-check horizontal fit after scaling
        fs = best_font_size(c, first, font, max_w, fs)
        ls = best_font_size(c, last,  font, max_w, fs * FIRST_LAST_RATIO)

    return fs, ls


def draw_name_quarter(c: canvas.Canvas, first: str, last: str) -> None:
    """
    Draw the name block centred in Q2.
    Q2 occupies y = 2*QUARTER to 3*QUARTER (i.e. 396 pt to 594 pt from bottom).
    """
    font   = "Helvetica-Bold"
    q2_bot = 2 * QUARTER          # 396 pt
    q2_top = 3 * QUARTER          # 594 pt
    q2_h   = QUARTER              # 198 pt
    cx     = PAGE_W / 2

    max_w  = PAGE_W - 2 * H_MARGIN
    max_h  = q2_h - 2 * V_PADDING

    fs, ls = compute_sizes(c, first, last, max_w, max_h)
    gap    = fs * LINE_GAP_RATIO

    # Total block height and vertical centre
    block_h = fs + gap + ls
    block_bot = q2_bot + (q2_h - block_h) / 2   # bottom of block (last name baseline)

    # Draw last name (lower)
    c.setFont(font, ls)
    c.setFillColor(colors.black)
    lw = c.stringWidth(last, font, ls)
    c.drawString(cx - lw / 2, block_bot, last)

    # Draw first name (above last name)
    c.setFont(font, fs)
    fw = c.stringWidth(first, font, fs)
    first_y = block_bot + ls + gap
    c.drawString(cx - fw / 2, first_y, first)


def draw_fold_lines(c: canvas.Canvas) -> None:
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
        # label on the right margin
        c.setDash()   # solid for label
        label_x = PAGE_W - c.stringWidth(FOLD_LABEL, "Helvetica", FOLD_LABEL_SIZE) - 4
        c.drawString(label_x, y + 2, FOLD_LABEL)
        c.setDash(*FOLD_DASH)

    c.restoreState()


def generate_pdf(students: list[tuple[str, str]], output_path: str) -> None:
    c = canvas.Canvas(output_path, pagesize=letter)

    for first, last in students:
        draw_name_quarter(c, first, last)
        draw_fold_lines(c)
        c.showPage()

    c.save()
    print(f"Saved {len(students)} pages → {output_path}")


def main():
    script_dir  = os.path.dirname(os.path.abspath(__file__))
    input_path  = os.path.join(script_dir, INPUT_FILE)
    output_path = os.path.join(script_dir, OUTPUT_FILE)

    students = read_students(input_path)
    print(f"Students : {len(students)}")
    generate_pdf(students, output_path)


if __name__ == "__main__":
    main()
