"""Bikin rw08/qgis/PANDUAN.pdf: khusus kirim update + dapetin banner pdf RW 08 (tanpa link / qr).
Screenshot diambil dari rw08/panduan/ss, kalau gak ada dari panduan/ss (punya RW 02, yang umum aja).
py rw08/panduan/buat_panduan.py"""
import os, tempfile
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, KeepTogether
from PIL import Image as PI

D = os.path.dirname(os.path.abspath(__file__))
SS = [os.path.join(D, "ss"), os.path.join(D, "..", "..", "panduan", "ss")]
OUT = os.path.join(D, "..", "qgis", "PANDUAN.pdf")
HIJAU, EMAS, MARUN = colors.HexColor("#1b6c32"), colors.HexColor("#febd59"), colors.HexColor("#7a0000")

LANGKAH = [
    ("", "sebelum mulai", [
        "ekstrak zip nya, isinya folder <b>Peta_RW08</b>. semua file di folder itu jangan dipisah ya.",
        "pastiin ada file <b>token.txt</b> di folder itu. jangan dihapus dan jangan disebar, itu kunci buat ngirim ke github.",
        "butuh internet. gak perlu install python, gak perlu login github.",
    ], None),
    ("1", "simpan editan di qgis", [
        "kalau abis edit titik / foto di qgis, klik ikon disket (<b>Save Layer Edits</b>) di sebelah pensil.",
        "matiin pensilnya, terus <b>tutup qgis</b>. ini penting, kalau qgis masih kebuka editannya belum kesimpen penuh.",
        "foto baru taruh dulu di folder <b>foto</b> di dalam Peta_RW08 biar ikut kekirim.",
    ], "06_simpan"),
    ("2", "kirim update", [
        "klik 2x <b>kirim_update.bat</b> di folder Peta_RW08.",
        "nanti muncul jendela hitam. biarin aja, jangan ditutup. dia upload editan terus nunggu github bikin banner.",
        "tunggu sekitar 5 menit sampai muncul tulisan <b>beres!</b>",
        "<i>(contoh tampilan jendelanya)</i>",
    ], "07_kirim_update"),
    ("3", "ambil pdf nya", [
        "pas beres, folder <b>banner</b> kebuka sendiri. isinya 2 pdf ukuran 75x45 cm:",
        "<b>..._citra.pdf</b> pakai latar citra satelit, <b>..._vektor.pdf</b> latar peta biasa. pilih salah satu buat dicetak.",
        "kalau gak ada editan, klik kirim_update.bat aja, dia cuma download banner yang terbaru.",
        "<i>(contoh hasil banner)</i>",
    ], "08_banner"),
    ("", "kalau ada masalah", [
        "<b>qgis masih kebuka</b>: tutup dulu qgisnya terus klik lagi kirim_update.bat.",
        "<b>gak bisa nyambung ke github</b>: internetnya mati atau wifinya ngeblok. ganti wifi / pakai hotspot hp.",
        "<b>token.txt nya ditolak</b>: token udah kadaluarsa, kabarin admin buat minta yang baru.",
        "<b>foto gak muncul di banner</b>: fotonya belum dicopy ke folder foto. banner cuma muat 8 foto.",
        "<b>gagal upload</b>: screenshot jendelanya terus kirim ke admin.",
    ], None),
]

st_judul = ParagraphStyle("j", fontName="Helvetica-Bold", fontSize=20, textColor=colors.white, leading=24)
st_sub = ParagraphStyle("s", fontName="Helvetica", fontSize=10.5, textColor=EMAS, leading=14)
st_h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=13.5, textColor=HIJAU, leading=17, spaceBefore=4)
st_p = ParagraphStyle("p", fontName="Helvetica", fontSize=10.5, leading=15, textColor=colors.HexColor("#1f2937"))

def cari_ss(nama):
    for d in SS:
        for ext in (".png", ".jpg", ".jpeg"):
            p = os.path.join(d, nama + ext)
            if os.path.exists(p): return p

def gambar(nama, lebar=17 * cm, maks_tinggi=11 * cm):
    p = cari_ss(nama)
    if not p:
        return Paragraph(f"<i>[screenshot {nama} belum ada]</i>", st_p)
    im0 = PI.open(p).convert("RGB"); w, h = im0.size
    tmp = os.path.join(tempfile.gettempdir(), "panduan08_" + nama + ".jpg"); im0.save(tmp, quality=85)
    s = min(lebar / w, maks_tinggi / h, 2.54 * cm / 100)   # jangan diperbesar lebih dari ~100 dpi
    t = Table([[Image(tmp, w * s, h * s)]], colWidths=[w * s]); t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.2, HIJAU)] + [(k, (0, 0), (-1, -1), 0) for k in ("LEFTPADDING", "RIGHTPADDING", "TOPPADDING", "BOTTOMPADDING")]))
    return t

def kepala(c, doc):
    c.saveState()
    c.setFillColor(HIJAU); c.rect(0, A4[1] - 0.6 * cm, A4[0], 0.6 * cm, fill=1, stroke=0)
    c.setFillColor(EMAS); c.rect(0, A4[1] - 0.75 * cm, A4[0], 0.15 * cm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#6b7280")); c.setFont("Helvetica", 8.5)
    c.drawString(2 * cm, 1.2 * cm, "panduan kirim update & banner rw 08 semaki")
    c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"hal {doc.page}")
    c.restoreState()

isi = []
lg = [Image(f, 2 * cm, 2 * cm) for f in (os.path.join(D, "..", "logo", x) for x in ("uad.jpg", "tim.png")) if os.path.exists(f)]
judul = [Paragraph("cara kirim update &amp; bikin banner rw 08", st_judul), Spacer(1, 4),
         Paragraph("kelurahan semaki, umbulharjo, kota yogyakarta", st_sub)]
head = Table([[lg[0] if lg else "", judul, lg[1] if len(lg) > 1 else ""]], colWidths=[2.6 * cm, 11.8 * cm, 2.6 * cm])
head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HIJAU), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                          ("LINEBELOW", (0, 0), (-1, -1), 4, EMAS), ("TOPPADDING", (0, 0), (-1, -1), 10),
                          ("BOTTOMPADDING", (0, 0), (-1, -1), 10), ("ALIGN", (0, 0), (0, 0), "CENTER"), ("ALIGN", (2, 0), (2, 0), "CENTER")]))
isi += [head, Spacer(1, 14)]

for no, judul_l, baris, ss in LANGKAH:
    blok = [Paragraph((f"{no}. " if no else "") + judul_l, st_h), Spacer(1, 3)]
    blok += [Paragraph("• " + b, st_p) for b in baris]
    if ss: blok += [Spacer(1, 6), gambar(ss)]
    isi.append(KeepTogether(blok)); isi.append(Spacer(1, 14))

SimpleDocTemplate(OUT, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.6 * cm, bottomMargin=2 * cm,
                  title="Panduan Kirim Update RW 08", author="KKN UAD").build(isi, onFirstPage=kepala, onLaterPages=kepala)
print("PANDUAN.pdf jadi:", os.path.abspath(OUT))
