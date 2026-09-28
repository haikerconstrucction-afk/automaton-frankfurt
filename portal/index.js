// Haiktec Portal ("Krake"): ein System, viele Mandanten. Jeder Mandant sieht nur seine eigenen Daten.
// Speicher: Cloudflare KV, alle Mandantendaten unter dem Praefix t:<tenantId>: - Zugriff nur ueber die Sitzung des Nutzers.
const ORIGINS = ["https://haiktec.tech", "https://www.haiktec.tech"];
const MODULES = ["geo", "mahn", "aufgaben"];
const enc = new TextEncoder();
const hex = b => [...new Uint8Array(b)].map(x => x.toString(16).padStart(2, "0")).join("");
const rid = (n = 16) => hex(crypto.getRandomValues(new Uint8Array(n)));
async function hash(pw, salt) {
  const k = await crypto.subtle.importKey("raw", enc.encode(pw), "PBKDF2", false, ["deriveBits"]);
  return hex(await crypto.subtle.deriveBits({ name: "PBKDF2", salt: enc.encode(salt), iterations: 100000, hash: "SHA-256" }, k, 256));
}
function eq(a, b) { if (a.length !== b.length) return false; let r = 0; for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i); return r === 0; }
const B32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
function b32dec(s) { let bits = "", out = []; for (const c of s.replace(/=+$/, "").toUpperCase()) { const v = B32.indexOf(c); if (v < 0) continue; bits += v.toString(2).padStart(5, "0"); }
  for (let i = 0; i + 8 <= bits.length; i += 8) out.push(parseInt(bits.slice(i, i + 8), 2)); return new Uint8Array(out); }
function b32enc(bytes) { let bits = [...bytes].map(b => b.toString(2).padStart(8, "0")).join(""), o = ""; for (let i = 0; i < bits.length; i += 5) o += B32[parseInt(bits.slice(i, i + 5).padEnd(5, "0"), 2)]; return o; }
async function totp(secret, step) {
  const key = await crypto.subtle.importKey("raw", b32dec(secret), { name: "HMAC", hash: "SHA-1" }, false, ["sign"]);
  const msg = new ArrayBuffer(8); new DataView(msg).setUint32(4, step);
  const h = new Uint8Array(await crypto.subtle.sign("HMAC", key, msg)); const o = h[19] & 15;
  return String((((h[o] & 127) << 24) | (h[o + 1] << 16) | (h[o + 2] << 8) | h[o + 3]) % 1000000).padStart(6, "0");
}
async function totpOk(secret, code) { const st = Math.floor(Date.now() / 30000); for (const d of [-1, 0, 1]) if (eq(await totp(secret, st + d), String(code || "").trim())) return true; return false; }
const clean = (v, n = 200) => String(v ?? "").replace(/[<>]/g, "").slice(0, n);

export default {
  async fetch(req, env) {
    const origin = req.headers.get("origin") || "";
    const cors = { "Access-Control-Allow-Origin": ORIGINS.includes(origin) ? origin : ORIGINS[0], "Access-Control-Allow-Headers": "content-type,authorization",
      "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS", "Vary": "Origin" };
    const J = (o, s = 200) => new Response(JSON.stringify(o), { status: s, headers: { ...cors, "content-type": "application/json", "cache-control": "no-store" } });
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    const url = new URL(req.url), path = url.pathname, KV = env.KV;
    let b = {}; if (req.method === "POST") { try { b = await req.json(); } catch {} }
    const ip = req.headers.get("cf-connecting-ip") || "x";
    const audit = async (tid, who, what) => KV.put(`t:${tid}:audit:${Date.now()}:${rid(3)}`, JSON.stringify({ t: new Date().toISOString(), who, what: clean(what, 300) }), { expirationTtl: 31536000 });

    // --- Einrichtung: nur mit geheimem Admin-Token (einmalig Marcel als Plattform-Admin einladen)
    if (path === "/bootstrap") {
      if (!env.ADMIN_TOKEN || !eq(req.headers.get("authorization") || "", "Bearer " + env.ADMIN_TOKEN)) return J({ error: "forbidden" }, 403);
      const email = clean(b.email, 120).toLowerCase(); const tok = rid(24);
      await KV.put("tenant:haiktec", JSON.stringify({ id: "haiktec", name: "Haiktec (Plattform)", branche: "plattform", modules: MODULES, created: Date.now() }));
      await KV.put("invite:" + tok, JSON.stringify({ email, tid: "haiktec", role: "superadmin", name: clean(b.name) }), { expirationTtl: 604800 });
      return J({ invite: `https://haiktec.tech/portal/?invite=${tok}` });
    }
    // --- Einladung annehmen: Passwort setzen
    if (path === "/auth/accept") {
      const inv = JSON.parse(await KV.get("invite:" + clean(b.token, 80)) || "null");
      if (!inv) return J({ error: "Einladung ungültig oder abgelaufen" }, 400);
      if (String(b.password || "").length < 10) return J({ error: "Passwort: mindestens 10 Zeichen" }, 400);
      if (!b.accept_terms) return J({ error: "Bitte AGB und Datenschutz bestätigen" }, 400);
      const salt = rid(16);
      await KV.put("user:" + inv.email, JSON.stringify({ id: rid(8), email: inv.email, tid: inv.tid, role: inv.role, name: inv.name || "", salt, pw: await hash(b.password, salt), created: Date.now() }));
      await KV.delete("invite:" + b.token); await audit(inv.tid, inv.email, "Konto aktiviert");
      return J({ ok: true });
    }
    // --- Login mit Sperre nach Fehlversuchen
    if (path === "/auth/login") {
      const email = clean(b.email, 120).toLowerCase(), fk = `fail:${ip}`;
      const fails = +(await KV.get(fk) || 0); if (fails >= 8) return J({ error: "Zu viele Versuche. Bitte 15 Minuten warten." }, 429);
      const u = JSON.parse(await KV.get("user:" + email) || "null");
      if (!u || !eq(await hash(String(b.password || ""), u.salt), u.pw)) { await KV.put(fk, String(fails + 1), { expirationTtl: 900 }); return J({ error: "E-Mail oder Passwort falsch" }, 401); }
      const cc = req.cf?.country || "XX";
      const tn = JSON.parse(await KV.get("tenant:" + u.tid) || "null");
      if (u.role !== "superadmin" && tn?.countries?.length && !tn.countries.includes(cc)) { await audit(u.tid, email, `Anmeldung aus ${cc} blockiert`); return J({ error: "Zugriff aus diesem Land nicht freigegeben" }, 403); }
      if (u.totp) { if (!b.code) return J({ need2fa: true }); if (!(await totpOk(u.totp, b.code))) { await KV.put(fk, String(fails + 1), { expirationTtl: 900 }); return J({ error: "Code falsch", need2fa: true }, 401); } }
      const s = rid(32); await KV.put("sess:" + s, JSON.stringify({ email, tid: u.tid, role: u.role, cc, ua: (req.headers.get("user-agent") || "").slice(0, 120), need2fa: !u.totp && u.role !== "user" }), { expirationTtl: 43200 });
      await audit(u.tid, email, "Anmeldung"); return J({ token: s });
    }
    // --- ab hier: nur mit gueltiger Sitzung
    const tok = (req.headers.get("authorization") || "").replace(/^Bearer /, "");
    const S = tok && JSON.parse(await KV.get("sess:" + tok) || "null");
    if (!S) return J({ error: "Bitte anmelden" }, 401);
    const T = JSON.parse(await KV.get("tenant:" + S.tid) || "null"); if (!T || T.locked) return J({ error: "Mandant gesperrt" }, 403);
    const cc = req.cf?.country || "XX";
    if (S.role !== "superadmin" && T.countries?.length && !T.countries.includes(cc)) return J({ error: "Zugriff aus diesem Land nicht freigegeben" }, 403);
    if (S.ua !== (req.headers.get("user-agent") || "").slice(0, 120)) { await KV.delete("sess:" + tok); return J({ error: "Bitte anmelden" }, 401); }
    // 2FA einrichten (Pflicht fuer Administratoren, bevor sie Daten sehen)
    if (path === "/auth/2fa/setup") { const sec = b32enc(crypto.getRandomValues(new Uint8Array(20))); await KV.put("totp_pending:" + S.email, sec, { expirationTtl: 900 });
      return J({ secret: sec, uri: `otpauth://totp/Haiktec:${encodeURIComponent(S.email)}?secret=${sec}&issuer=Haiktec` }); }
    if (path === "/auth/2fa/enable") { const sec = await KV.get("totp_pending:" + S.email); if (!sec || !(await totpOk(sec, b.code))) return J({ error: "Code falsch" }, 400);
      const u = JSON.parse(await KV.get("user:" + S.email)); u.totp = sec; await KV.put("user:" + S.email, JSON.stringify(u)); S.need2fa = false; await KV.put("sess:" + tok, JSON.stringify(S), { expirationTtl: 43200 });
      await audit(S.tid, S.email, "Zwei-Faktor-Anmeldung aktiviert"); return J({ ok: true }); }
    if (S.need2fa && path !== "/me" && path !== "/auth/logout") return J({ error: "Bitte zuerst die Zwei-Faktor-Anmeldung einrichten", need2fa_setup: true }, 403);
    const P = `t:${S.tid}:`;  // Mandanten-Praefix: ALLE Daten-Zugriffe laufen hierueber
    const isAdmin = S.role === "admin" || S.role === "superadmin", isSuper = S.role === "superadmin";
    const list = async (kind, lim = 200) => { const r = await KV.list({ prefix: P + kind + ":", limit: lim }); return (await Promise.all(r.keys.map(k => KV.get(k.name)))).map(x => JSON.parse(x)).filter(Boolean); };

    if (path === "/auth/logout") { await KV.delete("sess:" + tok); return J({ ok: true }); }
    if (path === "/me") return J({ email: S.email, role: S.role, need2fa_setup: !!S.need2fa, tenant: { id: T.id, name: T.name, branche: T.branche, modules: T.modules, lang: T.lang || "de", countries: T.countries || [] } });

    // Plattform-Admin (nur Marcel): Mandanten anlegen und Admins einladen
    if (path === "/super/tenants") {
      if (!isSuper) return J({ error: "forbidden" }, 403);
      if (req.method === "POST") {
        const id = "m" + rid(5); const t = { id, name: clean(b.name, 120), branche: clean(b.branche, 40), lang: ["de", "en", "es", "fr", "zh"].includes(b.lang) ? b.lang : "de",
          countries: (Array.isArray(b.countries) ? b.countries : String(b.countries || "").split(/[ ,;]+/)).map(c => clean(c, 2).toUpperCase()).filter(c => /^[A-Z]{2}$/.test(c)), modules: (b.modules || MODULES).filter(m => MODULES.includes(m)), plan: clean(b.plan, 40), created: Date.now() };
        await KV.put("tenant:" + id, JSON.stringify(t)); await KV.put("tenants:" + id, "1"); await audit("haiktec", S.email, "Mandant angelegt: " + t.name);
        return J(t);
      }
      const r = await KV.list({ prefix: "tenants:" }); return J(await Promise.all(r.keys.map(async k => JSON.parse(await KV.get("tenant:" + k.name.slice(8))))));
    }
    if (path === "/super/lock" && req.method === "POST") { if (!isSuper) return J({ error: "forbidden" }, 403);
      const t = JSON.parse(await KV.get("tenant:" + clean(b.tid, 20)) || "null"); if (!t || t.id === "haiktec") return J({ error: "nicht gefunden" }, 404);
      t.locked = !!b.locked; await KV.put("tenant:" + t.id, JSON.stringify(t)); await audit("haiktec", S.email, `${t.name} ${t.locked ? "gesperrt" : "entsperrt"}`); return J(t); }
    // Einladen: Superadmin in jeden Mandanten, Mandanten-Admin nur in den eigenen
    if (path === "/invite" && req.method === "POST") {
      const tid = isSuper && b.tid ? clean(b.tid, 20) : S.tid;
      if (!isAdmin) return J({ error: "Nur Administratoren dürfen einladen" }, 403);
      const role = ["admin", "user"].includes(b.role) ? b.role : "user";
      const email = clean(b.email, 120).toLowerCase(); if (!/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(email)) return J({ error: "E-Mail ungültig" }, 400);
      if (await KV.get("user:" + email)) return J({ error: "E-Mail ist bereits registriert" }, 409);
      const it = rid(24); await KV.put("invite:" + it, JSON.stringify({ email, tid, role, name: clean(b.name) }), { expirationTtl: 604800 });
      await audit(tid, S.email, `Einladung an ${email} (${role})`); return J({ invite: `https://haiktec.tech/portal/?invite=${it}` });
    }
    if (path === "/audit") { if (!isAdmin) return J({ error: "forbidden" }, 403); return J((await list("audit", 100)).reverse()); }

    // Modul Mahnwesen: offene Rechnungen des eigenen Mandanten
    if (path === "/mahn/invoices") {
      if (!T.modules.includes("mahn")) return J({ error: "Modul nicht gebucht" }, 403);
      if (req.method === "POST") {
        const id = clean(b.id, 20) || rid(6);
        const inv = { id, kunde: clean(b.kunde, 120), nr: clean(b.nr, 40), betrag: Math.max(0, +b.betrag || 0), faellig: clean(b.faellig, 10), status: ["offen", "gemahnt", "bezahlt"].includes(b.status) ? b.status : "offen", b2b: !!b.b2b, updated: Date.now() };
        await KV.put(P + "inv:" + id, JSON.stringify(inv)); await audit(S.tid, S.email, `Rechnung ${inv.nr} gespeichert`); return J(inv);
      }
      if (req.method === "DELETE") { await KV.delete(P + "inv:" + clean(url.searchParams.get("id"), 20)); return J({ ok: true }); }
      return J(await list("inv"));
    }
    if (path === "/mahn/letter" && req.method === "POST") {
      const inv = JSON.parse(await KV.get(P + "inv:" + clean(b.id, 20)) || "null"); if (!inv) return J({ error: "nicht gefunden" }, 404);
      const stufe = ["Zahlungserinnerung", "1. Mahnung", "2. Mahnung"][Math.min(2, Math.max(0, +b.stufe || 0))];
      const txt = await llm(env, "deepseek/deepseek-chat", `Schreibe eine hoefliche, sachliche ${stufe} in der Sprache ${clean(b.lang, 10) || "de"} im Namen von "${T.name}" an "${inv.kunde}" fuer Rechnung ${inv.nr} ueber ${inv.betrag.toFixed(2)} EUR, faellig seit ${inv.faellig}.
Keine Drohungen, keine Rechtsbehauptungen, keine erfundenen Betraege, keine Zinsbetraege nennen. Platzhalter nur fuer Bankverbindung als [IBAN]. Nur den Brieftext.`, 500);
      await audit(S.tid, S.email, `${stufe} erstellt fuer ${inv.nr}`); return J({ text: txt, stufe });
    }

    // Modul AI Visibility / GEO-Check
    if (path === "/geo/run" && req.method === "POST") {
      if (!T.modules.includes("geo")) return J({ error: "Modul nicht gebucht" }, 403);
      const day = new Date().toISOString().slice(0, 10), lk = `${P}geolimit:${day}`, used = +(await KV.get(lk) || 0);
      if (used >= (isSuper ? 20 : 3)) return J({ error: "Tageslimit erreicht (3 Analysen pro Tag)" }, 429);
      const firma = clean(b.firma, 120), ort = clean(b.ort, 80), web = clean(b.website, 120), branche = clean(b.branche, 80), lang = clean(b.lang, 5) || "de";
      if (!firma || !branche) return J({ error: "Firma und Branche angeben" }, 400);
      await KV.put(lk, String(used + 1), { expirationTtl: 172800 });
      const fr = JSON.parse(await llm(env, "deepseek/deepseek-chat", `Erzeuge 5 typische Fragen (Sprache ${lang}), die ein potenzieller Kunde einer KI-Suche stellt, um einen Anbieter der Branche "${branche}" in "${ort || "der Region"}" zu finden. Firmennamen NICHT nennen. JSON: {"q":["..."]}`, 300, true) || '{"q":[]}').q.slice(0, 5);
      const res = [];
      for (const q of fr) {
        const a = await llm(env, "perplexity/sonar", q, 500);
        const hit = [firma, web.replace(/^https?:\/\//, "").replace(/^www\./, "").split("/")[0]].filter(x => x && x.length > 3).some(x => a.toLowerCase().includes(x.toLowerCase()));
        res.push({ frage: q, genannt: hit, antwort: a.slice(0, 1200) });
      }
      const score = Math.round(100 * res.filter(r => r.genannt).length / Math.max(1, res.length));
      const tipps = await llm(env, "deepseek/deepseek-chat", `Firma "${firma}" (${branche}, ${ort}, ${web}) wurde in ${res.filter(r => r.genannt).length} von ${res.length} KI-Antworten genannt. Genannte Wettbewerber stehen in diesen Antworten: ${res.map(r => r.antwort.slice(0, 400)).join(" | ")}.
Gib 6 konkrete, umsetzbare Empfehlungen (Sprache ${lang}), wie die Firma in KI-Suchen sichtbarer wird (z. B. Google-Unternehmensprofil, strukturierte Daten, Bewertungen, Branchenverzeichnisse, FAQ-Seiten, Fachartikel). Keine erfundenen Zahlen. Als kurze Aufzaehlung.`, 600);
      const rep = { id: Date.now().toString(36), t: new Date().toISOString(), firma, ort, web, branche, score, res, tipps };
      await KV.put(P + "geo:" + rep.id, JSON.stringify(rep)); await audit(S.tid, S.email, `GEO-Analyse ${firma}: ${score} %`); return J(rep);
    }
    if (path === "/geo/reports") return J((await list("geo", 50)).reverse());

    // Modul Aufgaben (einfache Mandanten-To-dos, z. B. fuer Steuerbuero/Hausverwaltung/Handwerk)
    if (path === "/aufgaben") {
      if (req.method === "POST") { const a = { id: clean(b.id, 20) || rid(6), titel: clean(b.titel, 200), frist: clean(b.frist, 10), wer: clean(b.wer, 80), erledigt: !!b.erledigt, updated: Date.now() };
        await KV.put(P + "task:" + a.id, JSON.stringify(a)); return J(a); }
      if (req.method === "DELETE") { await KV.delete(P + "task:" + clean(url.searchParams.get("id"), 20)); return J({ ok: true }); }
      return J(await list("task"));
    }
    return J({ error: "404" }, 404);
  }
};

async function llm(env, model, prompt, max = 400, json = false) {
  const r = await fetch("https://openrouter.ai/api/v1/chat/completions", { method: "POST",
    headers: { Authorization: "Bearer " + env.LLM_API_KEY, "content-type": "application/json" },
    body: JSON.stringify({ model, max_tokens: max, messages: [{ role: "user", content: prompt }], ...(json ? { response_format: { type: "json_object" } } : {}) }) });
  const d = await r.json(); let t = d?.choices?.[0]?.message?.content || "";
  if (json) { const m = t.match(/\{[\s\S]*\}/); t = m ? m[0] : "{}"; }
  return t;
}
