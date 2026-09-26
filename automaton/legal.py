"""Erzeugt Impressum, AGB, Widerruf, Datenschutz und Versand aus impressum.json (DE/EU-Recht, global verkaufbar).
Hinweis: Mustertexte, ersetzen keine Rechtsberatung. Vor Start anwaltlich/per Rechtstexte-Dienst pruefen lassen."""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent

def wrap(title, body):
    return f"""<!doctype html><html lang="de"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>{title}</title><link rel="stylesheet" href="style.css"><main><a href="./">← Shop</a><h1>{title}</h1>{body}</main></html>"""

def build():
    f = ROOT/"impressum.json"
    if not f.exists(): return False
    i = json.loads(f.read_text()); site = ROOT/"site"
    if not i.get("email"): return False  # E-Mail ist Pflichtangabe - ohne sie kein Verkauf
    adr = f"{i['firma']}<br>{i['strasse']}<br>{i['plz_ort']}<br>{i['land']}"
    reg = f"<p>Registereintrag: {i['handelsregister']}</p>" if i.get("handelsregister") else ""
    ust = f"<p>Umsatzsteuer-ID gemäß § 27a UStG: {i['ust_id']}</p>" if i.get("ust_id") else ""
    extra = ""
    if i.get("lucid_nr"): extra += f"<p>Verpackungsregister LUCID: {i['lucid_nr']}</p>"
    if i.get("eori"): extra += f"<p>EORI: {i['eori']}</p>"
    pages = {}
    pages["impressum"] = ("Impressum", f"""<h2>Angaben gemäß § 5 DDG</h2><p>{adr}</p><p>Inhaber: {i['inhaber_oder_gf']}</p>
<h2>Kontakt</h2><p>E-Mail: {i['email']}{('<br>Telefon: ' + i['telefon']) if i.get('telefon') else ''}</p>{reg}{ust}{extra}
<h2>Verbraucherstreitbeilegung</h2><p>Wir sind nicht bereit und nicht verpflichtet, an Streitbeilegungsverfahren vor einer Verbraucherschlichtungsstelle teilzunehmen.</p>
<h2>KI-Hinweis</h2><p>Produkte und Texte dieses Shops werden mit Unterstützung künstlicher Intelligenz erstellt und vor Veröffentlichung automatisiert geprüft (Art. 50 KI-Verordnung).</p>
<h2>Legal notice (English)</h2><p>Operator: {i['firma']}, {i['strasse']}, {i['plz_ort']}, {i['land']}. Contact: {i['email']}. Content is created with the help of AI.</p>""")
    phys = i.get("physische_waren")
    pages["agb"] = ("Allgemeine Geschäftsbedingungen", f"""<h2>§ 1 Geltung</h2><p>Diese AGB gelten für alle Verträge zwischen {i['firma']} (nachfolgend „Anbieter“) und Kunden über den Shop {i['shopname']}. Vertragssprache ist Deutsch; englische Übersetzungen dienen der Information.</p>
<h2>§ 2 Vertragsschluss</h2><p>Die Produktdarstellung ist kein bindendes Angebot. Mit Abschluss des Bezahlvorgangs über Stripe gibt der Kunde ein verbindliches Angebot ab, das der Anbieter durch Bereitstellung des Downloads{' bzw. Versand der Ware' if phys else ''} annimmt.</p>
<h2>§ 3 Preise und Zahlung</h2><p>{'Alle Preise sind Endpreise. Gemäß § 19 UStG wird keine Umsatzsteuer berechnet.' if i.get('kleinunternehmer') else 'Alle Preise sind Endpreise inkl. gesetzlicher Umsatzsteuer. Bei Verkäufen an Verbraucher in anderen EU-Staaten wird die Umsatzsteuer des Bestimmungslandes berechnet (OSS).'}{' Zzgl. ausgewiesener Versandkosten.' if phys else ''} Die Zahlung erfolgt über Stripe.</p>
<h2>§ 4 Digitale Inhalte</h2><p>Digitale Produkte (Excel-Vorlagen, E-Books u. a.) werden unmittelbar nach Zahlungseingang zum Download bereitgestellt. Der Kunde erhält ein einfaches, nicht übertragbares Nutzungsrecht für eigene Zwecke; Weiterverkauf und Weitergabe sind untersagt.</p>
{'<h2>§ 5 Lieferung physischer Waren</h2><p>Lieferbedingungen, Lieferzeiten und Versandkosten ergeben sich aus der Seite <a href="versand.html">Versand</a>. Die Gefahr geht bei Verbrauchern erst mit Übergabe über.</p>' if phys else ''}
<h2>§ 6 Gewährleistung</h2><p>Es gelten die gesetzlichen Mängelrechte, für digitale Produkte einschließlich §§ 327 ff. BGB.</p>
<h2>§ 7 Haftung</h2><p>Der Anbieter haftet unbeschränkt bei Vorsatz, grober Fahrlässigkeit sowie bei Verletzung von Leben, Körper oder Gesundheit. Im Übrigen ist die Haftung auf vertragstypische, vorhersehbare Schäden begrenzt. Die Produkte stellen keine Rechts-, Steuer- oder Finanzberatung dar.</p>
<h2>§ 8 Schlussbestimmungen</h2><p>Es gilt deutsches Recht unter Ausschluss des UN-Kaufrechts. Gegenüber Verbrauchern gilt diese Rechtswahl nur, soweit nicht zwingende Verbraucherschutzvorschriften des Aufenthaltsstaates entgegenstehen.</p>""")
    pages["widerruf"] = ("Widerrufsbelehrung", f"""<h2>Widerrufsrecht</h2><p>Verbraucher haben das Recht, binnen vierzehn Tagen ohne Angabe von Gründen diesen Vertrag zu widerrufen. Die Frist beträgt vierzehn Tage ab dem Tag des Vertragsschlusses{' bzw. bei Waren ab Erhalt der Ware' if phys else ''}. Um Ihr Widerrufsrecht auszuüben, informieren Sie uns ({i['firma']}, {i['strasse']}, {i['plz_ort']}, E-Mail: {i['email']}) mittels einer eindeutigen Erklärung.</p>
<h2>Folgen des Widerrufs</h2><p>Wir erstatten alle Zahlungen{', einschließlich der Standard-Lieferkosten,' if phys else ''} unverzüglich, spätestens binnen vierzehn Tagen, über dasselbe Zahlungsmittel.{' Sie tragen die unmittelbaren Kosten der Rücksendung.' if phys else ''}</p>
<h2>Vorzeitiges Erlöschen bei digitalen Inhalten</h2><p>Das Widerrufsrecht erlischt bei digitalen Inhalten, wenn wir mit der Vertragserfüllung begonnen haben, nachdem Sie ausdrücklich zugestimmt haben, dass wir vor Ablauf der Widerrufsfrist beginnen, und Sie Ihre Kenntnis davon bestätigt haben, dass Sie dadurch Ihr Widerrufsrecht verlieren (§ 356 Abs. 5 BGB).</p>
{'<p>Kein Widerrufsrecht besteht bei Lebensmitteln, die schnell verderben oder deren Versiegelung nach Lieferung entfernt wurde.</p>' if i.get('lebensmittel') else ''}
<h2>Muster-Widerrufsformular</h2><p>An {i['firma']}, {i['strasse']}, {i['plz_ort']}, {i['email']}:<br>Hiermit widerrufe(n) ich/wir den von mir/uns abgeschlossenen Vertrag über den Kauf der folgenden Waren/digitalen Inhalte: ___ / Bestellt am: ___ / Name, Anschrift: ___ / Datum, Unterschrift (nur bei Papier)</p>""")
    pages["datenschutz"] = ("Datenschutzerklärung", f"""<h2>Verantwortlicher</h2><p>{adr}<br>E-Mail: {i['email']}</p>
<h2>Hosting</h2><p>Diese Website wird bei GitHub Pages (GitHub Inc., USA) gehostet. Beim Aufruf werden technisch notwendige Daten (IP-Adresse, Zeitpunkt, Browser) verarbeitet (Art. 6 Abs. 1 lit. f DSGVO). GitHub ist unter dem EU-US Data Privacy Framework zertifiziert.</p>
<h2>Zahlung</h2><p>Zahlungen werden über Stripe Payments Europe Ltd., Irland, abgewickelt. Dabei verarbeitet Stripe Ihre Zahlungs- und Kontaktdaten zur Vertragserfüllung (Art. 6 Abs. 1 lit. b DSGVO). Datenschutzhinweise: stripe.com/de/privacy.</p>
<h2>Keine Tracking-Cookies</h2><p>Wir setzen keine Analyse- oder Werbe-Cookies ein.</p>
<h2>Ihre Rechte</h2><p>Sie haben das Recht auf Auskunft, Berichtigung, Löschung, Einschränkung, Datenübertragbarkeit und Widerspruch sowie auf Beschwerde bei einer Aufsichtsbehörde, z. B. dem Hessischen Beauftragten für Datenschutz und Informationsfreiheit.</p>
<h2>Speicherdauer</h2><p>Bestelldaten werden gemäß handels- und steuerrechtlichen Aufbewahrungspflichten (bis zu 10 Jahre) gespeichert.</p>""")
    if phys:
        pages["versand"] = ("Versand und Lieferung", """<p>Lieferung in folgende Länder: EU, Schweiz, Vereinigtes Königreich. Versandkosten und Lieferzeiten werden beim jeweiligen Produkt angegeben.
Bei Lieferungen außerhalb der EU können Zölle und Einfuhrsteuern anfallen, die der Kunde trägt.</p>""")
    for k, (t, b) in pages.items(): (site/f"{k}.html").write_text(wrap(t, b))
    return True
