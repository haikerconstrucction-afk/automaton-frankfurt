"""Automaton-Kern: denkt, handelt, bucht Kosten - und stirbt bei 0 EUR."""
import json, os, re, datetime, pathlib, urllib.request
ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = json.loads((ROOT/"config.json").read_text())
STATE_F = ROOT/"state.json"
now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None).isoformat(timespec="seconds")

def load():
    if STATE_F.exists(): return json.loads(STATE_F.read_text())
    return {"born": now, "balance_eur": CFG["start_budget_eur"], "spent_eur": 0, "revenue_eur": 0,
            "phase": 0, "phase_started": now, "products": [], "log": [], "alive": True}

def book(s, amount, why):
    s["balance_eur"] = round(s["balance_eur"] + amount, 4)
    if amount < 0: s["spent_eur"] = round(s["spent_eur"] - amount, 4)
    else: s["revenue_eur"] = round(s["revenue_eur"] + amount, 4)
    s["log"].append({"t": now, "eur": amount, "why": why}); s["log"] = s["log"][-200:]

def stripe_revenue():
    key = os.getenv("STRIPE_SECRET_KEY")
    if not key: return None
    req = urllib.request.Request("https://api.stripe.com/v1/balance_transactions?limit=100&type=charge",
                                 headers={"Authorization": f"Bearer {key}"})
    data = json.load(urllib.request.urlopen(req, timeout=30))["data"]
    return sum(t["net"] for t in data) / 100  # netto nach Gebuehren

SITE = "https://haikerconstrucction-afk.github.io/automaton-frankfurt"

def stripe(method, path, data=None):
    import urllib.parse
    key = os.getenv("STRIPE_SECRET_KEY")
    body = urllib.parse.urlencode(data or {}).encode() if data else None
    req = urllib.request.Request("https://api.stripe.com/v1/" + path, data=body, method=method,
                                 headers={"Authorization": f"Bearer {key}"})
    return json.load(urllib.request.urlopen(req, timeout=30))

def ensure_payment_link(p):
    """Eigenes Produkt + Preis + Zahlungslink in Stripe; nach Kauf Weiterleitung zum Download."""
    if not os.getenv("STRIPE_SECRET_KEY") or p.get("pay_url") or not p.get("file") or p.get("retired") or not sales_enabled(): return
    prod = stripe("POST", "products", {"name": p["title"], "metadata[slug]": p["slug"]})
    cur = "usd" if p.get("language") == "en" else "eur"
    price = stripe("POST", "prices", {"product": prod["id"], "currency": cur, "unit_amount": int(float(p["price_eur"]) * 100)})
    link = stripe("POST", "payment_links", {"line_items[0][price]": price["id"], "line_items[0][quantity]": 1,
        "after_completion[type]": "redirect", "after_completion[redirect][url]": f"{SITE}/dl/{p['file']}",
        "automatic_tax[enabled]": "false", "metadata[slug]": p["slug"]})
    p["pay_url"], p["payment_link_id"] = link["url"], link["id"]

def count_sales(s):
    if not os.getenv("STRIPE_SECRET_KEY"): return
    for p in s["products"]:
        if p.get("payment_link_id"):
            r = stripe("GET", f"checkout/sessions?payment_link={p['payment_link_id']}&status=complete&limit=100")
            p["sales"] = len(r["data"])

RULES = """Regeln: legal, ehrlich, kein Spam, keine Finanz-/Rechts-/Steuerberatung, keine Steuer- oder Pauschalwerte,
keine Vertraege/Rechtsvorlagen, keine Gesundheitsversprechen, keine Marken/Figuren/Personen Dritter, keine Kopien bestehender Werke.
Aktuelles Jahr: 2026."""

TYPES = {
 "excel": """eine Excel-Vorlage (Tracker/Planer/Rechner) mit ECHTEN Formeln. JSON:
{"type":"excel","title":"...","slug":"kebab-case","price_eur":7,"target":"...","language":"de|en","pitch":"2 Saetze","content_html":"<h2>Inhalt</h2>...",
"guide":["Schritt 1",...],"sheets":[{"name":"max 30 Zeichen","columns":["..."],"rows":[["Wert","=B2*C2",...]],"blank_rows":30,"total_row":["Summe","","=SUM(C2:C40)"]}],"reason":"..."}
Formeln als Strings mit '=' (englische Funktionsnamen, Komma als Trenner). Mind. 5 Beispielzeilen mit Datum 2026, blank_rows fuer Nutzer.""",
 "ebook": """ein kurzes E-Book (Ratgeber mit konkreten Schritten ODER eine Sammlung origineller Kurzgeschichten, z.B. Gute-Nacht-Geschichten fuer Kinder). JSON:
{"type":"ebook","title":"...","slug":"kebab-case","price_eur":5,"target":"...","language":"de|en","pitch":"2 Saetze","content_html":"<h2>Inhalt</h2> Inhaltsverzeichnis + Leseprobe",
"chapters":[{"heading":"...","text":"mind. 350 Woerter, Absaetze mit \\n\\n getrennt"}],"reason":"..."}
Mindestens 6 Kapitel.""",
}

def think(s):
    phase = CFG["phases"][s["phase"]]
    live = [p for p in s["products"] if not p.get("retired")]
    kind = ["excel", "ebook"][len(s["products"]) % 2]
    market = "Deutschland (Deutsch)" if (len(s["products"]) // 2) % 2 == 0 else "weltweit (Englisch)"
    prompt = f"""Du bist ein autonomer Unternehmer-Agent und ueberlebst nur, wenn Menschen deine Produkte kaufen.
Kontostand {s['balance_eur']:.2f} EUR, Umsatz {s['revenue_eur']:.2f} EUR. Phase: {phase['goal']}
Bestehende Produkte (nicht wiederholen): {[p['title'] for p in s['products']]}
Verkaufszahlen: {[(p['title'], p.get('sales',0)) for p in live]}
{RULES}
Markt: {market}. Erstelle GENAU EIN neues Produkt: {TYPES[kind]}
Es muss den Preis klar wert sein. Antworte NUR als JSON."""
    p, cost = llm_json(prompt)
    if p is None:
        raise RuntimeError("kein LLM_API_KEY - Schlafmodus")
    p["type"] = kind
    if kind == "ebook":  # Kapitel einzeln schreiben lassen -> echte Laenge
        for ch in p.get("chapters", [])[:10]:
            r, c = llm_json(f"""Schreibe Kapitel "{ch['heading']}" des E-Books "{p['title']}" ({p.get('language','de')}), Zielgruppe {p.get('target')}.
{RULES} 450-700 Woerter, konkret, originell, gut lesbar, Absaetze mit \\n\\n. Nur JSON: {{"text":"..."}}""")
            cost += c
            if r and r.get("text"): ch["text"] = r["text"]
    return p, max(cost, 0.001)

def review(p):
    """Zweite KI prueft Qualitaet und Regeln. Nur Score >= 7 geht in den Verkauf."""
    sample = json.dumps({k: p.get(k) for k in ("title", "price_eur", "target", "guide", "sheets", "chapters")}, ensure_ascii=False)[:12000]
    r, cost = llm_json(f"""Du bist ein strenger Qualitaetspruefer fuer digitale Produkte. {RULES}
Wuerde ein zahlender Kunde dieses Produkt fuer {p.get('price_eur')} EUR als fair empfinden? Verstoesst es gegen eine Regel?
Pruefe bei Excel, ob Formeln sinnvoll sind. Produkt: {sample}
Antworte NUR als JSON: {{"score": 1-10, "rule_violation": true|false, "issues": "kurz"}}""")
    ok = r and int(r.get("score", 0)) >= 7 and not r.get("rule_violation")
    return bool(ok), r, cost

def build_excel(p, path):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    wb = Workbook(); ws = wb.active; ws.title = "Anleitung" if p.get("language","de") == "de" else "Guide"
    ws.append([p["title"]]); ws["A1"].font = Font(bold=True, size=14)
    for i, g in enumerate(p.get("guide", []), 1): ws.append([f"{i}. {g}"])
    ws.column_dimensions["A"].width = 100
    n = 0; formulas = 0
    for sh in p.get("sheets", [])[:6]:
        w = wb.create_sheet(str(sh["name"])[:30].replace("/", "-"))
        w.append(sh["columns"])
        for c in w[1]: c.font = Font(bold=True, color="FFFFFF"); c.fill = PatternFill("solid", fgColor="0B6E4F")
        for r in sh.get("rows", [])[:300]:
            row = []
            for x in r:
                if isinstance(x, str) and x.startswith("="): formulas += 1; row.append(x)
                else:
                    try: row.append(float(x) if isinstance(x, str) and re.fullmatch(r"-?\d+(\.\d+)?", x) else x)
                    except Exception: row.append(x)
            w.append(row); n += 1
        for _ in range(int(sh.get("blank_rows", 20))): w.append([None])
        if sh.get("total_row"): w.append(sh["total_row"]); [setattr(c, "font", Font(bold=True)) for c in w[w.max_row]]
        for col in w.columns: w.column_dimensions[col[0].column_letter].width = 22
        w.freeze_panes = "A2"
    wb.save(path)
    if p["type"] == "excel" and formulas < 3: raise RuntimeError("Excel ohne echte Formeln - verworfen")
    return n

def build_pdf(p, path):
    from reportlab.lib.pagesizes import A5
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from xml.sax.saxutils import escape
    st = getSampleStyleSheet(); story = [Spacer(1, 120), Paragraph(escape(p["title"]), st["Title"]),
                                         Paragraph(escape(p.get("pitch", "")), st["Italic"]), PageBreak()]
    words = 0
    for ch in p.get("chapters", []):
        story.append(Paragraph(escape(ch["heading"]), st["Heading2"]))
        for para in str(ch["text"]).split("\n\n"):
            words += len(para.split()); story += [Paragraph(escape(para), st["BodyText"]), Spacer(1, 6)]
        story.append(PageBreak())
    SimpleDocTemplate(str(path), pagesize=A5, title=p["title"]).build(story)
    if words < 1500: raise RuntimeError(f"E-Book zu kurz ({words} Woerter) - verworfen")
    return words

def build_file(p):
    import secrets
    d = ROOT/"site/dl"; d.mkdir(parents=True, exist_ok=True)
    ext = "pdf" if p["type"] == "ebook" else "xlsx"
    name = f"{p['slug']}-{secrets.token_hex(8)}.{ext}"
    size = (build_pdf if ext == "pdf" else build_excel)(p, d/name)
    return name, size

def page(p):
    cur = "$" if p.get("language") == "en" else "€"
    buy = (f'<a class="buy" href="{p["pay_url"]}">Jetzt kaufen – {p["price_eur"]} {cur}</a>' if p.get("pay_url")
           else '<p class="buy">Verkauf startet in Kürze</p>')
    html = f"""<!doctype html><html lang="{p.get('language','de')}"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{p['title']}</title><link rel="stylesheet" href="../style.css"><main><a href="../">← Alle Produkte</a>
<h1>{p['title']}</h1><p class="pitch">{p.get('pitch','')}</p>{buy}<article>{p.get('content_html','')}</article>
<p><small>Digitales Produkt ({"PDF" if p.get("type")=="ebook" else "Excel"}), sofortiger Download nach Zahlung. Endpreis, gemäß § 19 UStG wird keine Umsatzsteuer berechnet. Mit dem Kauf stimmen Sie zu, dass die Bereitstellung sofort beginnt, und bestätigen, dass Ihr Widerrufsrecht damit erlischt. <a href="../agb.html">AGB</a> · <a href="../widerruf.html">Widerruf</a> · <a href="../impressum.html">Impressum</a> · <a href="../datenschutz.html">Datenschutz</a></small></p></main></html>"""
    (ROOT/"site/products").mkdir(parents=True, exist_ok=True)
    (ROOT/"site/products"/f"{p['slug']}.html").write_text(html)

def act(s, p):
    ok, verdict, cost = review(p); book(s, -max(cost, 0.001), f"KI-Pruefung: {p['title']}")
    if not ok: raise RuntimeError(f"Qualitaetspruefung nicht bestanden: {verdict}")
    fname, size = build_file(p)
    rec = {k: p.get(k) for k in ("type", "title", "slug", "price_eur", "target", "reason", "language", "pitch", "content_html")}
    rec |= {"created": now, "file": fname, "size": size, "sales": 0, "score": verdict.get("score"), "quality": 2}
    s["products"].append(rec)

def sales_enabled():
    import legal
    return legal.build()

def retire_old(s):
    """Produkte der ersten Generation (ohne Formeln/Pruefung) aus dem Verkauf nehmen."""
    for p in s["products"]:
        if p.get("quality") != 2 and not p.get("retired"):
            if p.get("payment_link_id") and os.getenv("STRIPE_SECRET_KEY"):
                stripe("POST", f"payment_links/{p['payment_link_id']}", {"active": "false"})
            p["retired"] = True; p.pop("pay_url", None)
            f = ROOT/"site/products"/f"{p['slug']}.html"
            if f.exists(): f.unlink()
            if p.get("file") and (ROOT/"site/dl"/p["file"]).exists(): (ROOT/"site/dl"/p["file"]).unlink()

def monthly_revenue(s):
    cutoff = datetime.datetime.fromisoformat(now) - datetime.timedelta(days=30)
    return sum(e["eur"] for e in s["log"] if e["eur"] > 0 and datetime.datetime.fromisoformat(e["t"]) >= cutoff)

def llm_json(prompt):
    key = os.getenv("LLM_API_KEY")
    if not key: return None, 0
    body = json.dumps({"model": CFG["model"], "messages": [{"role": "user", "content": prompt}],
                       "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request(os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1") + "/chat/completions",
                                 data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=300))
    cost = r.get("usage", {}).get("total_tokens", 4000) / 1000 * CFG["eur_per_1k_tokens"]
    return json.loads(re.search(r"\{.*\}", r["choices"][0]["message"]["content"], re.S).group(0)), cost

def gh(*args):
    import subprocess
    return subprocess.run(["gh", *args], capture_output=True, text=True).stdout

def freelancer_step(s):
    """Ab 1.000 EUR Monatsumsatz: Auftraege an Menschen vorschlagen - nur mit Freigabe des Inhabers."""
    f = CFG["freelancer"]; mr = monthly_revenue(s)
    s.setdefault("jobs", [])
    # 1) Freigaben pruefen: Issue mit Label 'freigegeben' -> Budget reservieren
    if os.getenv("GITHUB_TOKEN"):
        for j in s["jobs"]:
            if j["status"] == "wartet_auf_freigabe":
                labels = gh("issue", "view", str(j["issue"]), "--json", "labels,state", "-q", "[.labels[].name]|join(\",\")")
                if "freigegeben" in labels:
                    j["status"] = "freigegeben"; book(s, -j["budget_eur"], f"Freelancer-Auftrag: {j['title']}")
                elif "abgelehnt" in labels:
                    j["status"] = "abgelehnt"
    if mr < f["min_monthly_revenue_eur"]: return
    budget_left = mr * f["max_share_of_monthly_revenue"] - sum(j["budget_eur"] for j in s["jobs"]
        if j["status"] in ("freigegeben", "wartet_auf_freigabe") and j["created"][:7] == now[:7])
    if budget_left < 50 or any(j["status"] == "wartet_auf_freigabe" for j in s["jobs"]): return
    job, cost = llm_json(f"""Monatsumsatz {mr:.0f} EUR. Produkte: {[p['title'] for p in s['products']][-20:]}.
Welche EINE Aufgabe sollte ein menschlicher Freelancer uebernehmen, um den Umsatz am meisten zu steigern
(z.B. Design, Lektorat, Kundensupport, Vertrieb an lokale Firmen)? Max. {min(budget_left, f['max_job_eur']):.0f} EUR, fair bezahlt.
Nur JSON: {{"title":"...","budget_eur":150,"platform":"Upwork/Fiverr/Malt","description":"Stellenbeschreibung auf Deutsch","expected_impact":"..."}}""")
    if not job: return
    book(s, -cost, "KI-Denken: Freelancer-Vorschlag")
    job["budget_eur"] = min(float(job["budget_eur"]), budget_left, f["max_job_eur"])
    body = (f"**Budget:** {job['budget_eur']:.0f} €  \n**Plattform:** {job['platform']}  \n**Erwartete Wirkung:** {job['expected_impact']}\n\n"
            f"{job['description']}\n\n---\nLabel `freigegeben` setzen = Auftrag genehmigen, `abgelehnt` = verwerfen.")
    url = gh("issue", "create", "--title", f"[Freelancer] {job['title']}", "--body", body, "--label", "freelancer").strip()
    s["jobs"].append({"title": job["title"], "budget_eur": job["budget_eur"], "issue": url.rsplit("/", 1)[-1] or "0",
                      "status": "wartet_auf_freigabe", "created": now})

def render(s):
    days = (datetime.datetime.fromisoformat(now) - datetime.datetime.fromisoformat(s["born"])).days
    burn = s["spent_eur"] / max(days, 1)
    life = "∞" if burn == 0 else f"{int(s['balance_eur']/burn)} Tage"
    items = "".join(f'<li><a href="products/{p["slug"]}.html">{p["title"]}</a> – {p["price_eur"]} {"$" if p.get("language")=="en" else "€"} · {p.get("sales",0)} verkauft</li>' for p in reversed(s["products"]) if not p.get("retired"))
    status = "LEBT" if s["alive"] else "TOT"
    (ROOT/"site/index.html").write_text(f"""<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Automaton Frankfurt</title><link rel="stylesheet" href="style.css"><main><h1>Automaton Frankfurt</h1>
<div class="kpis"><div><b>{status}</b>Status</div><div><b>{s['balance_eur']:.2f} €</b>Kontostand</div>
<div><b>{s['revenue_eur']:.2f} €</b>Umsatz</div><div><b>{life}</b>Restlebenszeit</div></div>
<p>Monatsumsatz: {monthly_revenue(s):.2f} € (Freelancer ab {CFG['freelancer']['min_monthly_revenue_eur']} €) · Jobs für Menschen: {sum(j['status']=='freigegeben' for j in s.get('jobs',[]))}</p><p>Phase: {CFG['phases'][s['phase']]['name']} · Alter: {days} Tage</p><h2>Produkte</h2><ul>{items}</ul>
<footer><a href="impressum.html">Impressum</a> · <a href="agb.html">AGB</a> · <a href="widerruf.html">Widerruf</a> · <a href="datenschutz.html">Datenschutz</a></footer></main></html>""")

def main():
    s = load()
    if not s["alive"]: print("Automaton ist tot."); return
    rev = stripe_revenue()
    if rev is not None and rev > s.get("stripe_seen", 0):
        book(s, rev - s.get("stripe_seen", 0), "Stripe-Umsatz"); s["stripe_seen"] = rev
    started = datetime.datetime.fromisoformat(s["phase_started"])
    if s["phase"] + 1 < len(CFG["phases"]) and (datetime.datetime.fromisoformat(now) - started).days >= CFG["phases"][s["phase"]]["min_days"]:
        s["phase"] += 1; s["phase_started"] = now
    try:
        product, cost = think(s); book(s, -cost, f"KI-Denken: {product['title']}"); act(s, product)
    except Exception as e:
        s["log"].append({"t": now, "eur": 0, "why": f"Fehler: {e}"})
    try: retire_old(s)
    except Exception as e: s["log"].append({"t": now, "eur": 0, "why": f"Retire-Fehler: {e}"})
    for p in [x for x in s["products"] if not x.get("retired")]:
        try: ensure_payment_link(p)
        except Exception as e: s["log"].append({"t": now, "eur": 0, "why": f"Stripe-Fehler {p['slug']}: {e}"})
        if p.get("content_html") is not None or p.get("pay_url"): page(p)
    try: count_sales(s)
    except Exception as e: s["log"].append({"t": now, "eur": 0, "why": f"Verkaufszaehlung-Fehler: {e}"})
    try: freelancer_step(s)
    except Exception as e: s["log"].append({"t": now, "eur": 0, "why": f"Freelancer-Fehler: {e}"})
    if s["balance_eur"] <= 0: s["alive"] = False
    render(s); STATE_F.write_text(json.dumps(s, indent=2, ensure_ascii=False))
    print(f"Kontostand {s['balance_eur']} EUR, Produkte {len(s['products'])}")

if __name__ == "__main__": main()
