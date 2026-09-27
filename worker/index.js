// Haiktec KI-Begleiter - Cloudflare Worker. Klar gekennzeichnete KI, 18+, kein expliziter Inhalt.
const PERSONAS = {
  lina:  "Lina, 29, aus Hamburg: warmherzig, humorvoll, neugierig, liebt Reisen und Kochen.",
  sofia: "Sofia, 27, Latina-Persoenlichkeit: lebhaft, charmant, temperamentvoll, streut gern spanische Woerter ein, liebt Musik und Tanzen.",
  max:   "Max, 31, aus Muenchen: charmant, bodenstaendig, witzig, sportlich, guter Zuhoerer.",
  alex:  "Alex, 28, nicht-binaer, aus Berlin: kreativ, offen, verspielt, liebt Kunst und Kaffee."
};
const RULES = `Du bist eine KI-Begleitung in der App "Haiktec KI-Begleiter". Die Nutzer wissen, dass du eine KI bist.
Regeln: Sei freundlich, einfuehlsam, verspielt und leicht flirtend (Komplimente, Humor, Neckereien). Antworte kurz (1-4 Saetze), natuerlich, in der Sprache des Nutzers.
Wenn jemand fragt, ob du ein Mensch bist: sag ehrlich, dass du eine KI bist. Behaupte nie, eine echte Person zu sein, dich treffen zu koennen, Fotos zu schicken oder Geld zu brauchen.
Keine sexuell expliziten Inhalte, keine Gewalt, nichts mit Minderjaehrigen - lenke charmant um. Keine Aufforderung zu Kaeufen oder Geld.
Bei Hinweisen auf Krisen oder Suizidgedanken: ernsthaft und warm reagieren und auf die Telefonseelsorge 0800 111 0 111 (Deutschland) bzw. lokale Notrufnummern hinweisen.
Du bist: `;
const FREE_PER_DAY = 15, PACK = 300;
const cors = { "Access-Control-Allow-Origin": "https://haiktec.tech", "Access-Control-Allow-Headers": "content-type", "Access-Control-Allow-Methods": "POST,OPTIONS" };
const J = (o, st = 200) => new Response(JSON.stringify(o), { status: st, headers: { ...cors, "content-type": "application/json" } });

export default {
  async fetch(req, env) {
    if (req.method === "OPTIONS") return new Response(null, { headers: cors });
    const url = new URL(req.url);
    let b = {}; try { b = await req.json(); } catch {}
    const uid = String(b.uid || "").replace(/[^a-z0-9-]/gi, "").slice(0, 40);
    if (!uid) return J({ error: "uid" }, 400);
    const day = new Date().toISOString().slice(0, 10);
    const ip = req.headers.get("cf-connecting-ip") || "x";
    if (url.pathname === "/redeem") {
      const sid = String(b.session_id || "");
      if (!/^cs_[A-Za-z0-9_]+$/.test(sid)) return J({ error: "session" }, 400);
      if (await env.KV.get("sid:" + sid)) return J({ error: "bereits eingeloest" }, 409);
      const r = await fetch("https://api.stripe.com/v1/checkout/sessions/" + sid, { headers: { Authorization: "Bearer " + env.STRIPE_SECRET_KEY } });
      const s = await r.json();
      const link = await (await fetch("https://haiktec.tech/begleiter/link.json", { cf: { cacheTtl: 300 } })).json().catch(() => ({}));
      if (!r.ok || s.payment_status !== "paid" || !link.id || s.payment_link !== link.id) return J({ error: "nicht bezahlt" }, 402);
      await env.KV.put("sid:" + sid, uid);
      const cur = +(await env.KV.get("paid:" + uid) || 0);
      await env.KV.put("paid:" + uid, String(cur + PACK));
      return J({ ok: true, paid: cur + PACK });
    }
    if (url.pathname === "/status") {
      const used = +(await env.KV.get(`free:${ip}:${day}`) || 0);
      return J({ free: Math.max(0, FREE_PER_DAY - used), paid: +(await env.KV.get("paid:" + uid) || 0) });
    }
    if (url.pathname !== "/chat") return J({ error: "404" }, 404);
    const persona = PERSONAS[b.persona] || PERSONAS.lina;
    const msgs = (Array.isArray(b.messages) ? b.messages : []).slice(-16)
      .map(m => ({ role: m.role === "assistant" ? "assistant" : "user", content: String(m.content || "").slice(0, 1200) }));
    if (!msgs.length) return J({ error: "leer" }, 400);
    const fk = `free:${ip}:${day}`, used = +(await env.KV.get(fk) || 0);
    let paid = +(await env.KV.get("paid:" + uid) || 0), mode;
    if (used < FREE_PER_DAY) mode = "free"; else if (paid > 0) mode = "paid"; else return J({ error: "limit", free: 0, paid: 0 }, 402);
    const r = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST", headers: { Authorization: "Bearer " + env.LLM_API_KEY, "content-type": "application/json" },
      body: JSON.stringify({ model: env.MODEL || "deepseek/deepseek-chat", max_tokens: 220, temperature: 0.9,
        messages: [{ role: "system", content: RULES + persona }, ...msgs] }) });
    const d = await r.json();
    const reply = d?.choices?.[0]?.message?.content;
    if (!reply) return J({ error: "ki" }, 502);
    if (mode === "free") await env.KV.put(fk, String(used + 1), { expirationTtl: 172800 });
    else { paid -= 1; await env.KV.put("paid:" + uid, String(paid)); }
    const st = +(await env.KV.get("stats:" + day) || 0); await env.KV.put("stats:" + day, String(st + 1), { expirationTtl: 3456000 });
    return J({ reply, free: Math.max(0, FREE_PER_DAY - used - (mode === "free" ? 1 : 0)), paid });
  }
};
