import requests,sys,time
q=sys.argv[1]; out=sys.argv[2]
for u in ["https://overpass.private.coffee/api/interpreter","https://maps.mail.ru/osm/tools/overpass/api/interpreter","https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter"]:
    try:
        r=requests.post(u,data={"data":q},headers={"User-Agent":"rw-map/1.0"},timeout=120)
        print(u,r.status_code,len(r.content))
        if r.status_code==200 and r.content.lstrip().startswith(b"{"):
            open(out,"wb").write(r.content); print("saved"); break
    except Exception as e: print(u,"ERR",e)
