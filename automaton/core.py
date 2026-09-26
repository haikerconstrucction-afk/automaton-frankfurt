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

def think(s):
    phase = CFG["phases"][s["phase"]]
    prompt = f"""Du bist ein autonomer Unternehmer-Agent. Du ueberlebst nur, wenn du Geld verdienst.
Kontostand: {s['balance_eur']} EUR. Umsatz bisher: {s['revenue_eur']} EUR. Phase: {phase['name']} - {phase['goal']}
Bisherige Produkte: {[p['title'] for p in s['products']]}
Regeln: legal, ehrlich, kein Spam, keine Finanz-/Rechtsberatung, deutsche Sprache.
Erstelle GENAU EIN neues, konkretes digitales Produkt, das Menschen wirklich nutzen. Antworte NUR als JSON:
{{"title":"...","slug":"kebab-case","price_eur":9,"target":"...","pitch":"2 Saetze","content_html":"<h2>...</h2> vollstaendiger Produktinhalt/Vorschau","reason":"warum es sich verkauft"}}"""
    key = os.getenv("LLM_API_KEY")
    if not key:  # Trockenlauf ohne Kosten
        return {"title": "Testprodukt", "slug": f"test-{len(s['products'])}", "price_eur": 5, "target": "Test",
                "pitch": "Trockenlauf.", "content_html": "<p>Demo</p>", "reason": "kein API-Key"}, 0
    body = json.dumps({"model": CFG["model"], "messages": [{"role": "user", "content": prompt}],
                       "response_format": {"type": "json_object"}}).encode()
    req = urllib.request.Request(os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1") + "/chat/completions",
                                 data=body, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    r = json.load(urllib.request.urlopen(req, timeout=120))
    text = r["choices"][0]["message"]["content"]
    cost = r.get("usage", {}).get("total_tokens", 4000) / 1000 * CFG["eur_per_1k_tokens"]
    return json.loads(re.search(r"\{.*\}", text, re.S).group(0)), min(cost, CFG["max_spend_per_run_eur"]) or 0.001

def act(s, p):
    link = os.getenv("STRIPE_PAYMENT_LINK_BASE", "")
    buy = f'<a class="buy" href="{link}">Jetzt kaufen – {p["price_eur"]} €</a>' if link else '<p class="buy">Kauf bald verfügbar</p>'
    html = f"""<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{p['title']}</title><link rel="stylesheet" href="../style.css"><main><a href="../">← Alle Produkte</a>
<h1>{p['title']}</h1><p class="pitch">{p['pitch']}</p>{buy}<article>{p['content_html']}</article></main></html>"""
    (ROOT/"site/products"/f"{p['slug']}.html").write_text(html)
    s["products"].append({k: p[k] for k in ("title", "slug", "price_eur", "target", "reason")} | {"created": now})

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
    r = json.load(urllib.request.urlopen(req, timeout=120))
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
    items = "".join(f'<li><a href="products/{p["slug"]}.html">{p["title"]}</a> – {p["price_eur"]} €</li>' for p in reversed(s["products"]))
    status = "LEBT" if s["alive"] else "TOT"
    (ROOT/"site/index.html").write_text(f"""<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Automaton Frankfurt</title><link rel="stylesheet" href="style.css"><main><h1>Automaton Frankfurt</h1>
<div class="kpis"><div><b>{status}</b>Status</div><div><b>{s['balance_eur']:.2f} €</b>Kontostand</div>
<div><b>{s['revenue_eur']:.2f} €</b>Umsatz</div><div><b>{life}</b>Restlebenszeit</div></div>
<p>Monatsumsatz: {monthly_revenue(s):.2f} € (Freelancer ab {CFG['freelancer']['min_monthly_revenue_eur']} €) · Jobs für Menschen: {sum(j['status']=='freigegeben' for j in s.get('jobs',[]))}</p><p>Phase: {CFG['phases'][s['phase']]['name']} · Alter: {days} Tage</p><h2>Produkte</h2><ul>{items}</ul></main></html>""")

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
        if not os.getenv("LLM_API_KEY"): raise RuntimeError("kein LLM_API_KEY - Schlafmodus")
        product, cost = think(s); book(s, -cost, f"KI-Denken: {product['title']}"); act(s, product)
    except Exception as e:
        s["log"].append({"t": now, "eur": 0, "why": f"Fehler: {e}"})
    try: freelancer_step(s)
    except Exception as e: s["log"].append({"t": now, "eur": 0, "why": f"Freelancer-Fehler: {e}"})
    if s["balance_eur"] <= 0: s["alive"] = False
    render(s); STATE_F.write_text(json.dumps(s, indent=2, ensure_ascii=False))
    print(f"Kontostand {s['balance_eur']} EUR, Produkte {len(s['products'])}")

if __name__ == "__main__": main()
