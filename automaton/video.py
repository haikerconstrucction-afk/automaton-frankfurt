"""KI-Kurzvideos (9:16) fuer Shorts/TikTok/Reels: freie Fotos + KI-Text + KI-Stimme. Kosten ~1 Cent."""
import json, subprocess, pathlib, tempfile, textwrap, asyncio, html
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import blog
VOICES = {"de": "de-DE-KatjaNeural", "en": "en-US-JennyNeural", "zh": "zh-CN-XiaoxiaoNeural", "es": "es-ES-ElviraNeural", "fr": "fr-FR-DeniseNeural"}
FONTS = {"zh": "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"}
W, H = 720, 1280

def font(lang, size):
    for f in [FONTS.get(lang, ""), "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]:
        try: return ImageFont.truetype(f, size)
        except Exception: pass
    return ImageFont.load_default()

def slide(photo_path, caption, lang, out, credit):
    im = Image.open(photo_path).convert("RGB")
    bg = im.copy(); bg = bg.resize((W, int(W * bg.height / bg.width)) if bg.width / bg.height > W / H else (int(H * bg.width / bg.height), H))
    bg = bg.resize((max(W, bg.width), max(H, bg.height))).crop((0, 0, W, H)).filter(ImageFilter.GaussianBlur(25))
    fg = im.copy(); fg.thumbnail((W, H)); bg.paste(fg, (0, (H - fg.height) // 2 - 120))
    d = ImageDraw.Draw(bg, "RGBA"); f = font(lang, 46)
    lines = [caption[i:i + 14] for i in range(0, len(caption), 14)] if lang == "zh" else textwrap.wrap(caption, 24)
    y = H - 140 - 62 * len(lines); d.rounded_rectangle((30, y - 24, W - 30, H - 110), 26, fill=(15, 61, 46, 225))
    for ln in lines: d.text((W // 2, y), ln, font=f, fill="white", anchor="ma"); y += 62
    d.text((W // 2, H - 80), "haiktec.tech", font=font(lang, 30), fill=(255, 255, 255, 230), anchor="ma")
    d.text((12, 12), credit[:90], font=font("de", 16), fill=(255, 255, 255, 200))
    bg.save(out, "JPEG", quality=88)

def make(s, llm_json, book, root, now):
    done = {v["slug"] for v in s.get("videos", [])}
    post = next((b for b in reversed(s.get("blog", [])) if b.get("img") and b["slug"] not in done), None)
    if not post: return
    lang = post["lang"]
    j, cost = llm_json(f"""Kurzvideo (30 Sekunden, 9:16) ueber '{post['topic']}' in Deutschland. WICHTIG: Einblendungen und Sprechertext komplett auf {dict(blog.LANGS)[lang]} (Sprachcode {lang}).
Gib 5 kurze Einblendungen (je max 45 Zeichen) und einen Sprechertext (70-90 Woerter, begeisternd, ohne erfundene Zahlen/Preise).
JSON: {{"captions":["..",".."],"voice":"...","hashtags":"#..."}}""")
    book(s, -cost, f"Video-Skript: {post['topic']}")
    tmp = pathlib.Path(tempfile.mkdtemp()); photos = []
    for q in ["", " landscape", " town", " nature", " panorama"]:
        ph = blog.commons_photo(post["topic"] + q)
        if ph and ph["url"] not in [p[1]["url"] for p in photos]:
            f = tmp / f"p{len(photos)}.jpg"
            try: blog.download(ph, f); photos.append((f, ph))
            except Exception: pass
    if len(photos) < 3: print("Video: zu wenige Fotos"); return
    caps = (j.get("captions") or [post["title"]])[:5]
    import edge_tts
    asyncio.run(edge_tts.Communicate(j["voice"], VOICES.get(lang, VOICES["en"])).save(str(tmp / "v.mp3")))
    dur = float(subprocess.run(["ffprobe", "-v", "0", "-show_entries", "format=duration", "-of", "csv=p=0", str(tmp / "v.mp3")], capture_output=True, text=True).stdout or 30) + 1
    n = len(caps); per = dur / n; parts = []
    for i, c in enumerate(caps):
        f, ph = photos[i % len(photos)]; sl = tmp / f"s{i}.jpg"
        slide(f, c, lang, sl, ph["credit"])
        o = tmp / f"c{i}.mp4"; frames = int(per * 25)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(sl), "-vf",
            f"scale={W*2}:{H*2},zoompan=z='min(zoom+0.0008,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps=25",
            "-t", f"{per:.2f}", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast", str(o)], check=True)
        parts.append(o)
    (tmp / "l.txt").write_text("".join(f"file '{p}'\n" for p in parts))
    out_dir = root / "site/videos"; out_dir.mkdir(parents=True, exist_ok=True); out = out_dir / f"{post['slug']}.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(tmp / "l.txt"), "-i", str(tmp / "v.mp3"),
        "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", "-c:a", "aac", "-b:a", "96k", "-shortest", str(out)], check=True)
    credits = "; ".join(sorted({p[1]["credit"] for p in photos}))
    s.setdefault("videos", []).append({"slug": post["slug"], "title": post["title"], "lang": lang, "created": now,
        "hashtags": j.get("hashtags", ""), "voice": j["voice"], "credits": credits})
    # nur die letzten 30 Videos behalten (Speicher)
    keep = {v["slug"] for v in s["videos"][-30:]}
    for f in out_dir.glob("*.mp4"):
        if f.stem not in keep: f.unlink()

def page(s, head, foot, root):
    vids = [v for v in reversed(s.get("videos", [])) if (root / f"site/videos/{v['slug']}.mp4").exists()]
    items = "".join(f'<div class="card"><video src="{v["slug"]}.mp4" controls preload="none" playsinline style="width:100%;aspect-ratio:9/16;background:#000;border-radius:12px"></video><div class="body"><h3>{html.escape(v["title"])}</h3><p style="font-size:.75rem">{html.escape(v["credits"])} · Stimme und Text: KI</p><p><a href="../blog/{v["slug"]}.html">Artikel lesen</a></p></div></div>' for v in vids)
    (root / "site/videos").mkdir(parents=True, exist_ok=True)
    (root / "site/videos/index.html").write_text(head.format(lang="de", title="Haiktec Videos – Deutschland in 30 Sekunden", desc="Kurze Reisevideos zu Deutschlands schoensten Orten, mit KI erstellt.", r="../")
        + f'<main class="wrap"><h1>Deutschland in 30 Sekunden</h1><p class="lead">Kurzvideos, mit KI erstellt.</p><div class="grid">{items or "<p>Die ersten Videos erscheinen in Kürze.</p>"}</div></main>' + foot.format(r="../") + "</body></html>")
