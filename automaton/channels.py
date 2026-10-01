import re
"""Vertriebskanaele: jeder Kanal wird automatisch aktiv, sobald seine Zugangsdaten als GitHub-Secret existieren.
Neue Plattform = neue Klasse mit enabled() und publish(product)."""
def etsy_title(t):
    # Etsy: "&" hoechstens einmal, keine Sonderzeichen wie $ ^ `, max. 140 Zeichen
    first = t.find("&")
    if first >= 0: t = t[:first + 1] + re.sub(r"\s*&\s*", ", ", t[first + 1:])
    t = re.sub(r"[\$\^`]", "", t)
    return re.sub(r"\s+", " ", t).strip()[:140]

import os, json, urllib.request, urllib.parse, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent

def http(method, url, headers, data=None, form=False):
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
        headers = {**headers, "Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data=body, method=method, headers=headers), timeout=60))

class Etsy:
    """Etsy Open API v3. Secrets: ETSY_API_KEY (keystring:shared_secret), ETSY_REFRESH_TOKEN, ETSY_USER_ID."""
    name = "etsy"; fee_eur = 0.19; per_run = 3
    def __init__(self): self._tok = None; self._shop = None
    def enabled(self): return all(os.getenv(k) for k in ("ETSY_API_KEY", "ETSY_REFRESH_TOKEN"))
    def h(self):
        if not self._tok:
            r = http("POST", "https://api.etsy.com/v3/public/oauth/token", {}, {"grant_type": "refresh_token",
                     "client_id": os.getenv("ETSY_API_KEY").split(":")[0], "refresh_token": os.getenv("ETSY_REFRESH_TOKEN")}, form=True)
            self._tok = r["access_token"]
        return {"x-api-key": os.getenv("ETSY_API_KEY"), "Authorization": f"Bearer {self._tok}"}
    def shop(self):
        if not self._shop:
            uid = os.getenv("ETSY_USER_ID") or self.h()["Authorization"].split()[1].split(".")[0]
            r = http("GET", f"https://api.etsy.com/v3/application/users/{uid}/shops", self.h())
            self._shop = str(r.get("shop_id") or r["results"][0]["shop_id"])
        return self._shop
    def upload(self, url, field, path, extra=None):
        import uuid
        b = uuid.uuid4().hex; parts = b""
        for k, v in (extra or {}).items():
            parts += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        parts += (f"--{b}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{path.name}\"\r\n"
                  f"Content-Type: application/octet-stream\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{b}--\r\n".encode()
        urllib.request.urlopen(urllib.request.Request(url, data=parts, method="POST",
            headers={**self.h(), "Content-Type": f"multipart/form-data; boundary={b}"}), timeout=120)
    def cover(self, p):
        from PIL import Image, ImageDraw, ImageFont
        import textwrap
        ebook = p.get("type") == "ebook"
        img = Image.new("RGB", (2000, 1600), (59, 47, 99) if ebook else (15, 92, 74)); d = ImageDraw.Draw(img)
        try:
            big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110)
            small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 60)
        except Exception: big = small = ImageFont.load_default()
        d.rounded_rectangle((120, 120, 1880, 1480), 40, fill=(250, 249, 246))
        d.text((200, 200), ("E-BOOK · PDF" if ebook else "EXCEL-VORLAGE") if p.get("language") != "en" else ("E-BOOK · PDF" if ebook else "EXCEL TEMPLATE"), font=small, fill=(15, 92, 74))
        y = 340
        for line in (textwrap.wrap(p["title"], 26) if p.get("language") != "zh" else [p["title"][i:i+12] for i in range(0, len(p["title"]), 12)])[:6]: d.text((200, y), line, font=big, fill=(22, 24, 29)); y += 140
        d.text((200, 1340), "Haiktec · Sofort-Download" if p.get("language") != "en" else "Haiktec · Instant download", font=small, fill=(95, 100, 112))
        path = ROOT/"site/dl"/f"cover-{p['slug']}.jpg"; img.save(path, quality=90); return path
    def publish(self, p):
        shop = self.shop(); base = f"https://api.etsy.com/v3/application/shops/{shop}/listings"
        en = p.get("language") == "en"
        desc = (p.get("pitch", "") + ("\n\nInstant digital download. No physical item will be shipped." if en else
                "\n\nSofortiger digitaler Download. Es wird kein physischer Artikel versendet. Kleinunternehmer gem. § 19 UStG."))
        tags = [t[:20] for t in (["excel template", "planner", "tracker", "spreadsheet"] if p.get("type") == "excel" else ["ebook", "pdf guide", "digital download", "instant download"])]
        lst = http("POST", base, self.h(), {"quantity": 999, "title": etsy_title(p["title"]), "description": desc[:4000],
            "price": float(p["price_eur"]), "who_made": "i_did", "when_made": "2020_2026", "taxonomy_id": int(os.getenv("ETSY_TAXONOMY_ID", "2078")),
            "type": "download", "is_supply": "false", "tags": ",".join(tags)}, form=True)
        lid = lst["listing_id"]
        self.upload(f"{base}/{lid}/images", "image", self.cover(p))
        import shutil, tempfile, re as _re
        src = ROOT/"site/dl"/p["file"]; short = _re.sub(r"[^A-Za-z0-9_.-]", "-", p["slug"])[:55] + src.suffix
        tmpf = pathlib.Path(tempfile.mkdtemp())/short; shutil.copy(src, tmpf)
        self.upload(f"{base}/{lid}/files", "file", tmpf, {"name": short})
        http("PATCH", f"{base}/{lid}", self.h(), {"state": "active"}, form=True)
        return f"https://www.etsy.com/listing/{lid}"

CHANNELS = [Etsy()]
CFG_DAY = {"etsy": 6}  # max. Einstellungen pro Tag (Etsy-Gebuehr 0,20 $ je Eintrag)

def sync_all(s, log, book):
    for ch in CHANNELS:
        if not ch.enabled(): continue
        done = 0
        import datetime as _dt
        today = _dt.datetime.utcnow().date().isoformat()
        left = CFG_DAY.get(ch.name, 6) - sum(1 for l in s["log"] if l["t"].startswith(today) and l["why"].startswith(f"Auf {ch.name} eingestellt"))
        for p in s["products"]:
            if done >= min(ch.per_run, left): break
            if p.get("retired") or not p.get("file") or not p.get("pay_url") or p.get("channels", {}).get(ch.name): continue
            done += 1
            try:
                url = ch.publish(p); p.setdefault("channels", {})[ch.name] = url
                book(-ch.fee_eur, f"{ch.name}-Einstellgebuehr: {p['title']}"); log(f"Auf {ch.name} eingestellt: {url}")
            except Exception as e:
                det = e.read()[:400].decode(errors="ignore") if hasattr(e, "read") else ""
                log(f"{ch.name}-Fehler bei {p['slug']}: {e} {det}"); break
