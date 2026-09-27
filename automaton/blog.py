"""Automatischer Reise- und Ratgeber-Blog mit freien Fotos (Wikimedia Commons) - bringt Besucher in den Shop."""
import json, re, urllib.request, urllib.parse, html, random
OK_LIC = ("cc0", "public domain", "pd", "cc by", "cc-by")

def commons_photo(query):
    """Freies Foto suchen. Gibt dict(url, credit, page) oder None."""
    q = urllib.parse.urlencode({"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 12,
        "gsrsearch": f"{query} filetype:bitmap", "prop": "imageinfo", "iiprop": "url|extmetadata|size", "iiurlwidth": 1200})
    try:
        r = json.load(urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + q,
            headers={"User-Agent": "HaiktecBot/1.0 (Haiktec@outlook.de)"}), timeout=30))
    except Exception as e:
        print("Commons-Fehler:", e); return None
    for pg in sorted(r.get("query", {}).get("pages", {}).values(), key=lambda x: x.get("index", 99)):
        ii = (pg.get("imageinfo") or [{}])[0]; md = ii.get("extmetadata", {})
        lic = md.get("LicenseShortName", {}).get("value", "").lower()
        if ii.get("width", 0) < 1000 or not any(lic.startswith(l) for l in OK_LIC) or "nc" in lic or "nd" in lic: continue
        artist = re.sub("<[^>]+>", "", md.get("Artist", {}).get("value", "unbekannt")).strip()[:80]
        return {"url": ii.get("thumburl") or ii["url"], "page": ii.get("descriptionurl", ""),
                "credit": f"Foto: {artist}, {md.get('LicenseShortName', {}).get('value', '')}, via Wikimedia Commons"}
    return None

def download(photo, out):
    import io
    from PIL import Image
    data = urllib.request.urlopen(urllib.request.Request(photo["url"], headers={"User-Agent": "HaiktecBot/1.0"}), timeout=60).read()
    im = Image.open(io.BytesIO(data)).convert("RGB"); im.thumbnail((1200, 1200)); im.save(out, "JPEG", quality=82)
    return im.size

TOPICS = ["Schwarzwald", "Saarland Saarschleife", "Koeln Dom", "Ruhrgebiet Zollverein", "Bodensee", "Mosel Cochem", "Heidelberg Altstadt",
    "Neuschwanstein", "Saechsische Schweiz", "Ruegen Kreidefelsen", "Hamburg Speicherstadt", "Frankfurt Skyline", "Rothenburg ob der Tauber",
    "Berlin Brandenburger Tor", "Dresden Frauenkirche", "Harz Brocken", "Nordsee Wattenmeer", "Muenchen Marienplatz", "Eifel Maare", "Rheingau Weinberge"]
LANGS = [("de", "Deutsch"), ("en", "English"), ("zh", "简体中文"), ("es", "Español"), ("fr", "Français")]

def post(s, llm_json, head, foot, site, root, book, now):
    posts = s.setdefault("blog", [])
    i = len(posts); topic = TOPICS[i % len(TOPICS)]; lang, lname = LANGS[(i // len(TOPICS) + i) % len(LANGS)]
    photo = commons_photo(topic)
    shop = [p for p in s["products"] if not p.get("retired") and p.get("pay_url")]
    rel = [p for p in shop if p.get("language") == lang][-3:] or shop[-3:]
    j, cost = llm_json(f"""Schreibe einen hochwertigen Reise-Blogartikel ueber '{topic}' (Deutschland) in der Sprache {lname}.
Leicht verstaendlich, 700-900 Woerter, konkrete Tipps (Anreise, beste Reisezeit, 3-5 Highlights, Essen). KEINE erfundenen Preise, Oeffnungszeiten, Studien oder Zahlen - nur allgemein bekanntes Wissen.
Antworte nur als JSON: {{"title":"...","slug":"kebab-case-ascii","desc":"max 150 Zeichen","html":"<p>..</p><h2>..</h2>..."}}""")
    book(s, -cost, f"Blog-Artikel: {topic} ({lang})")
    slug = re.sub(r"[^a-z0-9-]", "", j["slug"].lower())[:60] or f"post-{i}"
    body = re.sub(r"<(script|iframe|style)[^>]*>.*?</\1>", "", j["html"], flags=re.S | re.I)
    img = ""
    if photo:
        (root/"site/blog/img").mkdir(parents=True, exist_ok=True)
        try:
            download(photo, root/f"site/blog/img/{slug}.jpg")
            img = f'<figure><img src="img/{slug}.jpg" alt="{html.escape(topic)}" style="width:100%;border-radius:12px"><figcaption style="font-size:.8rem;color:#667"><a href="{photo["page"]}">{html.escape(photo["credit"])}</a></figcaption></figure>'
        except Exception as e: print("Foto-Fehler:", e)
    tips = "".join(f'<li><a href="../products/{p["slug"]}.html">{html.escape(p["title"])}</a></li>' for p in rel)
    page = head.format(lang=lang, title=f"{j['title']} – Haiktec Blog", desc=html.escape(j.get("desc", "")[:155]), r="../").replace(
        "</head>", f'<link rel="canonical" href="{site}/blog/{slug}.html"></head>') + f"""
<main class="wrap product"><a class="back" href="index.html">← Blog</a><article class="content"><h1>{html.escape(j['title'])}</h1>{img}{body}
<h2>Haiktec</h2><ul>{tips}</ul><p style="font-size:.8rem;color:#667">Text mit KI erstellt und automatisch geprueft.</p></article></main>""" + foot.format(r="../") + "</body></html>"
    (root/"site/blog").mkdir(parents=True, exist_ok=True)
    (root/f"site/blog/{slug}.html").write_text(page)
    posts.append({"slug": slug, "title": j["title"], "lang": lang, "topic": topic, "created": now, "img": bool(img)})

def index(s, head, foot, root):
    items = "".join(f'<a class="card" href="{b["slug"]}.html"><div class="body"><h3>{html.escape(b["title"])}</h3><p>{b["topic"]} · {b["lang"].upper()}</p></div></a>' for b in reversed(s.get("blog", [])))
    (root/"site/blog").mkdir(parents=True, exist_ok=True)
    (root/"site/blog/index.html").write_text(head.format(lang="de", title="Haiktec Blog – Deutschland entdecken", desc="Reisetipps zu Deutschlands schoensten Regionen in mehreren Sprachen.", r="../")
        + f'<main class="wrap"><h1>Deutschland entdecken</h1><p class="lead">Discover Germany · 探索德国 · Descubre Alemania · Découvrir l\'Allemagne</p><div class="grid">{items}</div></main>' + foot.format(r="../") + "</body></html>")
