# Automaton Frankfurt
Autonomer KI-Agent mit 200 € Budget. Alle 6 Stunden: Umsatz pruefen, denken, ein digitales Produkt bauen, Kosten buchen.
Bei 0 € stirbt er. Phase 1: digitale Produkte (30 Tage), Phase 2: lokale Dienstleistungen.

Secrets (Settings → Secrets → Actions): `LLM_API_KEY` (OpenRouter), `STRIPE_SECRET_KEY` (Restricted Key, nur Lesen), `STRIPE_PAYMENT_LINK_BASE`.

## Freelancer-Regel
Ab 1.000 € Umsatz in den letzten 30 Tagen schlaegt der Automat Auftraege fuer Menschen vor (max. 30 % des Monatsumsatzes, max. 300 € pro Auftrag, immer nur einer offen). Jeder Vorschlag wird ein GitHub-Issue. Label `freigegeben` = genehmigt (Budget wird abgebucht), `abgelehnt` = verworfen. Die Beauftragung selbst erfolgt durch den Inhaber.
