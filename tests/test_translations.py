"""Validate bundled translations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TRANSLATIONS = Path("custom_components/terralyra_ignis/translations")
SOURCE_STRINGS = Path("custom_components/terralyra_ignis/strings.json")
SUPPORTED_LANGUAGES = {"de", "en", "es", "fr", "hu", "it"}
EXPECTED_ENGLISH_IDENTICAL_PATHS = {
    "hu": {
        "title",
        "options.step.init.data.firms_map_key",
    },
    "de": {
        "title",
        "config.step.sources.data.firms_map_key",
        "options.step.init.data.firms_map_key",
        "entity.sensor.active_fire_situation.state.normal",
    },
    "fr": {
        "title",
        "config.step.monitoring_center.data.monitoring_latitude",
        "config.step.monitoring_center.data.monitoring_longitude",
        "options.step.init.data.firms_map_key",
    },
    "es": {
        "title",
        "options.step.init.data.firms_map_key",
        "entity.sensor.active_fire_situation.state.normal",
    },
    "it": {
        "title",
        "config.step.lsa_saf.data.password",
        "config.step.reauth_confirm.data.password",
        "options.step.init.data.firms_map_key",
    },
}
LOCATION_ENTITY_PREFIXES = {
    "de": "Ort: {location_name} — ",
    "en": "Location: {location_name} — ",
    "es": "Ubicación: {location_name} — ",
    "fr": "Lieu : {location_name} — ",
    "hu": "Hely: {location_name} — ",
    "it": "Località: {location_name} — ",
}
LOCATION_ENTITY_KEYS = {
    "monitored_location_sources",
    "monitored_location_status",
    "monitored_location_next_update",
}
LOCATION_PLATFORM_ENTITIES = {
    "geo_location": {"monitoring_area"},
    "sensor": LOCATION_ENTITY_KEYS,
}
HOME_ENTITY_PREFIXES = {
    "de": "Ort: Zuhause — ",
    "en": "Location: Home — ",
    "es": "Ubicación: Casa — ",
    "fr": "Lieu : Domicile — ",
    "hu": "Hely: Otthon — ",
    "it": "Località: Casa — ",
}
OVERVIEW_PREFIXES = {
    "de": "Übersicht — ",
    "en": "Overview — ",
    "es": "Resumen — ",
    "fr": "Vue d’ensemble — ",
    "hu": "Áttekintés — ",
    "it": "Panoramica — ",
}
SOURCE_PREFIXES = {
    "de": "Quellen — ",
    "en": "Sources — ",
    "es": "Fuentes — ",
    "fr": "Sources — ",
    "hu": "Források — ",
    "it": "Fonti — ",
}
HOME_ENTITIES = {
    "sensor": {
        "fire_risk_today",
        "fire_risk_area_maximum",
        "fire_risk_update",
        "land_surface_temperature",
    },
    "event": {"fire_risk_increase"},
    "select": {"fire_risk_day"},
    "camera": {"fire_risk_map"},
    "calendar": {"fire_risk_forecast"},
    "number": {"fire_risk_radius"},
}
OVERVIEW_ENTITIES = {
    "sensor": {
        "nearest_fire",
        "active_fire_count",
        "recent_detections",
        "fire_activity_frp_change",
        "new_incidents_24h",
        "active_fire_situation",
        "nearest_fire_evidence",
    },
    "event": {"new_fire", "fire_trend"},
    "calendar": {"fire_incident_history"},
    "number": {"fire_history_hours"},
}
SOURCE_ENTITIES = {
    "sensor": {
        "supplemental_fire_count",
        "combined_fire_count",
        "raw_pixel_count",
        "product_time",
        "product_age",
        "provider_status",
        "active_fire_provider",
        "provider_coverage",
        "fire_source_confirmation",
    }
}


def _leaf_paths(value: Any, prefix: tuple[str, ...] = ()) -> set[tuple[str, ...]]:
    if not isinstance(value, dict):
        return {prefix}
    return {
        path
        for key, child in value.items()
        for path in _leaf_paths(child, (*prefix, key))
    }


def _leaf_values(
    value: Any, prefix: tuple[str, ...] = ()
) -> dict[tuple[str, ...], Any]:
    if not isinstance(value, dict):
        return {prefix: value}
    return {
        path: leaf
        for key, child in value.items()
        for path, leaf in _leaf_values(child, (*prefix, key)).items()
    }


def test_all_supported_translations_match_english_schema() -> None:
    english = json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))
    expected_paths = _leaf_paths(english)

    assert {path.stem for path in TRANSLATIONS.glob("*.json")} == SUPPORTED_LANGUAGES
    for language in SUPPORTED_LANGUAGES - {"en"}:
        translation = json.loads(
            (TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8")
        )
        assert _leaf_paths(translation) == expected_paths

    source = json.loads(SOURCE_STRINGS.read_text(encoding="utf-8"))
    assert _leaf_paths(source) == expected_paths


def test_translation_values_are_non_empty_strings() -> None:
    for path in TRANSLATIONS.glob("*.json"):
        translation = json.loads(path.read_text(encoding="utf-8"))
        for leaf_path in _leaf_paths(translation):
            value: Any = translation
            for key in leaf_path:
                value = value[key]
            assert isinstance(value, str) and value.strip(), (path.name, leaf_path)


def test_location_entities_share_a_localized_sorting_prefix() -> None:
    """Keep all per-location entities grouped on alphabetical entity lists."""
    for language, prefix in LOCATION_ENTITY_PREFIXES.items():
        translation = json.loads(
            (TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8")
        )
        for platform, keys in LOCATION_PLATFORM_ENTITIES.items():
            entities = translation["entity"][platform]
            for key in keys:
                assert entities[key]["name"].startswith(prefix), (language, key)

    source = json.loads(SOURCE_STRINGS.read_text(encoding="utf-8"))
    for platform, keys in LOCATION_PLATFORM_ENTITIES.items():
        entities = source["entity"][platform]
        for key in keys:
            assert entities[key]["name"].startswith(
                LOCATION_ENTITY_PREFIXES["en"]
            )


def test_entity_names_expose_their_scope_before_the_metric() -> None:
    """Home, overview and source entities remain visibly grouped by scope."""
    groups = (
        (HOME_ENTITIES, HOME_ENTITY_PREFIXES),
        (OVERVIEW_ENTITIES, OVERVIEW_PREFIXES),
        (SOURCE_ENTITIES, SOURCE_PREFIXES),
    )
    for language in SUPPORTED_LANGUAGES:
        translation = json.loads(
            (TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8")
        )
        for entities, prefixes in groups:
            for platform, keys in entities.items():
                for key in keys:
                    assert translation["entity"][platform][key]["name"].startswith(
                        prefixes[language]
                    ), (language, platform, key)

    source = json.loads(SOURCE_STRINGS.read_text(encoding="utf-8"))
    for entities, prefixes in groups:
        for platform, keys in entities.items():
            for key in keys:
                assert source["entity"][platform][key]["name"].startswith(
                    prefixes["en"]
                ), (platform, key)


def test_primary_location_radius_uses_the_location_sorting_prefix() -> None:
    """The editable primary radius follows its actual managed-location name."""
    for language, prefix in LOCATION_ENTITY_PREFIXES.items():
        translation = json.loads(
            (TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8")
        )
        assert translation["entity"]["number"]["monitoring_radius"]["name"].startswith(
            prefix
        )


def test_localizations_do_not_accidentally_fall_back_to_english() -> None:
    english = _leaf_values(
        json.loads((TRANSLATIONS / "en.json").read_text(encoding="utf-8"))
    )
    for language, allowed in EXPECTED_ENGLISH_IDENTICAL_PATHS.items():
        localized = _leaf_values(
            json.loads((TRANSLATIONS / f"{language}.json").read_text(encoding="utf-8"))
        )
        identical = {
            ".".join(path)
            for path, value in localized.items()
            if value == english[path]
        }
        assert identical == allowed
