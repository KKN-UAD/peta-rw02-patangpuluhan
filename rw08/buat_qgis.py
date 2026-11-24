"""Ekspor data peta RW 08 ke proyek QGIS: qgis/peta_rw08.gpkg + qgis/Peta_RW08_Semaki.qgs
Jalankan setelah buat_peta.py (butuh data/pois.json).   py buat_qgis.py
Setelah diedit di QGIS, jalankan lagi buat_peta.py & buat_web.py -> titik & batas RW dibaca dari GeoPackage."""
import json, os, shutil, sqlite3, datetime
import numpy as np
import shapely
from shapely.geometry import Polygon, MultiLineString, LineString, Point
from pyogrio.raw import write
from PIL import Image, ImageOps

D = os.path.dirname(os.path.abspath(__file__))
J = lambda *a: os.path.join(D, *a)
Q = J("qgis"); GPKG = os.path.join(Q, "peta_rw08.gpkg")
ASET = "drive-download-20261115T153336Z-1-001"
def FOTO(f):   # sama dengan buat_peta.FOTO: kalau path di luar folder foto, cari nama filenya di qgis/foto
    if not f: return ""
    nama = os.path.basename(f.replace("\\", "/"))
    cand = [J("qgis", f), J(ASET, f), J("qgis", "foto", nama)]
    if os.path.isdir(J("qgis", "foto")):
        cand += [J("qgis", "foto", x) for x in os.listdir(J("qgis", "foto")) if x.lower() == nama.lower()]
    return next((p for p in cand if os.path.isfile(p)), "")
os.makedirs(os.path.join(Q, "foto"), exist_ok=True)
import sys
if os.path.exists(GPKG):
    if "--timpa" not in sys.argv: sys.exit("qgis/peta_rw08.gpkg sudah ada (mungkin sudah diedit). Pakai --timpa untuk membuat ulang.")
    os.remove(GPKG)

kel = json.load(open(J("data/kelurahan.json"), encoding="utf-8"))["elements"]
kon = json.load(open(J("data/konteks.json"), encoding="utf-8"))["elements"]
rw = json.load(open(J("data/rw_latlon.json")))
pois = json.load(open(J("data/pois.json"), encoding="utf-8"))
REC = dict(kelurahan="SEMAKI", kecamatan="UMBULHARJO", nama_rw="RW 08", kampung="SEMAKI KULON", rw_id="34711310010308")

def tulis(layer, geoms, fields, gtype):
    names = list(fields)
    data = [np.array(fields[n], dtype=object) for n in names]
    write(GPKG, shapely.to_wkb(np.array(geoms, dtype=object)), data, names, layer=layer, driver="GPKG",
          crs="EPSG:4326", geometry_type=gtype, append=os.path.exists(GPKG), encoding="UTF-8")

ll = lambda e: [(p["lon"], p["lat"]) for p in e["geometry"]]

# batas RW
tulis("batas_rw", [Polygon([(b, a) for a, b in rw])], {k: [v] for k, v in REC.items()}, "Polygon")
# batas kelurahan
rel = next(e for e in kel if e["type"] == "relation" and e.get("tags", {}).get("boundary") == "administrative")
tulis("batas_kelurahan", [MultiLineString([ll(m) for m in rel["members"] if m.get("role") == "outer" and "geometry" in m])],
      {"nama": ["Semaki"]}, "MultiLineString")

# titik fasilitas (foto disalin ke qgis/foto)
G, F = [], {k: [] for k in ("no", "nama", "kategori", "keterangan", "foto", "sumber")}
for p in pois:
    foto = ""
    if FOTO(p["foto"]):
        foto = "foto/" + os.path.basename(p["foto"]).rsplit(".", 1)[0] + ".jpg"
        if os.path.abspath(FOTO(p["foto"])) == os.path.abspath(os.path.join(Q, foto)): pass
        else:
          im = ImageOps.exif_transpose(Image.open(FOTO(p["foto"]))).convert("RGB"); im.thumbnail((1600, 1600))
          im.save(os.path.join(Q, foto), quality=85)
    G.append(Point(p["lon"], p["lat"]))
    for k, v in (("no", p["no"]), ("nama", p["nama"]), ("kategori", p["kat"]), ("keterangan", p.get("alamat", "")),
                 ("foto", foto), ("sumber", p.get("sumber", "") or "OpenStreetMap")):
        F[k].append(v)
tulis("titik_fasilitas", G, F, "Point")

# jalan, sungai, bangunan (sekitar kelurahan)
LAT0, LAT1, LON0, LON1 = -7.8045, -7.7935, 110.3760, 110.3880
masuk = lambda e: any(LAT0 < p["lat"] < LAT1 and LON0 < p["lon"] < LON1 for p in e.get("geometry", []))
BESAR = {"primary", "secondary", "tertiary", "trunk", "primary_link", "secondary_link", "tertiary_link"}
SETAPAK = {"footway", "path", "steps", "pedestrian", "track", "cycleway"}
jl, jf, sg, sf, bg, seen = [], {"nama": [], "kelas": []}, [], {"nama": []}, [], set()
for e in kon + kel:
    if e["type"] != "way" or e["id"] in seen or not masuk(e) or len(e.get("geometry", [])) < 2: continue
    seen.add(e["id"]); t = e.get("tags", {})
    if "highway" in t:
        h = t["highway"]; jl.append(LineString(ll(e)))
        jf["nama"].append(t.get("name", "")); jf["kelas"].append("besar" if h in BESAR else "setapak" if h in SETAPAK else "kecil")
    elif "waterway" in t:
        sg.append(LineString(ll(e))); sf["nama"].append(t.get("name", ""))
    elif "building" in t and len(e["geometry"]) > 3:
        bg.append(Polygon(ll(e)))
tulis("jalan", jl, jf, "LineString")
tulis("sungai", sg, sf, "LineString")
tulis("bangunan", bg, {"jenis": ["bangunan"] * len(bg)}, "Polygon")

# ---------------------------------------------------------------- gaya (QML) disimpan di GeoPackage
KAT = {}
for p in pois: KAT[p["kat"]] = p["warna"]
rgb = lambda h: ",".join(str(int(h[i:i + 2], 16)) for i in (1, 3, 5)) + ",255"

def qml(renderer, labels=""):
    return f'<!DOCTYPE qgis PUBLIC \'http://mrcc.com/qgis.dtd\' \'SYSTEM\'><qgis version="3.34" styleCategories="AllStyleCategories">{renderer}{labels}</qgis>'

def sym(kind, name, layers):
    return f'<symbol type="{kind}" name="{name}" alpha="1" clip_to_extent="1" force_rhr="0">{layers}</symbol>'

def lyr(cls, props):
    o = "".join(f'<Option type="QString" name="{k}" value="{v}"/>' for k, v in props.items())
    return f'<layer class="{cls}" enabled="1" locked="0" pass="0"><Option type="Map">{o}</Option></layer>'

def single(kind, layers):
    return f'<renderer-v2 type="singleSymbol" symbollevels="0" enableorderby="0" forceraster="0"><symbols>{sym(kind, "0", layers)}</symbols></renderer-v2>'

def label(field, size, color="255,255,255,255", buf="0,0,0,255", place="0", extra=""):
    return (f'<labeling type="simple"><settings calloutType="simple"><text-style fieldName="{field}" fontSize="{size}" fontWeight="75" '
            f'textColor="{color}" fontFamily="Arial" isExpression="0"><text-buffer bufferDraw="1" bufferSize="1" bufferColor="{buf}"/></text-style>'
            f'<placement placement="{place}" dist="1.5" {extra}/><rendering scaleVisibility="0"/></settings></labeling>')

ST = {}
cats, symbols = "", ""
for i, (k, c) in enumerate(KAT.items()):
    cats += f'<category symbol="{i}" value="{k}" label="{k}" render="true"/>'
    symbols += sym("marker", str(i), lyr("SimpleMarker", {"name": "circle", "size": "5", "color": rgb(c),
                   "outline_color": "255,255,255,255", "outline_width": "0.6", "size_unit": "MM"}))
ST["titik_fasilitas"] = qml(f'<renderer-v2 type="categorizedSymbol" attr="kategori" symbollevels="0" enableorderby="0" forceraster="0">'
                            f'<categories>{cats}</categories><symbols>{symbols}</symbols></renderer-v2>',
                            label('concat("no", \'. \', "nama")'.replace('"', "&quot;").replace("'", "&apos;"), 9, place="6").replace('isExpression="0"', 'isExpression="1"'))
ST["batas_rw"] = qml(single("fill", lyr("SimpleFill", {"style": "no", "color": "0,0,0,0"}) +
                            lyr("SimpleLine", {"line_color": "0,0,0,130", "line_width": "1.6", "line_width_unit": "MM"}) +
                            lyr("SimpleLine", {"line_color": "253,190,21,255", "line_width": "1.0", "line_width_unit": "MM"})))
ST["batas_kelurahan"] = qml(single("line", lyr("SimpleLine", {"line_color": "232,121,249,255", "line_width": "0.7",
                                   "line_width_unit": "MM", "use_custom_dash": "1", "customdash": "5;2;1;2"})))
ST["jalan"] = qml('<renderer-v2 type="categorizedSymbol" attr="kelas" symbollevels="0" enableorderby="0" forceraster="0"><categories>'
                  '<category symbol="0" value="besar" label="Jalan Besar" render="true"/><category symbol="1" value="kecil" label="Jalan Kecil / Gang" render="true"/>'
                  '<category symbol="2" value="setapak" label="Jalan Setapak" render="true"/></categories><symbols>'
                  + sym("line", "0", lyr("SimpleLine", {"line_color": "59,29,0,255", "line_width": "1.6", "line_width_unit": "MM"}) +
                        lyr("SimpleLine", {"line_color": "245,158,11,255", "line_width": "1.1", "line_width_unit": "MM"}))
                  + sym("line", "1", lyr("SimpleLine", {"line_color": "255,255,255,255", "line_width": "0.5", "line_width_unit": "MM"}))
                  + sym("line", "2", lyr("SimpleLine", {"line_color": "255,255,255,200", "line_width": "0.3", "line_width_unit": "MM",
                                                         "use_custom_dash": "1", "customdash": "2;2"}))
                  + '</symbols></renderer-v2>', label("nama", 8, place="2"))
ST["sungai"] = qml(single("line", lyr("SimpleLine", {"line_color": "56,189,248,255", "line_width": "0.9", "line_width_unit": "MM"})))
ST["bangunan"] = qml(single("fill", lyr("SimpleFill", {"color": "233,201,166,140", "outline_color": "156,122,91,255", "outline_width": "0.1"})))

con = sqlite3.connect(GPKG)
con.execute("""CREATE TABLE IF NOT EXISTS layer_styles (id INTEGER PRIMARY KEY AUTOINCREMENT, f_table_catalog TEXT(256),
  f_table_schema TEXT(256), f_table_name TEXT(256), f_geometry_column TEXT(256), styleName TEXT(30), styleQML TEXT,
  styleSLD TEXT, useAsDefault BOOLEAN, description TEXT, owner TEXT(30), ui TEXT(30), update_time DATETIME)""")
for t, x in ST.items():
    con.execute("INSERT INTO layer_styles (f_table_catalog,f_table_schema,f_table_name,f_geometry_column,styleName,styleQML,styleSLD,useAsDefault,description,owner,update_time) "
                "VALUES ('','',?,'geom',?,?,'',1,'gaya peta RW 08','',?)", (t, t, x, datetime.datetime.now().isoformat()))
con.commit(); con.close()

# ---------------------------------------------------------------- proyek .qgs
URUT = ["titik_fasilitas", "batas_rw", "batas_kelurahan", "jalan", "sungai", "bangunan"]
NAMA = {"titik_fasilitas": "Titik Fasilitas", "batas_rw": "Batas RW 08", "batas_kelurahan": "Batas Kelurahan",
        "jalan": "Jalan", "sungai": "Sungai", "bangunan": "Bangunan"}
GT = {"titik_fasilitas": "Point", "batas_rw": "Polygon", "batas_kelurahan": "Line", "jalan": "Line", "sungai": "Line", "bangunan": "Polygon"}
SRS = ('<spatialrefsys nativeFormat="Wkt"><wkt>GEOGCRS["WGS 84",DATUM["World Geodetic System 1984",ELLIPSOID["WGS 84",6378137,298.257223563]],'
       'CS[ellipsoidal,2],AXIS["latitude",north],AXIS["longitude",east],UNIT["degree",0.0174532925199433],ID["EPSG",4326]]</wkt>'
       '<proj4>+proj=longlat +datum=WGS84 +no_defs</proj4><srsid>3452</srsid><srid>4326</srid><authid>EPSG:4326</authid>'
       '<description>WGS 84</description><projectionacronym>longlat</projectionacronym><ellipsoidacronym>EPSG:7030</ellipsoidacronym>'
       '<geographicflag>true</geographicflag></spatialrefsys>')
SRS_UTM = ('<spatialrefsys nativeFormat="Wkt"><wkt></wkt><proj4>+proj=utm +zone=49 +south +datum=WGS84 +units=m +no_defs</proj4>'
           '<srsid>3187</srsid><srid>32749</srid><authid>EPSG:32749</authid><description>WGS 84 / UTM zone 49S</description>'
           '<projectionacronym>utm</projectionacronym><ellipsoidacronym>EPSG:7030</ellipsoidacronym><geographicflag>false</geographicflag></spatialrefsys>')
def body(x):  # isi renderer + label dari QML
    return x.split('styleCategories="AllStyleCategories">', 1)[1].rsplit("</qgis>", 1)[0]

layers, tree, order = "", "", ""
for t in URUT:
    lid = f"{t}_rw08"
    layers += (f'<maplayer type="vector" geometry="{GT[t]}" labelsEnabled="{1 if t in ("titik_fasilitas", "jalan") else 0}">'
               f'<id>{lid}</id><datasource>./peta_rw08.gpkg|layername={t}</datasource><layername>{NAMA[t]}</layername>'
               f'<srs>{SRS}</srs><provider encoding="UTF-8">ogr</provider>{body(ST[t])}</maplayer>')
    tree += f'<layer-tree-layer id="{lid}" name="{NAMA[t]}" source="./peta_rw08.gpkg|layername={t}" providerKey="ogr" checked="Qt::Checked" expanded="1"/>'
    order += f'<item>{lid}</item>'
url = "type=xyz&amp;url=https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/%7Bz%7D/%7By%7D/%7Bx%7D&amp;zmax=19&amp;zmin=0"
layers += (f'<maplayer type="raster"><id>citra_esri</id><datasource>{url}</datasource><layername>Citra Satelit (Esri)</layername>'
           f'<srs>{SRS_UTM.replace("32749", "3857").replace("utm +zone=49 +south", "merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +nadgrids=@null")}</srs>'
           f'<provider>wms</provider></maplayer>')
tree += '<layer-tree-layer id="citra_esri" name="Citra Satelit (Esri)" source="" providerKey="wms" checked="Qt::Checked" expanded="0"/>'
order += '<item>citra_esri</item>'
xs = [b for a, b in rw]; ys = [a for a, b in rw]
qgs = (f'<!DOCTYPE qgis PUBLIC \'http://mrcc.com/qgis.dtd\' \'SYSTEM\'><qgis projectname="Peta RW 08 Semaki" version="3.34.0-Prizren">'
       f'<title>Peta RW 08 Semaki</title><projectCrs>{SRS}</projectCrs>'
       f'<layer-tree-group>{tree}<custom-order enabled="0">{order}</custom-order></layer-tree-group>'
       f'<mapcanvas name="theMapCanvas"><units>degrees</units><extent><xmin>{min(xs) - 0.001}</xmin><ymin>{min(ys) - 0.001}</ymin>'
       f'<xmax>{max(xs) + 0.001}</xmax><ymax>{max(ys) + 0.001}</ymax></extent><destinationsrs>{SRS}</destinationsrs></mapcanvas>'
       f'<projectlayers>{layers}</projectlayers><properties><Paths><Absolute type="bool">false</Absolute></Paths></properties></qgis>')
open(os.path.join(Q, "Peta_RW08_Semaki.qgs"), "w", encoding="utf-8").write(qgs)
print("qgis/ siap:", len(G), "titik,", len(jl), "jalan,", len(sg), "sungai,", len(bg), "bangunan")
