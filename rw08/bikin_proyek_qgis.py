"""Bikin ulang qgis/Peta_RW08_Semaki.qgs pakai PyQGIS (gaya diambil dari layer_styles di GeoPackage).
Jalankan:  "C:\\Program Files\\QGIS 3.44.15\\bin\\python-qgis-ltr.bat" bikin_proyek_qgis.py"""
import os, sqlite3, sys
from qgis.core import (QgsApplication, QgsProject, QgsVectorLayer, QgsRasterLayer, QgsCoordinateReferenceSystem,
                       QgsMapSettings, QgsMapRendererParallelJob, QgsRectangle, QgsReadWriteContext)
from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor

D = os.path.dirname(os.path.abspath(__file__))
Q = os.path.join(D, "qgis"); GPKG = os.path.join(Q, "peta_rw08.gpkg")
app = QgsApplication([], False); app.initQgis()

URUT = [("titik_fasilitas", "Titik Fasilitas"), ("batas_rw", "Batas RW 08"), ("batas_kelurahan", "Batas Kelurahan"),
        ("jalan", "Jalan"), ("sungai", "Sungai"), ("bangunan", "Bangunan")]
qml = dict(sqlite3.connect(GPKG).execute("select f_table_name, styleQML from layer_styles where useAsDefault=1").fetchall())

prj = QgsProject.instance(); prj.clear()
prj.setTitle("Peta RW 08 Semaki")
prj.setCrs(QgsCoordinateReferenceSystem("EPSG:32749"))
prj.writeEntryBool("Paths", "/Absolute", False)
prj.setFileName(os.path.join(Q, "Peta_RW08_Semaki.qgs"))

url = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
citra = QgsRasterLayer(f"type=xyz&url={url.replace('{', '%7B').replace('}', '%7D')}&zmax=19&zmin=0&crs=EPSG3857",
                       "Citra Satelit (Esri)", "wms")
print("citra valid:", citra.isValid())
prj.addMapLayer(citra)

for t, nama in reversed(URUT):
    lyr = QgsVectorLayer(f"{GPKG}|layername={t}", nama, "ogr")
    print(t, "valid:", lyr.isValid(), lyr.featureCount())
    if t in qml:
        doc = QDomDocument(); doc.setContent(qml[t])
        ok = lyr.importNamedStyle(doc)
        print("   gaya:", ok, lyr.renderer().type() if lyr.renderer() else None)
    if t == "titik_fasilitas":   # kolom foto = tombol pilih file (path relatif ke folder proyek), kategori = pilihan
        from qgis.core import QgsEditorWidgetSetup
        i = lyr.fields().indexOf("foto")
        lyr.setEditorWidgetSetup(i, QgsEditorWidgetSetup("ExternalResource", {
            "RelativeStorage": 1, "StorageMode": 0, "DocumentViewer": 1, "DocumentViewerHeight": 200, "DocumentViewerWidth": 300,
            "DefaultRoot": "", "FileWidget": True, "FileWidgetButton": True, "UseLink": False, "FullUrl": False,
            "FileWidgetFilter": "Foto (*.jpg *.jpeg *.png)"}))
        i = lyr.fields().indexOf("kategori")
        kat = ["Tempat Ibadah", "Kesehatan", "Pendidikan", "Pemerintahan", "Ekonomi", "Keamanan", "Kebersihan", "Lainnya"]
        lyr.setEditorWidgetSetup(i, QgsEditorWidgetSetup("ValueMap", {"map": [{k: k} for k in kat]}))
        for f in ("no",):   # nomor diurutkan otomatis, sembunyikan dari form
            lyr.setEditorWidgetSetup(lyr.fields().indexOf(f), QgsEditorWidgetSetup("Hidden", {}))
    prj.addMapLayer(lyr)

# urutan di panel layer: titik paling atas, citra paling bawah
root = prj.layerTreeRoot()
for i, (t, nama) in enumerate(URUT):
    node = root.findLayer(prj.mapLayersByName(nama)[0].id())
    clone = node.clone(); root.insertChildNode(i, clone); root.removeChildNode(node)

rw = prj.mapLayersByName("Batas RW 08")[0]
ext = rw.extent(); ext.scale(1.6)
canvas_ext = QgsRectangle(ext)
prj.viewSettings().setDefaultViewExtent(
    __import__("qgis.core", fromlist=["QgsReferencedRectangle"]).QgsReferencedRectangle(canvas_ext, rw.crs()))
prj.write()
print("disimpan:", prj.fileName())

# render cek
if "--cek" in sys.argv:
    ms = QgsMapSettings()
    ms.setLayers([prj.mapLayersByName(n)[0] for _, n in URUT] + [citra])
    ms.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:4326"))
    ms.setExtent(ext); ms.setOutputSize(QSize(1600, 900)); ms.setBackgroundColor(QColor("white"))
    job = QgsMapRendererParallelJob(ms); job.start(); job.waitForFinished()
    job.renderedImage().save(sys.argv[sys.argv.index("--cek") + 1])
    print("render cek disimpan")
app.exitQgis()
