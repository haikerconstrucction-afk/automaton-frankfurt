"""Meldet neue/aktualisierte Seiten an Bing, Yandex, Seznam, Naver via IndexNow (nach dem Deploy)."""
import json, pathlib, urllib.request, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
KEY = "314c33bbed706e425706eb092cf6f430"
SITE = "https://haiktec.tech"
urls = re.findall(r"<loc>(.*?)</loc>", (ROOT/"site/sitemap.xml").read_text())
body = json.dumps({"host": "haiktec.tech", "key": KEY, "keyLocation": f"{SITE}/{KEY}.txt", "urlList": urls}).encode()
try:
    r = urllib.request.urlopen(urllib.request.Request("https://api.indexnow.org/indexnow", data=body, method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"}), timeout=30)
    print("IndexNow", r.status, len(urls))
except Exception as e: print("IndexNow Fehler", e)
