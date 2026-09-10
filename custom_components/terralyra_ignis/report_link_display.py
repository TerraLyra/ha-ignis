"""Context-only calendar annotations for explicitly reviewed report links."""

from datetime import datetime
from zoneinfo import ZoneInfo

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

# Display text only: no change to persisted reviews or matching evidence.
DETAILS = {
    "en": ("Related report", "Possible association; not proof of the same fire.", "Separation from the supplied report location", "Satellite observations", "Reviewed"),
    "hu": ("Kapcsolódó hír", "Lehetséges egyezés; nem bizonyítja, hogy ugyanaz a tűz.", "Távolság a hírhez megadott helytől", "Műholdas észlelések", "Ellenőrizve"),
    "de": ("Zugehörige Meldung", "Mögliche Zuordnung; kein Nachweis desselben Brandes.", "Abstand zum angegebenen Meldungsort", "Satellitenbeobachtungen", "Geprüft"),
    "es": ("Noticia relacionada", "Posible asociación; no demuestra que sea el mismo incendio.", "Distancia al lugar indicado de la noticia", "Observaciones por satélite", "Revisado"),
    "fr": ("Communiqué associé", "Association possible ; ne prouve pas qu’il s’agit du même incendie.", "Distance au lieu indiqué du communiqué", "Observations satellitaires", "Vérifié"),
    "it": ("Notizia collegata", "Associazione possibile; non prova che sia lo stesso incendio.", "Distanza dal luogo indicato nella notizia", "Osservazioni satellitari", "Verificato"),
}


def local_time(value, time_zone):
    """Use HA's time zone, including the UTC offset across DST transitions."""
    return datetime.fromisoformat(value).astimezone(ZoneInfo(time_zone)).strftime(
        "%Y-%m-%d %H:%M %Z (UTC%z)"
    )


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
    titles = {notice["url"]: notice.get("title", "") for notice in notices}
    return [
        {**item, "report_title": titles.get(item["review"]["report_url"], "")}
        for item in resolve_links(links, history, notices) if item["status"] == "active"
    ]


def link_lines(link, language, time_zone="UTC"):
    label = LABELS.get(language, LABELS["en"])[0]
    report, explanation, distance, observations, reviewed = DETAILS.get(language, DETAILS["en"])
    candidate = link["review"]["candidate"]
    return [
        f"{report}: {link.get('report_title') or 'BM OKF'}",
        f"BM OKF: {link['review']['report_url']}",
        label,
        explanation,
        f"{distance}: {candidate['distance_km']:.2f} km",
        f"{observations}: {local_time(candidate['first_seen'], time_zone)} – {local_time(candidate['last_seen'], time_zone)}",
        f"{reviewed}: {local_time(link['reviewed_at'], time_zone)}",
    ]
