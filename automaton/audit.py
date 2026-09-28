"""Qualitaets-Audit aller Produkte im Verkauf: prueft die echte Datei (PDF/Excel) und nimmt fehlerhafte Produkte automatisch raus."""
import json, re, os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import core
AUDIT_V = 3
SUSPECT = re.compile(r"(studie|study|umfrage|survey|laut .{0,40}(universit|institut)|universit(ä|a)t .{0,30}\(20\d\d\)|\b\d{1,3}\s?%\s|prozent|percent|according to|forscher|researchers|statistik)", re.I)

def text_of(p):
    f = core.ROOT/"site/dl"/(p.get("file") or "")
    if not p.get("file") or not f.exists(): return None, ["Datei fehlt"]
    issues = []
    if p.get("type") == "ebook":
        from pypdf import PdfReader
        try: r = PdfReader(str(f)); t = "\n".join((pg.extract_text() or "") for pg in r.pages)
        except Exception as e: return None, [f"PDF defekt: {e}"]
        n = len(t) // 2 if p.get("language") == "zh" else len(t.split())
        if n < 1200: issues.append(f"zu kurz ({n} Woerter)")
        if len(r.pages) < 6: issues.append(f"nur {len(r.pages)} Seiten")
        return t, issues
    import openpyxl
    try: wb = openpyxl.load_workbook(str(f))
    except Exception as e: return None, [f"Excel defekt: {e}"]
    out, formulas, errs = [], 0, 0
    for ws in wb.worksheets:
        out.append(f"## Blatt {ws.title}")
        for row in ws.iter_rows(max_row=60):
            vals = []
            for c in row:
                v = c.value
                if v is None: continue
                if isinstance(v, str) and v.startswith("="): formulas += 1
                if isinstance(v, str) and v.startswith("#"): errs += 1
                vals.append(str(v)[:400])
            if vals: out.append(" | ".join(vals))
    if formulas < 3: issues.append(f"nur {formulas} Formeln")
    try:
        import excel_pro; chk = excel_pro.recalc_check(f)
        if chk:
            if chk["errors"]: issues.append(f"{chk['errors']} Formelfehler")
            out.append("## Berechnete Kennzahlen (pruefe Plausibilitaet gegen die Beispieldaten!): " + str(chk["kpis"]))
    except Exception as e: print("recalc:", e)
    if errs: issues.append(f"{errs} Fehlerwerte")
    return "\n".join(out), issues

def judge(p, t):
    hits = sorted({m.group(0) for m in SUSPECT.finditer(t)})[:15]
    lang = {"de": "Deutsch", "en": "Englisch", "es": "Spanisch", "fr": "Franzoesisch", "zh": "Chinesisch"}.get(p.get("language"), "Deutsch")
    sample = t[:9000] if len(t) < 9000 else t[:6000] + "\n...\n" + t[-3000:]
    r, cost = core.llm_json(f"""Du bist ein strenger Endkontrolleur fuer digitale Produkte, die gerade verkauft werden. {core.RULES}
Titel: {p['title']} | Preis: {p.get('price_eur')} | Soll-Sprache: {lang} | Typ: {p.get('type')}
Auffaellige Stellen (Regex-Treffer, pruefe ob erfunden): {hits}
Pruefe den ECHTEN Inhalt auf: erfundene Studien, Statistiken, Prozentzahlen, Quellen oder Zitate; falsche oder gemischte Sprache;
unfertige/abgebrochene Texte, Platzhalter wie [Name] oder Lorem; Wiederholungen; sachliche Fehler; Rechts-, Steuer-, Finanz- oder Medizinberatung;
Gesundheitsversprechen; fremde Marken/Figuren; Formeln/Tabellen, die keinen Sinn ergeben.
Inhalt:
{sample}
Hinweis: Excel-Zellinhalte koennen zur Pruefung gekuerzt sein - das ist KEIN Fehler des Produkts.
STRENG: Jede konkrete Prozentzahl, Statistik oder Wirkungsbehauptung ("80 % der...", "400 % produktiver", "Studien zeigen") ohne allgemein bekannte Grundlage = erfunden = remove true.
Erlaubt sind nur allgemein bekannte Fakten (z. B. 19 % MwSt, 50-30-20-Regel als Faustregel, Beispielrechnungen die klar als Beispiel markiert sind).
Antworte NUR als JSON: {{"score": 1-10, "remove": true|false, "invented_numbers": ["..."], "reasons": "kurz, deutsch"}}  remove=true bei jedem klaren Regelverstoss oder score<6.""")
    return r or {}, cost

def retire(s, p, why):
    if p.get("payment_link_id") and os.getenv("STRIPE_SECRET_KEY"):
        try: core.stripe("POST", f"payment_links/{p['payment_link_id']}", {"active": "false"})
        except Exception as e: print("Stripe:", e)
    url = p.get("channels", {}).get("etsy")
    if url and os.getenv("ETSY_API_KEY"):
        try:
            import channels; e = channels.CHANNELS[0]; lid = url.rstrip("/").split("/")[-1]
            channels.http("PATCH", f"https://api.etsy.com/v3/application/shops/{e.shop()}/listings/{lid}", e.h(), {"state": "inactive"}, form=True)
            p["channels"]["etsy_inactive"] = True
        except Exception as ex: print("Etsy:", ex, getattr(ex, "read", lambda: b"")()[:200])
    p["retired"] = True; p["retired_why"] = why[:300]; p.pop("pay_url", None)
    for f in [core.ROOT/"site/products"/f"{p['slug']}.html", core.ROOT/"site/dl"/(p.get("file") or "_none_")]:
        if f.exists() and f.is_file(): f.unlink()
    core.book(s, 0, f"Audit entfernt: {p['title'][:80]} – {why[:160]}")

def run(s, limit=100):
    checked = removed = 0
    for p in s["products"]:
        if p.get("retired") or p.get("audit_v") == AUDIT_V: continue
        if checked >= limit: break
        checked += 1
        t, issues = text_of(p)
        if t is None: retire(s, p, "; ".join(issues)); removed += 1; continue
        r, cost = judge(p, t); core.book(s, -max(cost, 0.0005), f"Audit: {p['title'][:80]}")
        p["audit_v"], p["audit_score"], p["audit_note"] = AUDIT_V, r.get("score"), r.get("reasons", "")[:300]
        hard = [i for i in issues if not i.startswith("nur") or "Formeln" in i]
        if r.get("invented_numbers"): r["reasons"] = (r.get("reasons", "") + " Erfundene Zahlen: " + ", ".join(map(str, r["invented_numbers"]))[:200])
        if r.get("remove") or (r.get("score") is not None and int(r["score"]) < 6) or hard:
            retire(s, p, "; ".join(hard + [r.get("reasons", "")])); removed += 1
        print(p["slug"], r.get("score"), r.get("remove"), issues, (r.get("reasons") or "")[:120])
    return checked, removed

if __name__ == "__main__":
    s = core.load(); c, r = run(s)
    s["log"].append({"t": core.now, "eur": 0, "why": f"Audit: {c} geprueft, {r} entfernt"})
    core.render(s); core.STATE_F.write_text(json.dumps(s, indent=2, ensure_ascii=False))
    print("geprueft", c, "entfernt", r)
