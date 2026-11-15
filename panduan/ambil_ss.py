# Dijalankan di dalam QGIS:  qgis-ltr.bat --noversioncheck --nologo --code panduan\ambil_ss.py --project <salinan .qgs>
# Ambil screenshot tiap langkah panduan ke folder di env SS_DIR, tombol penting ditandai kotak merah. Tidak menyimpan apa pun.
import os
from qgis.utils import iface
from qgis.core import QgsProject, QgsFeature, QgsGeometry, QgsPointXY, QgsRectangle, QgsCoordinateTransform, QgsCoordinateReferenceSystem
from qgis.PyQt.QtCore import QTimer, QPoint, QRect, Qt
from qgis.PyQt.QtGui import QPainter, QPen, QColor, QFont
from qgis.PyQt.QtWidgets import QApplication, QToolButton

OUT = os.environ.get("SS_DIR", os.path.expanduser("~"))
mw = iface.mainWindow()
LOG = open(os.path.join(OUT, "_log.txt"), "w", encoding="utf-8")
def log(*a): LOG.write(" ".join(map(str, a)) + "\n"); LOG.flush()

def lyr(nama): return QgsProject.instance().mapLayersByName(nama)[0]

def tombol(action):
    for tb in mw.findChildren(__import__("qgis.PyQt.QtWidgets", fromlist=["QToolBar"]).QToolBar):
        w = tb.widgetForAction(action)
        if w and w.isVisible(): return w

def grab(nama, sorot=(), widget=None, label=None, potong=False):
    w = widget or mw
    QApplication.processEvents()
    pm = w.grab()
    p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor(220, 38, 38)); pen.setWidth(4); p.setPen(pen)
    rs = []
    for s in sorot:
        if s is None: continue
        if isinstance(s, QRect): r = s
        else:
            tl = s.mapTo(w, QPoint(0, 0)); r = QRect(tl, s.size())
        p.drawRoundedRect(r.adjusted(-5, -5, 5, 5), 6, 6); rs.append(r)
    p.end()
    if potong and rs:   # potong area sekitar tombol biar kelihatan jelas
        u = rs[0]
        for r in rs[1:]: u = u.united(r)
        W, H = 720, 240
        x = max(0, min(pm.width() - W, u.center().x() - W // 2))
        pm = pm.copy(QRect(x, 0, W, H)).scaled(W * 2, H * 2, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    pm.save(os.path.join(OUT, nama + ".png"))
    log("ss", nama, pm.width(), pm.height())

def fokus(skala=1.35):
    rw = lyr("Batas RW 02")
    tr = QgsCoordinateTransform(rw.crs(), iface.mapCanvas().mapSettings().destinationCrs(), QgsProject.instance())
    e = tr.transformBoundingBox(rw.extent()); e.scale(skala)
    iface.mapCanvas().setExtent(e); iface.mapCanvas().refresh()

titik = None
langkah = []
def nanti(ms):
    def dec(f): langkah.append((ms, f)); return f
    return dec

@nanti(500)
def siap():
    global titik
    if os.environ.get("PROJ"): iface.addProject(os.environ["PROJ"])
    titik = lyr("Titik Fasilitas")
    mw.showNormal(); mw.resize(1500, 900); mw.move(20, 20)
    iface.setActiveLayer(titik); fokus()

@nanti(9000)   # tunggu citra satelit kemuat
def s01():
    grab("01_buka_proyek")

@nanti(500)
def s02():
    titik.startEditing(); iface.setActiveLayer(titik); QApplication.processEvents()
    grab("02_toggle_editing", [tombol(iface.actionToggleEditing())], potong=True)

@nanti(500)
def s03():
    iface.actionVertexTool().trigger()
    grab("03_geser_titik", [tombol(iface.actionVertexTool())], potong=True)

@nanti(500)
def s04():
    iface.actionAddFeature().trigger(); QApplication.processEvents()
    grab("04a_tombol_tambah", [tombol(iface.actionAddFeature())], potong=True)
    f = QgsFeature(titik.fields())
    f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(110.3475, -7.8092)))
    f["kategori"] = "Kesehatan"
    dlg = iface.getFeatureForm(titik, f)
    dlg.setWindowTitle("Titik Fasilitas - Feature Attributes"); dlg.resize(560, 520); dlg.show()
    globals()["_dlg"] = dlg

@nanti(1500)
def s04b():
    grab("04_tambah_titik", widget=_dlg); _dlg.reject()

@nanti(500)
def s05():
    iface.actionIdentify().trigger(); QApplication.processEvents()
    grab("05a_ikon_identify", [tombol(iface.actionIdentify())], potong=True)
    f = next(x for x in titik.getFeatures() if x["foto"])
    dlg = iface.getFeatureForm(titik, f); dlg.resize(620, 640); dlg.show()
    globals()["_dlg"] = dlg

@nanti(2000)
def s05b():
    from qgis.PyQt.QtWidgets import QToolButton as TB
    btn = [b for b in _dlg.findChildren(TB) if b.isVisible() and b.text() in ("…", "...")]
    grab("05_foto", btn[:1], widget=_dlg); _dlg.reject()

@nanti(500)
def s06():
    iface.actionPan().trigger()
    grab("06_simpan", [tombol(iface.actionSaveActiveLayerEdits()), tombol(iface.actionToggleEditing())], potong=True)

@nanti(500)
def selesai():
    titik.rollBack(); log("selesai"); LOG.close()
    os._exit(0)

def jalan(i=0):
    if i >= len(langkah): return
    ms, f = langkah[i]
    def run():
        try: f()
        except Exception as e: log("ERROR", f.__name__, repr(e))
        jalan(i + 1)
    QTimer.singleShot(ms, run)

jalan()
