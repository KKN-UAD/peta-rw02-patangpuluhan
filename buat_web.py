"""Peta digital (web) RW 02 Patangpuluhan -> folder web/ (siap GitHub Pages).
Jalankan setelah buat_peta.py (butuh data/pois.json).  py buat_web.py"""
import json, os, shutil
from PIL import Image, ImageOps

D = os.path.dirname(os.path.abspath(__file__))
J = lambda *a: os.path.join(D, *a)
ASET = "drive-download-20261115T153336Z-1-001"
OUT = J("web")
MENYUSUL = []
FOTO = lambda f: next((p for p in (J("qgis", f), J(ASET, f)) if f and os.path.isfile(p)), "")
os.makedirs(J("web", "foto"), exist_ok=True)

r6 = lambda v: round(v, 6)
line = lambda e: [[r6(p["lon"]), r6(p["lat"])] for p in e["geometry"]]
fc = lambda feats: {"type": "FeatureCollection", "features": feats}
F = lambda geom, **props: {"type": "Feature", "geometry": geom, "properties": props}

kel = json.load(open(J("data/kelurahan.json"), encoding="utf-8"))["elements"]
kon = json.load(open(J("data/konteks.json"), encoding="utf-8"))["elements"]
rw = json.load(open(J("data/rw_latlon.json")))
pois = json.load(open(J("data/pois.json"), encoding="utf-8"))

# batas
rel = next(e for e in kel if e["type"] == "relation")
batas_kel = fc([F({"type": "MultiLineString", "coordinates": [line(m) for m in rel["members"]
                  if m.get("role") == "outer" and "geometry" in m]}, nama="Kelurahan Patangpuluhan")])
batas_rw = fc([F({"type": "Polygon", "coordinates": [[[r6(b), r6(a)] for a, b in rw]]}, nama="RW 02",
                 kampung="Patangpuluhan", luas="± 6,47 ha")])

# area tampilan (sekitar kelurahan)
LAT0, LAT1, LON0, LON1 = -7.8125, -7.8060, 110.3420, 110.3535
from matplotlib.path import Path
RWP = Path([(b, a) for a, b in rw])
def masuk(e):   # hanya fitur yang menyentuh RW 02
    return any(RWP.contains_point((p["lon"], p["lat"]), radius=-0.00005) for p in e.get("geometry", []))

BESAR = {"primary", "secondary", "tertiary", "trunk", "primary_link", "secondary_link", "tertiary_link"}
SETAPAK = {"footway", "path", "steps", "pedestrian", "track", "cycleway"}
jalan, sungai, bangunan, seen = [], [], [], set()
for e in kon + kel:
    if e["type"] != "way" or e["id"] in seen or not masuk(e): continue
    seen.add(e["id"]); t = e.get("tags", {})
    if "highway" in t:
        h = t["highway"]; kls = "besar" if h in BESAR else "setapak" if h in SETAPAK else "kecil"
        jalan.append(F({"type": "LineString", "coordinates": line(e)}, nama=t.get("name", ""), kelas=kls))
    elif "waterway" in t:
        sungai.append(F({"type": "LineString", "coordinates": line(e)}, nama=t.get("name", "")))
    elif "building" in t and len(e["geometry"]) > 3:
        bangunan.append(F({"type": "Polygon", "coordinates": [line(e)]}))

# foto: perkecil untuk web
titik = []
for p in pois:
    foto = ""
    if FOTO(p["foto"]):
        foto = "foto/%02d.jpg" % p["no"]
        im = ImageOps.exif_transpose(Image.open(FOTO(p["foto"]))).convert("RGB"); im.thumbnail((1000, 1000))
        im.save(J("web", foto), quality=80, optimize=True)
    titik.append(F({"type": "Point", "coordinates": [p["lon"], p["lat"]]}, no=p["no"], nama=p["nama"], kat=p["kat"],
                   warna=p["warna"], dalam=p["dalam"], foto=foto, alamat=p.get("alamat", "")))
for f in ("logo/uad.jpg", "logo/kkn.png"):
    im = Image.open(J(f)).convert("RGB"); im.thumbnail((256, 256)); im.save(J("web", os.path.basename(f).split(".")[0] + ".png"))

data = dict(rw=batas_rw, kel=batas_kel, jalan=fc(jalan), sungai=fc(sungai), bangunan=fc(bangunan), titik=fc(titik),
            menyusul=MENYUSUL)
with open(J("web", "data.js"), "w", encoding="utf-8") as fh:
    fh.write("const DATA = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n")
shutil.copy(J("web_template.html"), J("web", "index.html"))
open(J("web", ".nojekyll"), "w").close()
print("web/ siap:", len(titik), "titik,", len(jalan), "jalan,", len(bangunan), "bangunan")
