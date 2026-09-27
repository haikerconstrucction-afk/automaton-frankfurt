"""Automatisches Posten der Kurzvideos auf Facebook-Seite, Instagram Reels und TikTok. Aktiv, sobald die Schluessel als Secrets hinterlegt sind."""
import os, json, time, urllib.request, urllib.parse
G = "https://graph.facebook.com/v21.0"
SITE = "https://haiktec.tech"

def req(method, url, data=None, headers=None, js=False):
    body = None; h = dict(headers or {})
    if data is not None:
        if js: body = json.dumps(data).encode(); h["Content-Type"] = "application/json; charset=UTF-8"
        else: body = urllib.parse.urlencode(data).encode()
    try: return json.load(urllib.request.urlopen(urllib.request.Request(url, data=body, method=method, headers=h), timeout=120))
    except urllib.error.HTTPError as e: raise RuntimeError(f"{e.code} {e.read()[:300].decode(errors='ignore')}")

def caption(v):
    return f"{v['title']}\n\n{v.get('hashtags','')} #haiktec #germany #deutschland #travel\nMehr: {SITE}/blog/{v['slug']}.html\nText, Stimme: KI · Fotos: Wikimedia Commons ({SITE}/videos/)"[:2100]

def facebook(v):
    t, pid = os.getenv("META_PAGE_TOKEN"), os.getenv("META_PAGE_ID")
    if not (t and pid): return None
    r = req("POST", f"{G}/{pid}/videos", {"file_url": f"{SITE}/videos/{v['slug']}.mp4", "description": caption(v), "access_token": t})
    return f"https://www.facebook.com/{pid}/videos/{r['id']}"

def instagram(v):
    t, ig = os.getenv("META_PAGE_TOKEN"), os.getenv("IG_USER_ID")
    if not (t and ig): return None
    c = req("POST", f"{G}/{ig}/media", {"media_type": "REELS", "video_url": f"{SITE}/videos/{v['slug']}.mp4", "caption": caption(v), "share_to_feed": "true", "access_token": t})["id"]
    for _ in range(30):
        st = req("GET", f"{G}/{c}?fields=status_code&access_token={t}").get("status_code")
        if st == "FINISHED": break
        if st == "ERROR": raise RuntimeError("Instagram-Verarbeitung fehlgeschlagen")
        time.sleep(10)
    r = req("POST", f"{G}/{ig}/media_publish", {"creation_id": c, "access_token": t})
    return f"instagram:{r['id']}"

def tiktok_token(s):
    ck, cs, rt = os.getenv("TIKTOK_CLIENT_KEY"), os.getenv("TIKTOK_CLIENT_SECRET"), s.get("tiktok_refresh") or os.getenv("TIKTOK_REFRESH_TOKEN")
    if not (ck and cs and rt): return None
    r = req("POST", "https://open.tiktokapis.com/v2/oauth/token/", {"client_key": ck, "client_secret": cs, "grant_type": "refresh_token", "refresh_token": rt},
            {"Content-Type": "application/x-www-form-urlencoded"})
    if r.get("refresh_token"): s["tiktok_refresh"] = r["refresh_token"]  # TikTok rotiert das Refresh-Token
    return r["access_token"]

def tiktok(v, s):
    tok = tiktok_token(s)
    if not tok: return None
    # Ohne TikTok-App-Pruefung sind nur private Posts erlaubt -> SELF_ONLY, Marcel schaltet in der App auf oeffentlich.
    priv = os.getenv("TIKTOK_PRIVACY", "SELF_ONLY")
    r = req("POST", "https://open.tiktokapis.com/v2/post/publish/video/init/", {
        "post_info": {"title": caption(v)[:2000], "privacy_level": priv, "disable_comment": False, "is_aigc": True},
        "source_info": {"source": "PULL_FROM_URL", "video_url": f"{SITE}/videos/{v['slug']}.mp4"}},
        {"Authorization": f"Bearer {tok}"}, js=True)
    return "tiktok:" + r.get("data", {}).get("publish_id", "?")

def post_all(s, log, max_per_run=1):
    done = 0
    for v in s.get("videos", []):
        if done >= max_per_run: break
        posted = v.setdefault("posted", {})
        todo = [n for n in ("facebook", "instagram", "tiktok") if n not in posted]
        if not todo: continue
        did = False
        for n in todo:
            try:
                url = facebook(v) if n == "facebook" else instagram(v) if n == "instagram" else tiktok(v, s)
                if url: posted[n] = url; log(f"Video gepostet ({n}): {v['title'][:60]}"); did = True
            except Exception as e:
                posted[n] = "fehler"; log(f"{n}-Fehler: {str(e)[:200]}")
        if did: done += 1
