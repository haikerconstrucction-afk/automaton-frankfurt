"""Vertriebskanaele: jeder Kanal wird automatisch aktiv, sobald seine Zugangsdaten als GitHub-Secret existieren.
Neue Plattform = neue Klasse mit enabled() und publish(product)."""
import os, json, urllib.request, urllib.parse, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent

def http(method, url, headers, data=None, form=False):
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data).encode() if form else json.dumps(data).encode()
        headers = {**headers, "Content-Type": "application/x-www-form-urlencoded" if form else "application/json"}
    return json.load(urllib.request.urlopen(urllib.request.Request(url, data=body, method=method, headers=headers), timeout=60))

class Etsy:
    """Etsy Open API v3. Secrets: ETSY_API_KEY (keystring:shared_secret), ETSY_REFRESH_TOKEN, ETSY_SHOP_ID, ETSY_TAXONOMY_ID (optional)."""
    name = "etsy"; fee_eur = 0.19
    def enabled(self): return all(os.getenv(k) for k in ("ETSY_API_KEY", "ETSY_REFRESH_TOKEN", "ETSY_SHOP_ID"))
    def token(self):
        r = http("POST", "https://api.etsy.com/v3/public/oauth/token", {}, {"grant_type": "refresh_token",
                 "client_id": os.getenv("ETSY_API_KEY").split(":")[0], "refresh_token": os.getenv("ETSY_REFRESH_TOKEN")}, form=True)
        return r["access_token"]
    def publish(self, p):
        tok = self.token(); shop = os.getenv("ETSY_SHOP_ID")
        h = {"x-api-key": os.getenv("ETSY_API_KEY"), "Authorization": f"Bearer {tok}"}
        lst = http("POST", f"https://api.etsy.com/v3/application/shops/{shop}/listings", h, {
            "quantity": 999, "title": p["title"][:140], "description": (p.get("pitch", "") + "\n\nSofort-Download / Instant download.")[:4000],
            "price": float(p["price_eur"]), "who_made": "i_did", "when_made": "made_to_order", "taxonomy_id": int(os.getenv("ETSY_TAXONOMY_ID", "2078")),
            "type": "download", "is_supply": "false", "state": "draft"}, form=True)
        lid = lst["listing_id"]
        # Datei anhaengen (multipart)
        import uuid
        f = ROOT/"site/dl"/p["file"]; b = uuid.uuid4().hex
        body = (f"--{b}\r\nContent-Disposition: form-data; name=\"name\"\r\n\r\n{f.name}\r\n--{b}\r\n"
                f"Content-Disposition: form-data; name=\"file\"; filename=\"{f.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n").encode() + f.read_bytes() + f"\r\n--{b}--\r\n".encode()
        urllib.request.urlopen(urllib.request.Request(f"https://api.etsy.com/v3/application/shops/{shop}/listings/{lid}/files",
            data=body, method="POST", headers={**h, "Content-Type": f"multipart/form-data; boundary={b}"}), timeout=120)
        return f"https://www.etsy.com/listing/{lid}"

CHANNELS = [Etsy()]

def sync_all(s, log, book):
    for ch in CHANNELS:
        if not ch.enabled(): continue
        for p in s["products"]:
            if p.get("retired") or not p.get("file") or p.get("channels", {}).get(ch.name): continue
            try:
                url = ch.publish(p); p.setdefault("channels", {})[ch.name] = url
                book(-ch.fee_eur, f"{ch.name}-Einstellgebuehr: {p['title']}"); log(f"Auf {ch.name} eingestellt (Entwurf): {url}")
            except Exception as e:
                log(f"{ch.name}-Fehler bei {p['slug']}: {e}"); break
