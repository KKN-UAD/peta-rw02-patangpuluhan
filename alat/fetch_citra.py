"""Unduh citra satelit Esri World Imagery (zoom 19) untuk area RW 02 -> data/citra_z19.png"""
import math, io, json, requests
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
Z = 19
LAT0, LAT1, LON0, LON1 = -7.8140, -7.8030, 110.3405, 110.3575
def tile(lat, lon):
    n = 2 ** Z; x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y
tx0, ty0 = map(int, tile(LAT1, LON0)); tx1, ty1 = map(int, tile(LAT0, LON1))
URL = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
s = requests.Session(); s.headers["User-Agent"] = "rw-map/1.0"
def get(xy):
    x, y = xy
    for _ in range(3):
        try:
            r = s.get(URL.format(z=Z, x=x, y=y), timeout=30)
            if r.ok: return xy, Image.open(io.BytesIO(r.content)).convert("RGB")
        except Exception: pass
    return xy, None
jobs = [(x, y) for x in range(tx0, tx1 + 1) for y in range(ty0, ty1 + 1)]
print("tiles:", len(jobs))
mos = Image.new("RGB", ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
miss = 0
with ThreadPoolExecutor(8) as ex:
    for (x, y), im in ex.map(get, jobs):
        if im is None: miss += 1; continue
        mos.paste(im, ((x - tx0) * 256, (y - ty0) * 256))
print("gagal:", miss)
mos.save("data/citra_z19.png")
json.dump({"z": Z, "tx0": tx0, "ty0": ty0}, open("data/citra_meta.json", "w"))
