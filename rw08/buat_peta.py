"""Peta Wilayah RW 08 Semaki - layout banner 120 x 90 cm (landscape).

Input : Semaki RW 08.shp/.dbf (UTM 49S / EPSG:32749), data/*.json (OSM via Overpass),
        data/citra_z19.png (Esri World Imagery, dari fetch_citra.py)
Output: output/Peta_RW08_Semaki_<mode>.pdf + .png (150 dpi)
        mode "vektor" = peta garis (jalan, bangunan); mode "citra" = latar citra satelit
Foto  : taruh foto di folder foto/ dengan nama 01.jpg, 02.jpg ... sesuai nomor di legenda.

Jalankan: py buat_peta.py            (dua-duanya)
          py buat_peta.py citra      (satu mode saja)
"""
import json, math, os, sys, subprocess
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, PathPatch, Circle, Polygon
from matplotlib.path import Path
from matplotlib.collections import LineCollection, PolyCollection
import matplotlib.patheffects as pe
from PIL import Image, ImageEnhance
import shapefile

BASE = os.path.dirname(os.path.abspath(__file__))
J = lambda *p: os.path.join(BASE, *p)
plt.rcParams["font.family"] = ["Arial", "Liberation Sans", "DejaVu Sans"]

if len(sys.argv) < 2:   # jalankan semua ukuran x kedua mode
    for u in ("75x45",):
        for m in ("vektor", "citra"):
            subprocess.run([sys.executable, __file__, m], check=True, env={**os.environ, "UKURAN": u})
    sys.exit()
MODE = sys.argv[1]
CITRA = MODE == "citra"

# ------------------------------------------------------------------ konfigurasi
UKURAN = os.environ.get("UKURAN", "75x45")   # ukuran cetak: "75x45", "80x60" atau "120x90"
SKALA_CETAK = None                    # skala di kertas cetak; None = otomatis (batas RW + kelurahan masuk semua)
# Layout dirancang di "kanvas desain" lalu diperkecil F kali ke ukuran cetak (teks & simbol ikut proporsional).
PRESET = {
    "120x90": dict(page=(120.0, 90.0), F=1.0, FW=15.6, FH=14.0, TH=13.2, SH=10.6, PL=1.45, TTD_H=7.0, SRH=6.0),
    "80x60":  dict(page=(120.0, 90.0), F=2 / 3, FW=15.6, FH=14.0, TH=13.2, SH=10.6, PL=1.45, TTD_H=7.0, SRH=6.0),
    "75x45":  dict(page=(125.0, 75.0), F=0.6, FW=14.6, FH=10.6, TH=10.6, SH=8.8, PL=1.05, TTD_H=4.8, SRH=4.9),
}[UKURAN]
PAGE_W, PAGE_H = PRESET["page"]; F = PRESET["F"]
TOP, BOT = PAGE_H - 3.6, 4.0 if F == 1 else 3.6
JUDUL = ["PETA WILAYAH RW 08", "KELURAHAN SEMAKI"]
SUBJUDUL = "KEMANTREN UMBULHARJO, KOTA YOGYAKARTA\nDAERAH ISTIMEWA YOGYAKARTA"
TTD = [("Mengetahui,\nLurah Semaki", "( ................................. )"),
       ("Ketua RW 08", "( ................................. )")]
TAHUN = "2026"
ABAIKAN = set()
ASET = "drive-download-20261115T153336Z-1-001"   # folder foto survei
FOTO_OSM = {}
GANTI_NAMA = {}   # nama mengikuti Geoportal Kota Yogyakarta
ALAMAT_OSM = {}       # foto untuk titik dari OSM
MENYUSUL = []   # fasilitas yang lokasinya belum diketahui (hanya di legenda)
LOGO = ["logo/uad.jpg", "logo/kkn.png"]   # nama titik OSM yang tidak perlu ditandai

HIJAU, EMAS, NAVY, KRIM = "#1b6c32", "#fdbe15", "#033e6f", "#fbf8ea"   # palet logo KKN & UAD
KATEGORI = {
    "Tempat Ibadah": "#1b8a3a",
    "Kesehatan": "#d62828",
    "Pendidikan": "#1d4ed8",
    "Pemerintahan": "#7b2cbf",
    "Ekonomi": "#e07a00",
    "Keamanan": "#be185d",
    "Kebersihan": "#65a30d",
    "Lainnya": "#0e7490",
}

# gaya per mode
if CITRA:
    ST = dict(besar=("#3b1d00", "#f59e0b", 5.5), kecil=("#00000000", "#ffffffd0", 2.0), setapak=("#ffffffb0", 1.2),
              sungai=("#38bdf8", 4), kel="#e879f9", rw_out=EMAS, rw_in=EMAS, rw_dash=None,
              lbl_big="white", lbl_small="white", halo="black", mask=("black", 0.42), sungai_lbl="#7dd3fc")
else:
    ST = dict(besar=("#8c5a00", "#fbc94a", None), kecil=("#7a7a7a", "#ffffff", None), setapak=("#8a8a8a", 1.3),
              sungai=("#6fa8dc", 7), kel="#6d28d9", rw_out=EMAS, rw_in=HIJAU, rw_dash=(0, (6, 2.5)),
              lbl_big="#3b2a00", lbl_small="#374151", halo="white", mask=(KRIM, 0.82), sungai_lbl="#1d5fa8")

# ------------------------------------------------------------------ proyeksi UTM 49S
A_, F_ = 6378137.0, 1 / 298.257223563
E2 = F_ * (2 - F_); EP2 = E2 / (1 - E2); K0 = 0.9996; LON0 = math.radians(111.0)

def utm(lat, lon):
    p, l = math.radians(lat), math.radians(lon)
    n = A_ / math.sqrt(1 - E2 * math.sin(p) ** 2)
    t = math.tan(p) ** 2; c = EP2 * math.cos(p) ** 2; a = math.cos(p) * (l - LON0)
    e4, e6 = E2 * E2, E2 ** 3
    m = A_ * ((1 - E2 / 4 - 3 * e4 / 64 - 5 * e6 / 256) * p
              - (3 * E2 / 8 + 3 * e4 / 32 + 45 * e6 / 1024) * math.sin(2 * p)
              + (15 * e4 / 256 + 45 * e6 / 1024) * math.sin(4 * p)
              - (35 * e6 / 3072) * math.sin(6 * p))
    x = K0 * n * (a + (1 - t + c) * a ** 3 / 6 + (5 - 18 * t + t * t + 72 * c - 58 * EP2) * a ** 5 / 120) + 500000
    y = K0 * (m + n * math.tan(p) * (a * a / 2 + (5 - t + 9 * c + 4 * c * c) * a ** 4 / 24
                                    + (61 - 58 * t + t * t + 600 * c - 330 * EP2) * a ** 6 / 720)) + 10000000
    return x, y

def inv_utm(x, y):
    lat, lon = -7.8, 110.35
    for _ in range(8):  # Newton sederhana (area kecil, konvergen cepat)
        x0, y0 = utm(lat, lon); x1, _ = utm(lat, lon + 1e-4); _, y1 = utm(lat + 1e-4, lon)
        lon += (x - x0) / ((x1 - x0) / 1e-4); lat += (y - y0) / ((y1 - y0) / 1e-4)
    return lat, lon

def geom(e):
    return [utm(p["lat"], p["lon"]) for p in e["geometry"]]

def rings_from_relation(rel):
    segs = [geom(m) for m in rel["members"] if m.get("role") == "outer" and "geometry" in m]
    rings = []
    while segs:
        ring = segs.pop(0)
        changed = True
        while changed and ring[0] != ring[-1]:
            changed = False
            for i, s in enumerate(segs):
                if _close(s[0], ring[-1]): ring += s[1:]
                elif _close(s[-1], ring[-1]): ring += s[::-1][1:]
                elif _close(s[-1], ring[0]): ring = s[:-1] + ring
                elif _close(s[0], ring[0]): ring = s[::-1][:-1] + ring
                else: continue
                segs.pop(i); changed = True; break
        rings.append(ring)
    return rings

def _close(a, b): return abs(a[0] - b[0]) < 0.5 and abs(a[1] - b[1]) < 0.5

def centroid(pts):
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

# ------------------------------------------------------------------ data
GPKG = J("qgis", "peta_rw08.gpkg")   # kalau ada: titik & batas RW dibaca dari proyek QGIS (hasil edit)
def FOTO(f):   # cari file foto: folder qgis/ dulu, lalu folder aset
    if not f: return ""
    nama = os.path.basename(f.replace("\\", "/"))   # foto dipilih dari luar folder foto -> cari nama filenya di qgis/foto
    cand = [J("qgis", f), J(ASET, f), J("qgis", "foto", nama)]
    if os.path.isdir(J("qgis", "foto")):
        cand += [J("qgis", "foto", x) for x in os.listdir(J("qgis", "foto")) if x.lower() == nama.lower()]
    return next((p for p in cand if os.path.isfile(p)), "")
if os.path.exists(GPKG):
    import pyogrio, shapely
    _rwdf = pyogrio.raw.read(GPKG, layer="batas_rw")
    _geom = shapely.from_wkb(_rwdf[2][0])
    _geom = max(getattr(_geom, "geoms", [_geom]), key=lambda g: g.area)
    REC = {k: v[0] for k, v in zip(_rwdf[0]["fields"], _rwdf[3])}
    RW = [utm(lat, lon) for lon, lat in list(_geom.exterior.coords)[:-1]]
    json.dump([list(inv_utm(*p)) for p in RW], open(J("data/rw_latlon.json"), "w"))
else:
    _rw = shapefile.Reader(J("Semaki RW 08"))
    REC = _rw.records()[0].as_dict()
    RW = [tuple(p) for p in _rw.shapes()[0].points]
RW_PATH = Path(RW)
rx0, ry0 = min(p[0] for p in RW), min(p[1] for p in RW); rx1, ry1 = max(p[0] for p in RW), max(p[1] for p in RW)
RCX, RCY = (rx0 + rx1) / 2, (ry0 + ry1) / 2
LUAS = abs(sum(RW[i][0] * RW[i - 1][1] - RW[i - 1][0] * RW[i][1] for i in range(len(RW)))) / 2  # m2

kel = json.load(open(J("data/kelurahan.json"), encoding="utf-8"))["elements"]
ktx = json.load(open(J("data/konteks.json"), encoding="utf-8"))["elements"]
ins = json.load(open(J("data/inset.json"), encoding="utf-8"))["elements"]
KEL = rings_from_relation([e for e in kel if e["type"] == "relation" and e.get("tags", {}).get("boundary") == "administrative"][0])

# ------------------------------------------------------------------ halaman
fig = plt.figure(figsize=(PAGE_W / 2.54, PAGE_H / 2.54))
def cm_ax(x, y, w, h, **kw):
    return fig.add_axes([x / PAGE_W, y / PAGE_H, w / PAGE_W, h / PAGE_H], **kw)

page = cm_ax(0, 0, PAGE_W, PAGE_H); page.set_xlim(0, PAGE_W); page.set_ylim(0, PAGE_H); page.axis("off")
INK = "#1f2937"
page.add_patch(Rectangle((0, 0), PAGE_W, PAGE_H, fc=KRIM, ec="none", zorder=-10))
page.add_patch(Rectangle((1.2, 1.2), PAGE_W - 2.4, PAGE_H - 2.4, fill=False, lw=5, ec=HIJAU))
page.add_patch(Rectangle((1.6, 1.6), PAGE_W - 3.2, PAGE_H - 3.2, fill=False, lw=2, ec=EMAS))

# area kiri: strip foto atas, peta, strip foto bawah
PW = 29.4; PX = PAGE_W - 3.2 - PW
FW, FH = PRESET["FW"], PRESET["FH"]
FOTO_ATAS_Y, FOTO_BAWAH_Y = TOP - FH + 0.4, BOT + 0.2
MX = 4.2; MW = PX - 2.0 - MX
MY = FOTO_BAWAH_Y + FH + 2.2; MH = FOTO_ATAS_Y - 2.4 - MY
_all = RW   # fokus RW 02 saja (luar RW diredam)
ux0, ux1 = min(p[0] for p in _all), max(p[0] for p in _all)
uy0, uy1 = min(p[1] for p in _all), max(p[1] for p in _all)
if SKALA_CETAK is None:   # skala cetak bulat (kelipatan 250) yang memuat semua batas + margin 5%
    need = max((ux1 - ux0) * 1.2 / MW * 100, (uy1 - uy0) * 1.2 / MH * 100) / F
    SKALA_CETAK = next(v for v in (500, 750, 1000, 1250, 1500, 2000, 2500, 3000, 4000, 5000, 7500, 10000) if v >= need)
SKALA = SKALA_CETAK * F   # skala di kanvas desain
CX, CY = (ux0 + ux1) / 2, (uy0 + uy1) / 2
mx0 = CX - MW * SKALA / 200; my0 = CY - MH * SKALA / 200
mx1 = mx0 + MW * SKALA / 100; my1 = my0 + MH * SKALA / 100
def m2cm(x, y): return MX + (x - mx0) / SKALA * 100, MY + (y - my0) / SKALA * 100

ax = cm_ax(MX, MY, MW, MH)
ax.set_xlim(mx0, mx1); ax.set_ylim(my0, my1); ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
ax.set_facecolor("#eef0e6")
for s in ax.spines.values(): s.set_lw(2.5); s.set_color(INK); s.set_zorder(30)

# ------------------------------------------------------------------ latar
if CITRA:
    meta = json.load(open(J("data/citra_meta.json")))
    mos = Image.open(next(J("data", f) for f in ("citra_z19.jpg", "citra_z19.png") if os.path.exists(J("data", f))))
    def to_px(x, y):  # UTM -> piksel mosaik (Web Mercator)
        lat, lon = inv_utm(x, y); n = 2 ** meta["z"]
        tx = (lon + 180) / 360 * n
        ty = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
        return (tx - meta["tx0"]) * 256, (ty - meta["ty0"]) * 256
    RES = SKALA / 100 * 2.54 / 220  # m per piksel -> ~220 dpi di kertas
    W_px, H_px = int((mx1 - mx0) / RES), int((my1 - my0) / RES)
    # transformasi afin (area kecil -> sangat akurat), fit dari grid 5x5 titik
    src, dst = [], []
    for i in np.linspace(0, W_px, 5):
        for j in np.linspace(0, H_px, 5):
            src.append([i, j, 1]); dst.append(to_px(mx0 + i * RES, my1 - j * RES))
    coef, *_ = np.linalg.lstsq(np.array(src), np.array(dst), rcond=None)
    img = mos.transform((W_px, H_px), Image.AFFINE, tuple(coef[:, 0]) + tuple(coef[:, 1]), resample=Image.BICUBIC)
    img = ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(1.2)).enhance(1.06)
    # luar batas RW: blur + sedikit gelap
    from PIL import ImageDraw, ImageFilter
    m = Image.new("L", img.size, 0)
    ImageDraw.Draw(m).polygon([((x - mx0) / RES, (my1 - y) / RES) for x, y in RW], fill=255)
    m = m.filter(ImageFilter.GaussianBlur(4))
    luar = img.filter(ImageFilter.GaussianBlur(22))     # luar RW: blur kuat, pucat, gelap
    luar = ImageEnhance.Brightness(ImageEnhance.Color(luar).enhance(0.35)).enhance(0.75)
    img = Image.composite(img, luar, m)
    ax.imshow(np.asarray(img), extent=(mx0, mx1, my0, my1), zorder=0, interpolation="lanczos")
else:
    LAND = {"residential": "#eef0e6", "grass": "#cfe8b4", "cemetery": "#c8dcc0", "commercial": "#f2e3dc",
            "retail": "#f2e3dc", "farmland": "#e3efc0", "meadow": "#d6ebb6", "religious": "#e5e1d3"}
    polys, cols = [], []
    for e in ktx:
        t = e.get("tags", {})
        if "landuse" in t and t["landuse"] in LAND and "geometry" in e:
            polys.append(geom(e)); cols.append(LAND[t["landuse"]])
    ax.add_collection(PolyCollection(polys, facecolors=cols, edgecolors="none", zorder=1))
    ax.add_patch(Polygon(RW, closed=True, fc="#e3f1d0", ec="none", zorder=1.5))

water = [geom(e) for e in ktx if "waterway" in e.get("tags", {}) and "geometry" in e]
ax.add_collection(LineCollection(water, colors=ST["sungai"][0], lw=ST["sungai"][1], zorder=2, capstyle="round",
                                 alpha=0.8 if CITRA else 1))

if not CITRA:
    bld, bld_c = [], []
    for e in ktx:
        if "building" in e.get("tags", {}) and "geometry" in e:
            g = geom(e); bld.append(g)
            bld_c.append("#e9c9a6" if RW_PATH.contains_point(centroid(g)) else "#ddd5cc")
    ax.add_collection(PolyCollection(bld, facecolors=bld_c, edgecolors="#9c7a5b", lw=0.4, zorder=3))

BESAR = {"primary", "primary_link", "secondary", "secondary_link", "tertiary", "tertiary_link", "trunk"}
KECIL = {"residential", "living_street", "unclassified", "service"}
SETAPAK = {"footway", "path", "pedestrian", "steps", "track", "cycleway"}
roads = {"besar": [], "kecil": [], "setapak": []}
named = {}
for e in ktx:
    t = e.get("tags", {}); h = t.get("highway")
    if not h or "geometry" not in e: continue
    g = geom(e)
    k = "besar" if h in BESAR else "kecil" if h in KECIL else "setapak" if h in SETAPAK else None
    if not k: continue
    roads[k].append(g)
    if t.get("name"): named.setdefault(t["name"], []).append((k, g))
LW = 72 / 2.54 / SKALA * 100   # pt per meter di kertas
if CITRA:  # luar RW di-blur -> jalan setapak hanya digambar di dalam RW
    roads["setapak"] = [g for g in roads["setapak"] if any(RW_PATH.contains_point(p) for p in g)]
_lc = ax.add_collection(LineCollection(roads["setapak"], colors=ST["setapak"][0], lw=ST["setapak"][1],
                                 linestyles=(0, (3, 2)), zorder=4))
if CITRA: _lc.set_clip_path(PathPatch(RW_PATH, transform=ax.transData))
if CITRA:
    roads["kecil"] = [g for g in roads["kecil"] if any(RW_PATH.contains_point(p) for p in g)]
    _lc = ax.add_collection(LineCollection(roads["kecil"], colors=ST["kecil"][1], lw=ST["kecil"][2], zorder=5, capstyle="round"))
    _lc.set_clip_path(PathPatch(RW_PATH, transform=ax.transData))
    ax.add_collection(LineCollection(roads["besar"], colors=ST["besar"][0], lw=ST["besar"][2] + 2, zorder=6, capstyle="round"))
    ax.add_collection(LineCollection(roads["besar"], colors=ST["besar"][1], lw=ST["besar"][2], zorder=7, capstyle="round"))
else:
    ax.add_collection(LineCollection(roads["kecil"], colors=ST["kecil"][0], lw=5 * LW + 1.6, zorder=4, capstyle="round"))
    ax.add_collection(LineCollection(roads["kecil"], colors=ST["kecil"][1], lw=5 * LW, zorder=5, capstyle="round"))
    ax.add_collection(LineCollection(roads["besar"], colors=ST["besar"][0], lw=11 * LW + 2, zorder=6, capstyle="round"))
    ax.add_collection(LineCollection(roads["besar"], colors=ST["besar"][1], lw=11 * LW, zorder=7, capstyle="round"))

# masker di luar RW
frame = [(mx0 - 50, my0 - 50), (mx1 + 50, my0 - 50), (mx1 + 50, my1 + 50), (mx0 - 50, my1 + 50), (mx0 - 50, my0 - 50)]
mask = Path(frame + list(reversed(RW)),
            [Path.MOVETO] + [Path.LINETO] * 3 + [Path.CLOSEPOLY] + [Path.MOVETO] + [Path.LINETO] * (len(RW) - 2) + [Path.CLOSEPOLY])
if True:   # redam semua yang di luar RW (jalan, sungai, bangunan)
    ax.add_patch(PathPatch(mask, fc=ST["mask"][0], ec="none", alpha=ST["mask"][1], zorder=8))

# batas kelurahan & RW
for r in KEL:
    xs, ys = zip(*r)
    ax.plot(xs, ys, color=ST["kel"], lw=3, ls=(0, (8, 3, 2, 3)), zorder=9, alpha=0.6)
xs, ys = zip(*(RW + [RW[0]]))
if CITRA:
    ax.plot(xs, ys, color="black", lw=9, alpha=0.5, zorder=9.4, solid_joinstyle="round")
    ax.plot(xs, ys, color=ST["rw_out"], lw=6, zorder=9.5, solid_joinstyle="round")
else:
    ax.plot(xs, ys, color=ST["rw_out"], lw=11, zorder=9.5, solid_joinstyle="round")
    ax.plot(xs, ys, color=ST["rw_in"], lw=4, ls=ST["rw_dash"], zorder=9.6)

# label jalan
halo = [pe.withStroke(linewidth=4, foreground=ST["halo"])]
def seg_len(g): return sum(math.dist(g[i], g[i + 1]) for i in range(len(g) - 1))
MG = 12  # margin label dari tepi (m)
def inview(p, mg=MG): return mx0 + mg < p[0] < mx1 - mg and my0 + mg < p[1] < my1 - mg
for name, items in named.items():
    k, g = max(items, key=lambda it: seg_len([p for p in it[1] if inview(p)] or [(0, 0)]))
    g = [p for p in g if inview(p, 18)]
    if len(g) < 2 or seg_len(g) < 45: continue
    half, acc = seg_len(g) / 2, 0
    for i in range(len(g) - 1):
        d = math.dist(g[i], g[i + 1])
        if acc + d >= half:
            f = (half - acc) / d; px = g[i][0] + f * (g[i + 1][0] - g[i][0]); py = g[i][1] + f * (g[i + 1][1] - g[i][1])
            ang = math.degrees(math.atan2(g[i + 1][1] - g[i][1], g[i + 1][0] - g[i][0]))
            break
        acc += d
    if ang > 90: ang -= 180
    if ang < -90: ang += 180
    big = k == "besar"
    dekat = min(math.dist((px, py), q) for q in RW)
    if not RW_PATH.contains_point((px, py)) and (not big or dekat > 70): continue
    ax.text(px, py, name, rotation=ang, rotation_mode="anchor", ha="center", va="center",
            fontsize=18 if big else 13, fontweight="bold" if big else "normal", style="normal" if big else "italic",
            color=ST["lbl_big"] if big else ST["lbl_small"], zorder=11, path_effects=halo)
water_named = [] and [e for e in ktx if e.get("tags", {}).get("waterway") == "river" and e["tags"].get("name")]
if water_named:
    g = max((geom(e) for e in water_named), key=seg_len)
    g = [p for p in g if inview(p, 40)]
    if len(g) > 2:
        p0, p1 = g[len(g) // 2 - 1], g[len(g) // 2]
        ang = math.degrees(math.atan2(p1[1] - p0[1], p1[0] - p0[0])); ang = ang - 180 if ang > 90 else ang + 180 if ang < -90 else ang
        ax.text(p1[0] - 10, p1[1], water_named[0]["tags"]["name"], rotation=ang, rotation_mode="anchor", color=ST["sungai_lbl"],
                fontsize=15, style="italic", fontweight="bold", zorder=11, ha="right", path_effects=halo)

# label RW di tengah (watermark)
ax.text(RCX, RCY, "RW 08", ha="center", va="center", fontsize=80, fontweight="bold",
        color="white" if CITRA else HIJAU, alpha=0.28 if CITRA else 0.16, zorder=8.5)

# ------------------------------------------------------------------ fasilitas (POI)
def kategori(t):
    a = t.get("amenity", ""); n = t.get("name", "").lower()
    if a == "place_of_worship" or "masjid" in n or "mushola" in n: return "Tempat Ibadah"
    if a in ("clinic", "hospital", "doctors", "pharmacy") or "posyandu" in n: return "Kesehatan"
    if a in ("school", "kindergarten", "college", "university"): return "Pendidikan"
    if t.get("office") == "government" or a in ("townhall", "police"): return "Pemerintahan"
    if a == "marketplace" or "shop" in t: return "Ekonomi"
    return "Lainnya"

pois = []
for e in kel:
    t = e.get("tags", {})
    if not t.get("name") or "highway" in t or e["type"] == "relation": continue
    if not any(k in t for k in ("amenity", "shop", "office", "leisure", "tourism")): continue
    if "place" in t or t["name"] in ABAIKAN: continue
    p = utm(e["lat"], e["lon"]) if e["type"] == "node" else centroid(geom(e))
    if not inview(p, 10): continue
    nm = t["name"]; nm = nm[0].upper() + nm[1:]
    nm = " ".join(w.capitalize() if w.islower() else w for w in nm.split())
    pois.append(dict(name=nm, kat=kategori(t), x=p[0], y=p[1], dalam=RW_PATH.contains_point(p)))
for p in pois:
    p["foto"] = FOTO_OSM.get(p["name"], ""); p["alamat"] = ALAMAT_OSM.get(p["name"], "")
    p["name"] = GANTI_NAMA.get(p["name"], p["name"])
# titik survei lapangan (data/lokasi.json, dari link Google Maps) -> dianggap dalam RW
for L in json.load(open(J("data/lokasi.json"), encoding="utf-8")):
    x, y = utm(L["lat"], L["lon"])
    kt = L.get("kat") or ("Keamanan" if "Kamling" in L["nama"] else "Kebersihan" if "Sampah" in L["nama"] else "Lainnya")
    pois.append(dict(name=L["nama"], kat=kt, x=x, y=y, dalam=True, foto=L.get("foto", ""), alamat=L.get("alamat", "")))
pois = [p for p in pois if p["dalam"]]   # hanya fasilitas dalam RW 02
if os.path.exists(GPKG):   # titik dari proyek QGIS menggantikan semua di atas
    _t = pyogrio.raw.read(GPKG, layer="titik_fasilitas"); _a = dict(zip(_t[0]["fields"], _t[3])); pois = []
    for i, w in enumerate(_t[2]):
        if w is None: continue
        g = shapely.from_wkb(w); x, y = utm(g.y, g.x)
        kt = _a["kategori"][i] if _a["kategori"][i] in KATEGORI else "Lainnya"
        pois.append(dict(name=str(_a["nama"][i] or ""), kat=kt, x=x, y=y, dalam=True, foto=str(_a["foto"][i] or ""),
                         alamat=str(_a["keterangan"][i] or ""), sumber=str(_a["sumber"][i] or "")))
pois.sort(key=lambda p: (not p["dalam"], list(KATEGORI).index(p["kat"]), p["name"]))
for i, p in enumerate(pois, 1): p["no"] = i
# posisi simbol di kertas (cm); yang terlalu dekat didorong menjauh biar gak numpuk
for p in pois: p["cx"], p["cy"] = m2cm(p["x"], p["y"])
JARAK = 2.05
for _ in range(60):
    gerak = False
    for i, a in enumerate(pois):
        for b in pois[i + 1:]:
            dx, dy = b["cx"] - a["cx"], b["cy"] - a["cy"]; d = math.hypot(dx, dy)
            if d < JARAK:
                if d < 1e-6: dx, dy, d = 1.0, 0.0, 1.0
                k = (JARAK - d) / 2 / d
                a["cx"] -= dx * k; a["cy"] -= dy * k; b["cx"] += dx * k; b["cy"] += dy * k; gerak = True
    if not gerak: break
json.dump([dict(no=p["no"], nama=p["name"], kat=p["kat"], warna=KATEGORI[p["kat"]], dalam=bool(p["dalam"]), foto=p.get("foto", ""), alamat=p.get("alamat", ""), sumber=p.get("sumber", ""),
                lat=round(inv_utm(p["x"], p["y"])[0], 7), lon=round(inv_utm(p["x"], p["y"])[1], 7)) for p in pois],
          open(J("data/pois.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)

# overlay (di atas peta) untuk garis penunjuk, simbol, dan bingkai foto -> koordinat cm halaman
ov = cm_ax(0, 0, PAGE_W, PAGE_H); ov.set_xlim(0, PAGE_W); ov.set_ylim(0, PAGE_H); ov.axis("off")

# foto: fasilitas dalam RW dulu, lalu yang terdekat ke RW; dibagi atas/bawah menurut posisi
foto = [p for p in pois if p["foto"] and FOTO(p["foto"])][:8]
if len(foto) < 8:   # belum ada foto -> bingkai kosong untuk titik lain (tersebar), nanti tinggal diisi
    sisa = [p for p in pois if p not in foto]
    while sisa and len(foto) < 8:   # ambil yang paling jauh dari titik yang sudah dipilih biar menyebar
        p = max(sisa, key=lambda q: min([math.dist((q["x"], q["y"]), (r["x"], r["y"])) for r in foto] or [1e9]))
        foto.append(p); sisa.remove(p)
def slots(n):
    if not n: return []
    gap = (MW - n * FW) / (n + 1)
    return [MX + gap + i * (FW + gap) for i in range(n)]

def _silang(a, b, c, d):
    o = lambda p, q, r: (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return o(a, b, c) * o(a, b, d) < 0 and o(c, d, a) * o(c, d, b) < 0

def _biaya(atas, bawah):   # panjang total garis + hukuman garis bersilang
    seg = []
    for row, y0 in ((atas, FOTO_ATAS_Y), (bawah, FOTO_BAWAH_Y + FH)):
        for p, x0 in zip(row, slots(len(row))):
            seg.append(((x0 + FW / 2, y0), m2cm(p["x"], p["y"])))
    c = sum(math.dist(*s) for s in seg)
    return c + 40 * sum(_silang(*seg[i], *seg[j]) for i in range(len(seg)) for j in range(i + 1, len(seg)))

from itertools import combinations
n_atas = (len(foto) + 1) // 2
best = None
for na in {n_atas, len(foto) // 2}:
    for idx in combinations(range(len(foto)), na):
        A = sorted([foto[i] for i in idx], key=lambda p: p["x"])
        B = sorted([p for i, p in enumerate(foto) if i not in idx], key=lambda p: p["x"])
        c = _biaya(A, B)
        if best is None or c < best[0]: best = (c, A, B)
_, atas, bawah = best

for row, y0 in ((atas, FOTO_ATAS_Y), (bawah, FOTO_BAWAH_Y)):
    for p, x0 in zip(row, slots(len(row))):
        cap = 2.4
        px, py = p["cx"], p["cy"]
        ex, ey = x0 + FW / 2, (y0 if row is atas else y0 + FH)
        ov.plot([ex, px], [ey, py], color="white" if CITRA else INK, lw=3.2 if CITRA else 0, zorder=1, solid_capstyle="round")
        ov.plot([ex, px], [ey, py], color=INK, lw=1.4, zorder=1.1)
        ov.add_patch(Rectangle((x0 + 0.25, y0 - 0.25), FW, FH, fc="#00000040", ec="none", zorder=2))
        ov.add_patch(Rectangle((x0, y0), FW, FH, fc="white", ec=HIJAU, lw=2.4, zorder=3))
        ov.add_patch(Rectangle((x0, y0), FW, 0.3, fc=EMAS, ec="none", zorder=3.5))
        img = FOTO(p["foto"])
        ix0, iy0, iw, ih = x0 + 0.4, y0 + cap, FW - 0.8, FH - cap - 0.4
        if os.path.exists(img):
            from PIL import ImageOps
            pim = ImageOps.exif_transpose(Image.open(img)).convert("RGB"); pim.thumbnail((1400, 1400)); im = np.asarray(pim)
            ih_px, iw_px = im.shape[:2]; r = iw / ih
            if iw_px / ih_px > r:  # crop tengah
                nw = int(ih_px * r); o = (iw_px - nw) // 2; im = im[:, o:o + nw]
            else:
                nh = int(iw_px / r); o = (ih_px - nh) // 2; im = im[o:o + nh]
            ov.imshow(im, extent=(ix0, ix0 + iw, iy0, iy0 + ih), zorder=4, interpolation="lanczos")
        else:
            ov.add_patch(Rectangle((ix0, iy0), iw, ih, fc="#e5e7eb", ec="#9ca3af", lw=1, ls="--", zorder=4))
            ov.text(ix0 + iw / 2, iy0 + ih / 2, "FOTO\n(belum ada)", ha="center", va="center",
                    fontsize=14, color="#6b7280", zorder=5)
        ov.add_patch(Circle((x0 + 1.1, y0 + cap / 2), 0.7, fc=KATEGORI[p["kat"]], ec="white", lw=1.5, zorder=5))
        ov.text(x0 + 1.1, y0 + cap / 2, str(p["no"]), ha="center", va="center", color="white", fontsize=11,
                fontweight="bold", zorder=6)
        ov.text(x0 + FW / 2 + 0.7, y0 + cap / 2, p["name"], ha="center", va="center", fontsize=13, fontweight="bold",
                color=INK, zorder=5)
ov.set_xlim(0, PAGE_W); ov.set_ylim(0, PAGE_H)

for p in pois:
    cx, cy = p["cx"], p["cy"]
    tx, ty = m2cm(p["x"], p["y"])
    if math.hypot(cx - tx, cy - ty) > 0.3:   # simbol digeser -> garis kecil ke lokasi asli
        ov.plot([tx, cx], [ty, cy], color="white", lw=1.6, zorder=6.5); ov.add_patch(Circle((tx, ty), 0.18, fc="white", ec=INK, lw=0.8, zorder=6.6))
    ov.add_patch(Circle((cx, cy), 0.95, fc=KATEGORI[p["kat"]], ec="white", lw=2.5, zorder=7))
    ov.text(cx, cy, str(p["no"]), ha="center", va="center", color="white", fontsize=15, fontweight="bold", zorder=8)

# grid koordinat (DMS) di tepi
def dms(v, ax_):
    h = ("S" if v < 0 else "U") if ax_ == "lat" else ("T" if v >= 0 else "B")
    v = abs(v); d = int(v); m = int((v - d) * 60); s = round(((v - d) * 60 - m) * 60)
    if s == 60: s = 0; m += 1
    return f"{d}°{m:02d}'{s:02d}\" {h}"
la0, lo0 = inv_utm(mx0, my0); la1, lo1 = inv_utm(mx1, my1)
step = 5 / 3600
v = math.ceil(lo0 / step) * step
while v < lo1:
    x, _ = utm((la0 + la1) / 2, v)
    for yy, d in ((my0, 8), (my1, -8)):
        ax.plot([x, x], [yy, yy + d], color=INK, lw=1.5, clip_on=False, zorder=31)
    page.text(MX + (x - mx0) / SKALA * 100, MY - 0.35, dms(v, "lon"), ha="center", va="top", fontsize=11)
    page.text(MX + (x - mx0) / SKALA * 100, MY + MH + 0.3, dms(v, "lon"), ha="center", va="bottom", fontsize=11)
    v += step
v = math.ceil(la0 / step) * step
while v < la1:
    _, y = utm(v, (lo0 + lo1) / 2)
    for xx, d in ((mx0, 8), (mx1, -8)):
        ax.plot([xx, xx + d], [y, y], color=INK, lw=1.5, clip_on=False, zorder=31)
    page.text(MX - 0.4, MY + (y - my0) / SKALA * 100, dms(v, "lat"), ha="right", va="center", fontsize=11, rotation=90)
    page.text(MX + MW + 0.4, MY + (y - my0) / SKALA * 100, dms(v, "lat"), ha="left", va="center", fontsize=11, rotation=90)
    v += step

# ------------------------------------------------------------------ panel kanan
def box(y, h):
    page.add_patch(Rectangle((PX, y), PW, h, fc="white", ec=HIJAU, lw=2.4, zorder=-5))
    page.add_patch(Rectangle((PX, y), PW, h, fill=False, ec=HIJAU, lw=2.4, zorder=20))
def head(y, txt):
    page.add_patch(Rectangle((PX, y - 1.6), PW, 1.6, fc=HIJAU, ec=HIJAU, lw=2))
    page.add_patch(Rectangle((PX, y - 1.6), PW, 0.22, fc=EMAS, ec="none"))
    page.text(PX + PW / 2, y - 0.8, txt, ha="center", va="center", color="white", fontsize=17, fontweight="bold")

# judul
TY = TOP; TH = PRESET["TH"]; k = TH / 13.2
page.add_patch(Rectangle((PX, TY - TH), PW, TH, fc=HIJAU, ec=HIJAU, lw=2))
page.add_patch(Rectangle((PX, TY - TH), PW, 0.45, fc=EMAS, ec="none"))
page.text(PX + PW / 2, TY - 2.6 * k, JUDUL[0], ha="center", va="center", color="white", fontsize=38, fontweight="bold")
page.text(PX + PW / 2, TY - 5.5 * k, JUDUL[1], ha="center", va="center", color=EMAS, fontsize=27, fontweight="bold")
page.text(PX + PW / 2, TY - 8.3 * k, f"Kampung {REC['kampung'].title()}  •  Luas ± {LUAS / 10000:.2f} ha".replace(".", ","),
          ha="center", va="center", color="white", fontsize=17, fontweight="bold")
for i, f in enumerate(LOGO):   # logo bulat kiri & kanan judul
    if not os.path.exists(J(f)): continue
    r = 2.35 * k; cx = PX + 0.6 + r if i == 0 else PX + PW - 0.6 - r; cy = TY - 4.0 * k
    page.add_patch(Circle((cx, cy), r, fc="white", ec="white", lw=2, zorder=5))
    lim = np.asarray(Image.open(J(f)).convert("RGB").resize((500, 500)))
    ii = page.imshow(lim, extent=(cx - r * .97, cx + r * .97, cy - r * .97, cy + r * .97), zorder=6, interpolation="lanczos")
    ii.set_clip_path(Circle((cx, cy), r * .97, transform=page.transData))
page.set_xlim(0, PAGE_W); page.set_ylim(0, PAGE_H)
page.text(PX + PW / 2, TY - 10.9 * k, SUBJUDUL, ha="center", va="center", color="white", fontsize=17, linespacing=1.4)

# arah utara + skala
SH = PRESET["SH"]; SY = TY - TH; box(SY - SH, SH)
a = SH / 10.6   # ukuran panah utara ikut tinggi kotak
nx, ny = PX + 5, SY - SH / 2 - 0.4 * a
page.add_patch(Polygon([(nx, ny + 3.6 * a), (nx - 1.8 * a, ny - 2.6 * a), (nx, ny - 1.4 * a)], fc=HIJAU, ec=HIJAU))
page.add_patch(Polygon([(nx, ny + 3.6 * a), (nx + 1.8 * a, ny - 2.6 * a), (nx, ny - 1.4 * a)], fc="white", ec=INK, lw=1.5))
page.text(nx, ny + 4.0 * a, "U", ha="center", va="bottom", fontsize=24, fontweight="bold")
page.text(PX + 18.4, SY - 1.9, f"SKALA 1 : {SKALA_CETAK:,}".replace(",", "."), ha="center", va="center", fontsize=20, fontweight="bold")
# panjang segmen = angka bulat (meter) yang mendekati 4 cm di kanvas
seg_m = min((10, 20, 25, 50, 60, 75, 100, 150, 200, 250, 500), key=lambda v: abs(v / (SKALA / 100) - 4.0))
bx, by, seg = PX + 10.2, SY - 4.6, seg_m / (SKALA / 100)
for i in range(4):
    page.add_patch(Rectangle((bx + i * seg, by), seg, 0.55, fc=INK if i % 2 == 0 else "white", ec=INK, lw=1.2))
    page.text(bx + i * seg, by + 0.8, f"{i * seg_m}", ha="center", fontsize=12)
page.text(bx + 4 * seg, by + 0.8, f"{4 * seg_m} m", ha="center", fontsize=12)
page.text(PX + 18.4, SY - SH + 2.7, f"Proyeksi : Transverse Mercator  •  UTM Zona 49S\nDatum : WGS 1984\nKode Wilayah RW : {REC['rw_id']}",
          ha="center", va="center", fontsize=12.5, linespacing=1.5)

# legenda
LY = SY - SH; head(LY, "LEGENDA")
y = LY - 2.8
def sub(t, xx=PX + 1.0):
    page.text(xx, y, t, fontsize=14.5, fontweight="bold", va="center")
def item_line(xx, yy, label, **kw):
    for k in kw.pop("layers", [kw]):
        page.plot([xx, xx + 2.6], [yy, yy], solid_capstyle="butt", **k)
    page.text(xx + 3.2, yy, label, fontsize=15, va="center")
def sample_bg(xx, yy):  # latar contoh simbol di mode citra
    if CITRA: page.add_patch(Rectangle((xx - 0.15, yy - 0.5), 2.9, 1.0, fc="#3f4a3a", ec="none"))
sub("Batas Wilayah"); sub("Jaringan Jalan", PX + 15.2)
y -= 1.5
for xx in (PX + 1, PX + 15.2): sample_bg(xx, y)
if CITRA:
    item_line(PX + 1, y, "Batas RW 08", layers=[dict(color="black", lw=8, alpha=.5), dict(color="#fde047", lw=5)])
    item_line(PX + 15.2, y, "Jalan Besar", layers=[dict(color="#3b1d00", lw=7), dict(color="#f59e0b", lw=5)])
else:
    item_line(PX + 1, y, "Batas RW 08", layers=[dict(color=EMAS, lw=9), dict(color=HIJAU, lw=3.5, ls=(0, (6, 2.5)))])
    item_line(PX + 15.2, y, "Jalan Besar", layers=[dict(color="#8c5a00", lw=10), dict(color="#fbc94a", lw=7.5)])
y -= 1.3
for xx in (PX + 1, PX + 15.2): sample_bg(xx, y)
item_line(PX + 1, y, "Batas Kelurahan", color=ST["kel"], lw=2.5, ls=(0, (8, 3, 2, 3)))
if CITRA:
    item_line(PX + 15.2, y, "Jalan Kecil / Gang", color="white", lw=2.2)
else:
    item_line(PX + 15.2, y, "Jalan Kecil / Gang", layers=[dict(color="#7a7a7a", lw=6), dict(color="white", lw=4)])
y -= 1.3
sample_bg(PX + 15.2, y)
if CITRA:
    page.add_patch(Rectangle((PX + 1, y - 0.45), 2.6, 0.9, fc="#00000060", ec=INK, lw=0.8))
    page.text(PX + 4.2, y, "Luar wilayah RW", fontsize=15, va="center")
    item_line(PX + 15.2, y, "Jalan Setapak", color="white", lw=1.5, ls=(0, (3, 2)))
else:
    page.add_patch(Rectangle((PX + 1, y - 0.45), 2.6, 0.9, fc="#e9c9a6", ec="#9c7a5b"))
    page.text(PX + 4.2, y, "Bangunan", fontsize=15, va="center")
    item_line(PX + 15.2, y, "Jalan Setapak", color="#8a8a8a", lw=1.5, ls=(0, (3, 2)))
y -= 1.3
item_line(PX + 1, y, "Sungai", color=ST["sungai"][0], lw=5)
y -= 1.9
sub("Fasilitas Umum")
y -= 1.5
xk = PX + 1
for k, c in KATEGORI.items():
    if not any(p["kat"] == k for p in pois): continue
    page.add_patch(Circle((xk + 0.45, y), 0.42, fc=c, ec="white", lw=1))
    page.text(xk + 1.2, y, k, fontsize=14, va="center")
    xk += 9.4
    if xk > PX + PW - 8: xk = PX + 1; y -= 1.15
if xk != PX + 1: y -= 1.15
y -= 0.5
daftar = [(p["no"], p["kat"], p["name"], p["dalam"]) for p in pois] + [(None, "Kebersihan", nm, True) for nm in MENYUSUL]
nbar = (len(daftar) + 1) // 2; y_top = y
for j, (no, kt, nm, dl) in enumerate(daftar):   # 2 kolom
    xx = PX + (1.5 if j < nbar else 1.5 + PW / 2 - 0.3); y = y_top - (j % nbar) * PRESET["PL"]
    if no is None:
        page.add_patch(Circle((xx, y), 0.5, fc="white", ec=KATEGORI[kt], lw=1.5, ls="--"))
        page.text(xx, y, "?", ha="center", va="center", color=KATEGORI[kt], fontsize=10, fontweight="bold")
        page.text(xx + 1.0, y, nm + " (menyusul)", fontsize=12.5, va="center", color="#6b7280", style="italic", linespacing=1.0)
        continue
    page.add_patch(Circle((xx, y), 0.5, fc=KATEGORI[kt], ec="white", lw=1))
    page.text(xx, y, str(no), ha="center", va="center", color="white", fontsize=10, fontweight="bold")
    page.text(xx + 1.0, y, nm + ("" if dl else " (luar RW)"), fontsize=12.5, va="center", color=INK if dl else "#6b7280")
y = y_top - nbar * PRESET["PL"]
for p in []:
    page.add_patch(Circle((PX + 1.5, y), 0.5, fc=KATEGORI[p["kat"]], ec="white", lw=1))
    page.text(PX + 1.5, y, str(p["no"]), ha="center", va="center", color="white", fontsize=10, fontweight="bold")
    page.text(PX + 2.5, y, p["name"] + ("" if p["dalam"] else "  (luar RW)"), fontsize=15, va="center",
              color=INK if p["dalam"] else "#6b7280")
    y -= PRESET["PL"]
for nm in []:
    page.add_patch(Circle((PX + 1.5, y), 0.5, fc="white", ec=KATEGORI["Kebersihan"], lw=1.5, ls="--"))
    page.text(PX + 1.5, y, "?", ha="center", va="center", color=KATEGORI["Kebersihan"], fontsize=10, fontweight="bold")
    page.text(PX + 2.5, y, nm + "  (lokasi menyusul)", fontsize=15, va="center", color="#6b7280", style="italic")
    y -= PRESET["PL"]
LH = LY - y + 0.2; box(LY - LH, LH)

# inset lokasi (mengisi sisa ruang)
TTD_H, SRH = PRESET["TTD_H"], PRESET["SRH"]
IY = LY - LH; IH = IY - BOT - TTD_H - SRH; box(IY - IH, IH); head(IY, "LOKASI DI KEMANTREN UMBULHARJO")
iax = cm_ax(PX + 0.6, IY - IH + 0.5, PW - 1.2, IH - 2.6); iax.set_aspect("equal"); iax.axis("off")
kelr = [e for e in ins if e["type"] == "relation" and e["tags"].get("admin_level") == "7"]
WARNA_KEL = {"Semaki": "#fde7a3"}
for e in kelr:
    for r in rings_from_relation(e):
        iax.add_patch(Polygon(r, fc=WARNA_KEL.get(e["tags"]["name"], "#e5e7eb"), ec="#6b7280", lw=1))
        cx, cy = centroid(r)
        iax.text(cx, cy, e["tags"]["name"], ha="center", va="center", fontsize=13, fontweight="bold", color="#374151")
iax.add_patch(Polygon(RW, fc=HIJAU, ec=HIJAU, lw=1.5))
iax.autoscale_view()

# sumber data
SRY = IY - IH; box(SRY - SRH, SRH); head(SRY, "SUMBER DATA")
sumber = ("1. Batas RW 08 : Geoportal Kota Yogyakarta\n"
          "2. Jalan, sungai, fasilitas : © kontributor OpenStreetMap\n")
sumber += ("3. Citra satelit : Esri World Imagery (Maxar, Earthstar)\n" if CITRA
           else "3. Bangunan : © kontributor OpenStreetMap\n")
sumber += f"4. Fasilitas : Geoportal Kota Yogyakarta & OpenStreetMap, {TAHUN}"
page.text(PX + 1, SRY - 2.2, sumber, fontsize=12, va="top", linespacing=1.45)

TTY = SRY - SRH; box(BOT, TTY - BOT)
for i, (a, b) in enumerate(TTD):
    cx = PX + PW / 4 + i * PW / 2
    page.text(cx, TTY - 0.8, a, ha="center", va="top", fontsize=12, linespacing=1.3)
    page.text(cx, BOT + 1.2, b, ha="center", va="bottom", fontsize=12)

os.makedirs(J("output"), exist_ok=True)
out = J("output", f"Peta_RW08_Semaki_{UKURAN}cm_{MODE}")
fig.savefig(out + ".pdf", dpi=250 * F)            # ~250 dpi pada ukuran cetak
fig.savefig(out + ".png", dpi=150 * F)           # 150 dpi pada ukuran cetak
if F != 1:   # perkecil halaman PDF ke ukuran cetak sebenarnya
    from pypdf import PdfReader, PdfWriter
    w = PdfWriter(clone_from=out + ".pdf"); w.pages[0].scale_by(F)
    with open(out + ".pdf", "wb") as fh: w.write(fh)
print(f"ukuran {UKURAN} cm, skala 1:{SKALA_CETAK}")
print("POI:", [(p["no"], p["name"], p["dalam"]) for p in pois])
print("selesai:", out)
