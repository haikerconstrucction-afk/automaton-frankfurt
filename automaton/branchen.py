"""Eigene Bereichsseiten je Branche/Angebot (getrennte Auftritte, gemeinsamer sicherer Kundenbereich)."""
import pathlib, html
ROOT = pathlib.Path(__file__).resolve().parent.parent
MAIL = "Haiktec@outlook.de"
PAGES = {
 "ki-sichtbarkeit": ("KI-Sichtbarkeit", "Wird Ihre Firma von ChatGPT, Perplexity und Gemini empfohlen?",
   "Immer mehr Kunden fragen eine KI statt Google. Wir prüfen, ob Ihr Unternehmen in diesen Antworten vorkommt, zeigen, wer stattdessen genannt wird, und setzen die Verbesserungen für Sie um.",
   [("Analyse", "Wir stellen KI-Suchmaschinen die Fragen, die Ihre Kunden stellen, und dokumentieren jede Antwort."), ("Bericht", "Sichtbarkeitswert, genannte Wettbewerber und konkrete Maßnahmen, verständlich erklärt."), ("Umsetzung", "Auf Wunsch optimieren wir Website, Unternehmensprofile, FAQ und Inhalte."), ("Kundenbereich", "Alle Berichte liegen geschützt in Ihrem eigenen Portal-Zugang.")],
   [("Sichtbarkeits-Check", "500 €", "Einmalige Analyse mit Bericht und Maßnahmenplan"), ("Umsetzung und Betreuung", "75 € pro Stunde", "Abrechnung im 15-Minuten-Takt (18,75 € je Viertelstunde), jede Tätigkeit protokolliert")]),
 "steuerbuero": ("Für Steuerbüros", "Mehr Mandanten über KI-Suchen. Weniger Aufwand beim Forderungsmanagement.",
   "Ein Portal für Ihre Kanzlei: KI-Sichtbarkeit, Überblick über offene Honorarrechnungen mit Mahnvorlagen in Ihrem Namen, Aufgaben und Fristen im Team.",
   [("Sichtbarkeit", "Werden Sie gefunden, wenn jemand nach einem Steuerberater in Ihrer Stadt fragt?"), ("Offene Posten", "Honorarrechnungen erfassen, überfällige erkennen, freundliche Erinnerungen erstellen."), ("Team", "Eigene Zugänge für Mitarbeitende, jeder sieht nur Ihre Kanzleidaten."), ("Sicherheit", "Zwei-Faktor-Anmeldung, Länder-Freigabe, Protokoll jeder Aktion.")], None),
 "immobilien": ("Für Immobilien und Hausverwaltungen", "Gefunden werden. Offene Zahlungen im Griff.",
   "Für Makler und Hausverwaltungen: KI-Sichtbarkeit in Ihrer Region, Übersicht über offene Rechnungen mit Erinnerungsschreiben und ein gemeinsamer Aufgabenplan.",
   [("Sichtbarkeit", "Welche Makler empfiehlt die KI in Ihrem Ort, und wie kommen Sie dazu?"), ("Offene Posten", "Rechnungen und Fälligkeiten übersichtlich, Schreiben in Ihrem Namen."), ("Aufgaben", "Fristen und Zuständigkeiten für das ganze Team."), ("Sicherheit", "Getrennte Mandantenbereiche, Zwei-Faktor-Anmeldung, Protokoll.")], None),
 "handwerk": ("Für Handwerksbetriebe", "Mehr Aufträge, weniger Papierkram.",
   "Für Handwerker: Werden Sie gefunden, wenn jemand die KI nach einem Betrieb in der Nähe fragt? Dazu offene Rechnungen im Blick und professionelle Excel-Vorlagen für Angebote und Baustellen.",
   [("Sichtbarkeit", "Prüfen, ob Ihr Betrieb bei KI-Anfragen in Ihrer Region genannt wird."), ("Offene Rechnungen", "Überfällige Rechnungen erkennen und freundlich erinnern."), ("Vorlagen", "Kalkulation, Aufmaß und Baustellenkosten als Profi-Excel im Shop."), ("Sicherheit", "Eigener Zugang je Betrieb, niemand sieht fremde Daten.")], None),
}
def build(head, foot):
    for slug, (title, h1, lead, feats, prices) in PAGES.items():
        cards = "".join(f'<div class="card" style="padding:18px"><h3>{html.escape(a)}</h3><p>{html.escape(b)}</p></div>' for a, b in feats)
        pr = "" if not prices else '<section class="wrap"><h2>Preise</h2><div class="grid">' + "".join(
            f'<div class="card" style="padding:18px"><h3>{html.escape(a)}</h3><p style="font-size:1.4rem;font-weight:700;color:#0b6e4f">{html.escape(b)}</p><p>{html.escape(c)}</p></div>' for a, b, c in prices) + '</div><p class="legal">Alle Preise sind Endpreise. Gemäß § 19 UStG wird keine Umsatzsteuer berechnet. Leistungen ausschließlich für Unternehmer.</p></section>'
        other = " · ".join(f'<a href="../{s}/">{html.escape(t[0])}</a>' for s, t in PAGES.items() if s != slug)
        body = f"""<section class="hero"><div class="wrap"><p class="eyebrow">Haiktec · {html.escape(title)}</p><h1>{html.escape(h1)}</h1><p class="lead">{html.escape(lead)}</p>
<a class="btn" href="mailto:{MAIL}?subject={html.escape(title)}%20-%20Anfrage">Unverbindlich anfragen</a> <a class="btn" style="background:#fff;color:#0b6e4f;border:1px solid #0b6e4f" href="../portal/">Kunden-Login</a></div></section>
<section class="wrap"><div class="grid">{cards}</div></section>{pr}
<section class="wrap"><h2>Sicherheit und Datenschutz</h2><p>Jedes Unternehmen erhält einen eigenen, abgeschotteten Bereich. Zugang nur auf Einladung, Zwei-Faktor-Anmeldung für Administratoren, Zugriff auf freigegebene Länder beschränkbar, jede Aktion wird protokolliert. Auftragsverarbeitung nach Art. 28 DSGVO auf Anfrage. KI-Ergebnisse werden als solche gekennzeichnet und ersetzen keine Rechts- oder Steuerberatung.</p><p class="legal">Weitere Bereiche: {other}</p></section>"""
        d = ROOT/"site"/slug; d.mkdir(parents=True, exist_ok=True)
        (d/"index.html").write_text(head.format(lang="de", title=f"{title} – Haiktec", desc=h1[:155], r="../") + body + foot.format(r="../") + "</body></html>")
