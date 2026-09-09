"""Filter weather/accident noise while retaining explicitly described fires."""

from copy import deepcopy
from pathlib import Path

import pytest
import yaml

from custom_components.terralyra_ignis.report_relevance import classify_report


@pytest.mark.parametrize("title,description", [
    ("Elsőfokú riasztást adott ki zivatarok kialakulása miatt a HungaroMet", "A tűzoltók készenlétben vannak."),
    ("Karambol történt", "A tűzoltók áramtalanították az autót."),
    ("Szén-monoxid miatt riasztottak", "Tűzoltók érkeztek."),
    ("Tűzveszélyre figyelmeztetnek", "A száraz növényzet könnyen kigyulladhat."),
    ("Tűzoltók gyakorlata", "A gyakorlaton egy szimulált tűzesethez vonultak."),
    ("Téves riasztás", "Nem keletkezett tűz, és nem égett semmi."),
    ("Figyelmeztetés", "Ha kigyulladt egy autó, hívja a segélyhívót."),
    ("Riasztás", "Tűzoltók vonultak a helyszínre."),
])
def test_nonfire_and_ambiguous_not_displayed(title, description):
    assert classify_report({"title": title, "description": description})["category"] != "fire_related"


@pytest.mark.parametrize("title,description", [
    ("Eddig hét hektár égett le Egyeknél", ""),
    ("Kigyulladt a nádas", ""),
    ("Ég a bozótos", ""),
    ("Tűz ütött ki egy raktárban", ""),
    ("Eloltották a tüzet", ""),
    ("Leégett a melléképület", ""),
    ("Felcsaptak a lángok", ""),
    ("Lángra kapott egy autó", ""),
    ("Karambol történt", "Az ütközés után kigyulladt az autó."),
    ("Viharkárok a megyében", "Villámcsapás miatt tűz keletkezett egy pajtában."),
    ("Dolgoznak az egységek", "Oltják a lángokat."),
])
def test_actual_fire_language_retained(title, description):
    assert classify_report({"title": title, "description": description})["category"] == "fire_related"


def test_saved_egyek_import_kept_unchanged():
    path = Path(__file__).parents[1] / "examples/egyek-report-import.yaml"
    record = yaml.safe_load(path.read_text())["data"]
    original = deepcopy(record)
    assert classify_report(record)["category"] == "fire_related"
    assert record == original


def test_unknown_and_negated_body_are_not_evidence():
    assert classify_report({})["category"] == "uncertain"
    assert classify_report({"description": "Nem égett a nádas."})["category"] == "uncertain"
