"""Context-only calendar annotations for explicitly reviewed report links."""

from .const import DOMAIN
from .report_links import resolve_links

LABELS = {
    "en": ("Manually reviewed link — not official confirmation", "Not matched to satellite detections."),
    "hu": ("Kézzel jóváhagyott kapcsolat — nem hivatalos megerősítés", "Nincs műholdas észleléshez párosítva."),
    "de": ("Manuell geprüfte Zuordnung — keine amtliche Bestätigung", "Keine Zuordnung zu Satellitenerkennungen."),
    "es": ("Vínculo revisado manualmente — no es confirmación oficial", "Sin vinculación a detecciones por satélite."),
    "fr": ("Association vérifiée manuellement — pas une confirmation officielle", "Aucune association aux détections satellitaires."),
    "it": ("Collegamento verificato manualmente — non è una conferma ufficiale", "Nessuna associazione ai rilevamenti satellitari."),
}


async def active_links(hass, entry_id, history, notices=None):
    """Read local stores only; calendar annotations never poll another source."""
    domain_data = hass.data.get(DOMAIN, {})
    store = domain_data.get("official_report_links")
    if store is None:
        return []
    links = await store.async_list(entry_id)
    if not links:
        return []
    if notices is None:
        client = domain_data.get("official_report_client")
        notices = await client.archive.async_merge() if client is not None and client.archive is not None else []
    return [item for item in resolve_links(links, history, notices) if item["status"] == "active"]


def link_lines(link, language):
    label = LABELS.get(language, LABELS["en"])[0]
    candidate = link["review"]["candidate"]
    return [
        label,
        f"BM OKF: {link['review']['report_url']}",
        f"Incident: {candidate['incident_id']} ({candidate['first_seen']} – {candidate['last_seen']})",
        f"Review: {candidate['relation']} / {candidate['distance_km']} km",
        f"Reviewed at: {link['reviewed_at']}",
        f"Link ID: {link['link_id']}",
    ]
