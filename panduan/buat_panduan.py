"""Bikin PANDUAN.pdf dari teks di bawah + screenshot di folder panduan/ss/.
Nama file ss harus sama dengan kolom 'ss' di tiap langkah (png/jpg). Yang belum ada muncul kotak kosong.
py panduan/buat_panduan.py"""
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, KeepTogether, PageBreak
from PIL import Image as PI

D = os.path.dirname(os.path.abspath(__file__))
SS = os.path.join(D, "ss"); os.makedirs(SS, exist_ok=True)
OUT = os.path.join(D, "..", "qgis", "PANDUAN.pdf")
HIJAU, EMAS = colors.HexColor("#1b6c32"), colors.HexColor("#fdbe15")

LANGKAH = [
    ("", "sebelum mulai", [
        "install qgis dulu dari qgis.org, pilih yang LTR.",
        "ekstrak zip nya, isinya folder Peta_RW02. semua file di folder itu jangan dipisah ya.",
        "token.txt jangan dihapus dan jangan disebar, itu kunci buat ngirim ke github.",
    ], None),
    ("1", "buka proyeknya", [
        "klik 2x <b>Peta_RW02_Patangpuluhan.qgs</b>, nanti kebuka di qgis.",
        "harusnya kelihatan citra satelit, garis kuning batas rw 02, jalan, sama titik-titik fasilitas.",
        "citra satelit butuh internet, kalau offline latarnya putih aja.",
    ], "01_buka_proyek"),
    ("2", "nyalain mode edit", [
        "di panel layers kiri bawah klik layer <b>Titik Fasilitas</b>.",
        "klik ikon pensil kuning (<b>Toggle Editing</b>) di toolbar atas.",
    ], "02_toggle_editing"),
    ("3", "geser titik", [
        "pilih <b>Vertex Tool</b> di toolbar (ikon titik dengan panah).",
        "klik titiknya terus geser ke tempat yang bener.",
    ], "03_geser_titik"),
    ("4", "nambah titik baru", [
        "klik <b>Add Point Feature</b> (ikon titik dengan tanda bintang), terus klik di peta tempat titiknya.",
        "nanti muncul form. isi <b>nama</b>, pilih <b>kategori</b> dari daftar, keterangan boleh dikosongin.",
        "kolom nomor gak usah diisi, nanti ngurut sendiri.",
    ], ["04a_tombol_tambah", "04_tambah_titik"]),
    ("5", "nambah atau ganti foto", [
        "copy fotonya dulu ke folder <b>foto</b> yang ada di folder Peta_RW02. jangan ambil dari tempat lain biar ikut kekirim.",
        "klik ikon <b>i</b> (Identify Features, bisa juga Ctrl+Shift+I) terus klik titiknya di peta.",
        "di panel Identify Results klik kanan nama titiknya, pilih <b>Edit Feature Form</b>.",
        "di kolom <b>foto</b> klik tombol <b>...</b> terus pilih fotonya. kalau bener nanti fotonya kelihatan di form.",
        "foto di banner maksimal 8, sisanya cuma muncul di peta online.",
    ], ["05a_ikon_identify", "05_foto"]),
    ("6", "simpan", [
        "klik ikon disket (<b>Save Layer Edits</b>) di sebelah pensil.",
        "matiin lagi pensilnya, terus <b>tutup qgis</b>. ini penting, kalau qgis masih kebuka editannya belum kesimpen penuh.",
    ], "06_simpan"),
    ("7", "kirim ke github", [
        "klik 2x <b>kirim_update.bat</b> di folder Peta_RW02. gak perlu login apa-apa.",
        "tunggu aja jendelanya. sekitar 3 menit muncul tulisan peta online udah ke-update.",
        "sekitar 5 menit banner pdf 75x45 otomatis kedownload ke folder <b>banner</b> terus foldernya kebuka sendiri.",
        "kalau gak ada editan, file ini cuma download banner yang terbaru.",
        "<i>(contoh tampilan jendelanya)</i>",
    ], "07_kirim_update"),
    ("8", "cek hasilnya", [
        "buka <b>kkn-uad.github.io/peta-rw02-patangpuluhan</b> di hp atau laptop. titik yang diklik nanti keluar foto sama keterangannya.",
        "banner pdf nya ada di folder banner, ada versi citra sama vektor.",
    ], "08_peta_online"),
    ("", "kalau ada masalah", [
        "<b>qgis masih kebuka</b>: tutup dulu qgisnya terus klik lagi kirim_update.bat.",
        "<b>gagal upload</b>: cek internet. kalau masih gagal mungkin token nya udah kadaluarsa, kabarin admin.",
        "<b>titik warnanya abu-abu</b>: kategorinya belum dipilih.",
        "<b>foto gak muncul</b>: fotonya belum dicopy ke folder foto.",
    ], None),
]

st_judul = ParagraphStyle("j", fontName="Helvetica-Bold", fontSize=20, textColor=colors.white, leading=24)
st_sub = ParagraphStyle("s", fontName="Helvetica", fontSize=10.5, textColor=EMAS, leading=14)
st_h = ParagraphStyle("h", fontName="Helvetica-Bold", fontSize=13.5, textColor=HIJAU, leading=17, spaceBefore=4)
st_p = ParagraphStyle("p", fontName="Helvetica", fontSize=10.5, leading=15, textColor=colors.HexColor("#1f2937"))

def cari_ss(nama):
    for ext in (".png", ".jpg", ".jpeg"):
        p = os.path.join(SS, nama + ext)
        if os.path.exists(p): return p

def gambar(nama, lebar=17 * cm, maks_tinggi=11 * cm):
    p = cari_ss(nama)
    if not p:
        t = Table([[Paragraph(f"<i>[screenshot: taruh file <b>{nama}.png</b> di folder panduan/ss]</i>", st_p)]],
                  colWidths=[lebar], rowHeights=[3 * cm])
        t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#9ca3af")), ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f3f4f6"))]))
        return t
    import tempfile
    im0 = PI.open(p).convert("RGB"); w, h = im0.size
    tmp = os.path.join(tempfile.gettempdir(), "panduan_" + nama + ".jpg"); im0.save(tmp, quality=82); p = tmp
    s = min(lebar / w, maks_tinggi / h, 2.54 * cm / 100)   # jangan diperbesar lebih dari ~100 dpi
    im = Image(p, w * s, h * s)
    t = Table([[im]], colWidths=[w * s]); t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1.2, HIJAU)]))
    return t

def kepala(c, doc):
    c.saveState()
    c.setFillColor(HIJAU); c.rect(0, A4[1] - 0.6 * cm, A4[0], 0.6 * cm, fill=1, stroke=0)
    c.setFillColor(EMAS); c.rect(0, A4[1] - 0.75 * cm, A4[0], 0.15 * cm, fill=1, stroke=0)
    c.setFillColor(colors.HexColor("#6b7280")); c.setFont("Helvetica", 8.5)
    c.drawString(2 * cm, 1.2 * cm, "panduan update peta rw 02 patangpuluhan")
    c.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f"hal {doc.page}")
    c.restoreState()

isi = []
logo = [os.path.join(D, "..", "logo", f) for f in ("uad.jpg", "kkn.png")]
lg = [Image(f, 2 * cm, 2 * cm) for f in logo if os.path.exists(f)]
judul = [Paragraph("cara update peta rw 02", st_judul), Spacer(1, 4),
         Paragraph("kelurahan patangpuluhan, wirobrajan, kota yogyakarta", st_sub)]
head = Table([[lg[0] if lg else "", judul, lg[1] if len(lg) > 1 else ""]], colWidths=[2.6 * cm, 11.8 * cm, 2.6 * cm])
head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), HIJAU), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                          ("LINEBELOW", (0, 0), (-1, -1), 4, EMAS), ("TOPPADDING", (0, 0), (-1, -1), 10),
                          ("BOTTOMPADDING", (0, 0), (-1, -1), 10), ("ALIGN", (0, 0), (0, 0), "CENTER"), ("ALIGN", (2, 0), (2, 0), "CENTER")]))
isi += [head, Spacer(1, 14)]

for no, judul_l, baris, ss in LANGKAH:
    blok = [Paragraph((f"{no}. " if no else "") + judul_l, st_h), Spacer(1, 3)]
    blok += [Paragraph("• " + b, st_p) for b in baris]
    for x in ([ss] if isinstance(ss, str) else ss or []): blok += [Spacer(1, 6), gambar(x)]
    isi.append(KeepTogether(blok)); isi.append(Spacer(1, 14))

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=1.6 * cm, bottomMargin=2 * cm,
                        title="Panduan Update Peta RW 02", author="KKN UAD")
doc.build(isi, onFirstPage=kepala, onLaterPages=kepala)
semua = [x for *_, s in LANGKAH for x in ([s] if isinstance(s, str) else s or [])]
ada = [x for x in semua if cari_ss(x)]; kurang = [x for x in semua if not cari_ss(x)]
print("PANDUAN.pdf jadi. ss ada:", len(ada), "| belum:", ", ".join(kurang) or "-")
