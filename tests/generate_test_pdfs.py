"""
Generate realistic test PDFs for AutoRename-PDF testing.

Creates PDFs covering all extraction tiers:
  - Text-native PDFs (Tier 1: pdfplumber)
  - Image-only PDFs (Tier 2: OCR/vision)
  - Mixed PDFs (text + embedded images)
  - Edge cases (empty, huge text, multi-page, special chars)

Usage:
  python tests/generate_test_pdfs.py          # generates into tests/fixtures/
  python tests/generate_test_pdfs.py --dir /tmp/pdfs
"""

import os
import sys
import argparse
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_font():
    """Get a TrueType font for image rendering, with fallback."""
    for name in ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(name, 28)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _get_small_font():
    for name in ["arial.ttf", "Arial.ttf", "DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        try:
            return ImageFont.truetype(name, 16)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _make_logo(width=300, height=80, text="ACME Corp", bg="navy", fg="white"):
    """Create a simple logo-style image."""
    img = Image.new("RGB", (width, height), color=bg)
    draw = ImageDraw.Draw(img)
    font = _get_font()
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((width - tw) / 2, (height - th) / 2), text, fill=fg, font=font)
    return img


def _make_scanned_page(lines, width=1240, height=1754, bg="white", fg="black"):
    """Create an image that looks like a scanned document page."""
    img = Image.new("RGB", (width, height), color=bg)
    draw = ImageDraw.Draw(img)
    font = _get_small_font()
    y = 80
    for line in lines:
        draw.text((80, y), line, fill=fg, font=font)
        y += 30
    return img


# ---------------------------------------------------------------------------
# PDF Generators
# ---------------------------------------------------------------------------

def gen_text_invoice(out_dir):
    """Clean text-only invoice (Tier 1 target)."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.cell(0, 15, "INVOICE", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(5)
    pdf.set_font("Helvetica", size=11)
    rows = [
        "Invoice No: INV-2024-3038228",
        "Date: 15.03.2024",
        "",
        "From: ACME Corporation GmbH",
        "Industriestrasse 42, 8010 Graz, Austria",
        "VAT: ATU12345678",
        "",
        "To: Petermeir Digital Solutions e.U.",
        "Hauptplatz 1, 8530 Bad Gleichenberg, Austria",
        "",
        "Description                     Qty    Unit Price     Total",
        "-" * 65,
        "Web Development Services         40    EUR  85.00    EUR  3,400.00",
        "Hosting & Maintenance             1    EUR 120.00    EUR    120.00",
        "SSL Certificate                   1    EUR  29.00    EUR     29.00",
        "-" * 65,
        "                                          Subtotal   EUR  3,549.00",
        "                                          VAT 20%    EUR    709.80",
        "                                          TOTAL      EUR  4,258.80",
        "",
        "Payment due: 14.04.2024",
        "Bank: Steiermärkische Sparkasse",
        "IBAN: AT12 3456 7890 1234 5678",
    ]
    for row in rows:
        pdf.cell(0, 6, row, new_x="LMARGIN", new_y="NEXT")

    path = os.path.join(out_dir, "text_invoice_acme.pdf")
    pdf.output(path)
    return path


def gen_text_letter(out_dir):
    """Text-only business letter, not an invoice (Tier 1, non-invoice doc type)."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    rows = [
        "Globex Corporation",
        "123 Innovation Drive, Vienna, Austria",
        "",
        "Date: 22.01.2025",
        "",
        "Dear Mr. Petermeir,",
        "",
        "We are pleased to confirm our partnership agreement",
        "effective from February 1st, 2025. The terms outlined",
        "in our previous meeting have been approved by our board.",
        "",
        "Please find attached the signed contract for your records.",
        "",
        "Best regards,",
        "Hank Scorpio",
        "CEO, Globex Corporation",
    ]
    for row in rows:
        pdf.cell(0, 7, row, new_x="LMARGIN", new_y="NEXT")

    path = os.path.join(out_dir, "text_letter_globex.pdf")
    pdf.output(path)
    return path


def gen_text_german_invoice(out_dir):
    """German-language invoice to test date/language handling."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "Rechnung", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)
    pdf.set_font("Helvetica", size=10)
    rows = [
        "Rechnungsnummer: RE-2025-0042",
        "Rechnungsdatum: 08.02.2025",
        "",
        "Mustermann Consulting GmbH",
        "Musterstrasse 10, 1010 Wien",
        "UID: ATU98765432",
        "",
        "An: Petermeir Digital Solutions e.U.",
        "",
        "Leistungsbeschreibung              Menge    Preis       Gesamt",
        "-" * 65,
        "IT-Beratung                           8    EUR 95,00   EUR   760,00",
        "Projektmanagement                     4    EUR 85,00   EUR   340,00",
        "-" * 65,
        "                                              Netto    EUR 1.100,00",
        "                                              USt 20%  EUR   220,00",
        "                                              Brutto   EUR 1.320,00",
        "",
        "Zahlungsziel: 08.03.2025",
        "IBAN: AT99 8765 4321 0987 6543",
    ]
    for row in rows:
        pdf.cell(0, 6, row, new_x="LMARGIN", new_y="NEXT")

    path = os.path.join(out_dir, "text_rechnung_mustermann.pdf")
    pdf.output(path)
    return path


def gen_image_invoice(out_dir):
    """Image-only scanned invoice (Tier 2 target - no extractable text)."""
    lines = [
        "INVOICE",
        "",
        "Invoice No: SC-2024-0099",
        "Date: 03.11.2024",
        "",
        "From: Springfield Power Co.",
        "742 Evergreen Terrace",
        "Springfield, IL 62704",
        "",
        "To: Petermeir Digital Solutions",
        "",
        "Description                  Amount",
        "-" * 45,
        "Energy Consulting            USD 2,500.00",
        "Safety Audit                 USD 1,800.00",
        "-" * 45,
        "Total                        USD 4,300.00",
        "",
        "Payment terms: Net 30",
    ]
    page_img = _make_scanned_page(lines)

    pdf = FPDF()
    pdf.add_page()
    img_path = os.path.join(out_dir, "_tmp_scan.png")
    page_img.save(img_path)
    pdf.image(img_path, x=0, y=0, w=210, h=297)
    os.remove(img_path)

    path = os.path.join(out_dir, "image_invoice_springfield.pdf")
    pdf.output(path)
    return path


def gen_mixed_invoice_with_logo(out_dir):
    """Text invoice with an embedded company logo image (mixed content)."""
    logo = _make_logo(300, 80, "Initech", bg="#2c3e50", fg="#ecf0f1")
    logo_path = os.path.join(out_dir, "_tmp_logo.png")
    logo.save(logo_path)

    pdf = FPDF()
    pdf.add_page()
    pdf.image(logo_path, x=10, y=10, w=60)
    os.remove(logo_path)

    pdf.ln(25)
    pdf.set_font("Helvetica", size=10)
    rows = [
        "Initech Solutions AG",
        "TPS Report Division",
        "4th Floor, 123 Business Park",
        "",
        "Invoice: INIT-2024-1577",
        "Date: 28.06.2024",
        "",
        "Bill to: Petermeir Digital Solutions e.U.",
        "",
        "TPS Report Cover Sheets (500x)     EUR    45.00",
        "Printer Maintenance                EUR   180.00",
        "Red Stapler Replacement            EUR    12.50",
        "                                   -----------",
        "                         Total     EUR   237.50",
        "",
        "Due: 28.07.2024",
    ]
    for row in rows:
        pdf.cell(0, 6, row, new_x="LMARGIN", new_y="NEXT")

    path = os.path.join(out_dir, "mixed_invoice_initech.pdf")
    pdf.output(path)
    return path


def gen_multipage_invoice(out_dir):
    """3-page invoice to test max_pages handling."""
    pdf = FPDF()
    pdf.set_font("Helvetica", size=10)

    # Page 1: header
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "INVOICE - Page 1 of 3", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, "Invoice: MP-2025-0001", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "Date: 01.03.2025", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "From: Stark Industries Ltd", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "To: Petermeir Digital Solutions e.U.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)
    for i in range(1, 31):
        pdf.cell(0, 5, f"  Item {i:03d}: Widget Type-{chr(64+i%26+1)}    EUR {i*12.50:.2f}", new_x="LMARGIN", new_y="NEXT")

    # Page 2: more items
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "Page 2 - Continued", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    for i in range(31, 61):
        pdf.cell(0, 5, f"  Item {i:03d}: Component-{i}          EUR {i*8.75:.2f}", new_x="LMARGIN", new_y="NEXT")

    # Page 3: totals
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, "Page 3 - Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 8, "Subtotal:    EUR  14,250.00", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "VAT 20%:     EUR   2,850.00", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 8, "TOTAL:       EUR  17,100.00", new_x="LMARGIN", new_y="NEXT")

    path = os.path.join(out_dir, "multipage_invoice_stark.pdf")
    pdf.output(path)
    return path


def gen_empty_pdf(out_dir):
    """Completely empty PDF (edge case)."""
    pdf = FPDF()
    pdf.add_page()
    path = os.path.join(out_dir, "empty.pdf")
    pdf.output(path)
    return path


def gen_minimal_text_pdf(out_dir):
    """PDF with very little text (edge case for quality threshold)."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 6, "ref: 42", new_x="LMARGIN", new_y="NEXT")
    path = os.path.join(out_dir, "minimal_text.pdf")
    pdf.output(path)
    return path


def gen_outgoing_invoice(out_dir):
    """Invoice FROM my company (outgoing / AR) to test AR vs ER classification."""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 12, "INVOICE", new_x="LMARGIN", new_y="NEXT", align="C")
    pdf.ln(3)
    pdf.set_font("Helvetica", size=10)
    rows = [
        "Invoice No: OUT-2025-0007",
        "Date: 10.03.2025",
        "",
        "From: Petermeir Digital Solutions e.U.",
        "Hauptplatz 1, 8530 Bad Gleichenberg",
        "UID: ATU00000000",
        "",
        "To: Wayne Enterprises Inc.",
        "1007 Mountain Drive, Gotham City",
        "",
        "Website Redesign                  EUR 8,500.00",
        "SEO Optimization Package          EUR 2,200.00",
        "                                  -----------",
        "                        Total     EUR 10,700.00",
        "",
        "Due: 10.04.2025",
    ]
    for row in rows:
        pdf.cell(0, 6, row, new_x="LMARGIN", new_y="NEXT")

    path = os.path.join(out_dir, "text_outgoing_invoice_wayne.pdf")
    pdf.output(path)
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ALL_GENERATORS = [
    ("text_invoice_acme",           gen_text_invoice,           "Clean text invoice (EN, Tier 1)"),
    ("text_letter_globex",          gen_text_letter,            "Business letter, not invoice (Tier 1)"),
    ("text_rechnung_mustermann",    gen_text_german_invoice,    "German invoice (Tier 1, date/lang)"),
    ("image_invoice_springfield",   gen_image_invoice,          "Image-only scanned invoice (Tier 2)"),
    ("mixed_invoice_initech",       gen_mixed_invoice_with_logo,"Text + logo image (mixed)"),
    ("multipage_invoice_stark",     gen_multipage_invoice,      "3-page invoice (max_pages test)"),
    ("empty",                       gen_empty_pdf,              "Empty PDF (edge case)"),
    ("minimal_text",                gen_minimal_text_pdf,       "Minimal text (quality threshold)"),
    ("text_outgoing_invoice_wayne", gen_outgoing_invoice,       "Outgoing invoice / AR classification"),
]


def main():
    parser = argparse.ArgumentParser(description="Generate test PDFs for AutoRename-PDF")
    parser.add_argument("--dir", default=os.path.join(os.path.dirname(__file__), "fixtures"),
                        help="Output directory (default: tests/fixtures/)")
    args = parser.parse_args()

    os.makedirs(args.dir, exist_ok=True)
    print(f"Generating {len(ALL_GENERATORS)} test PDFs in {args.dir}/\n")

    for name, gen_func, description in ALL_GENERATORS:
        path = gen_func(args.dir)
        size_kb = os.path.getsize(path) / 1024
        print(f"  [{name}] {size_kb:.1f} KB - {description}")

    print(f"\nDone. {len(ALL_GENERATORS)} PDFs generated.")


if __name__ == "__main__":
    main()
