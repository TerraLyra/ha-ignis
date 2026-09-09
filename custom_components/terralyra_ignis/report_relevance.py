"""Conservative Hungarian publication relevance, not incident verification."""

import re
import unicodedata

# Explicit incident language, not the substring 'tuz' (e.g. tuzoltok/tuzveszely).
FIRE_SIGNAL = re.compile(
    r"\b(?:kigyulladt|meggyulladt|leegett|kiegett|langolt|langol|langokban|eg|egnek|egett|egtek|egni|"
    r"eloltottak|eloltotta|oltjak|oltottak|tuzeset(?:hez|nel|ben|rol|et|ek)?|"
    r"erdotuz(?:et|nel|hoz|ben)?|avartuz(?:et|nel|hoz|ben)?|"
    r"langra\s+(?:kapott|lobbant)|felcsaptak\s+a\s+langok|felszitotta\s+a\s+langokat|"
    r"tuz\s+(?:keletkezett|utott\s+ki|pusztitott|van|volt)|"
    r"tuzet\s+(?:oltanak|oltottak)|megfekeztek\s+a\s+tuzet)\b"
)
UNCERTAIN_SENTENCE = re.compile(
    r"\b(?:nem|sem|teves|gyakorlat|gyakorlaton|szimulalt|"
    r"ha|esetleg|lehet|lehetett|okozhat|keletkezhet|kigyulladhat)\b"
)
NON_FIRE_TOPIC = re.compile(
    r"\b(?:hungaromet|zivatar\w*|idojaras\w*|karambol\w*|"
    r"baleset\w*|utkoz\w*|szendioxid|szenmonoxid|viharkar\w*)\b"
)


def _normalize(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text.casefold())
                   if not unicodedata.combining(c))


def classify_report(notice: dict) -> dict[str, str]:
    """Classify bounded title/body independently, preserving unknowns in archive.

    No network, coordinates, AI model, or writes. A positive classification is
    only permission to display a publication, never stronger fire evidence.
    """
    title = _normalize(str(notice.get("title", ""))[:500])
    description = _normalize(str(notice.get("description", ""))[:4000])
    for field, text in (("title", title), ("description", description)):
        for sentence in re.split(r"[.!?;\n]+", text):
            signal = FIRE_SIGNAL.search(sentence)
            if signal and not UNCERTAIN_SENTENCE.search(sentence):
                return {"category": "fire_related", "reason": f"explicit_fire_language_in_{field}"}
    if NON_FIRE_TOPIC.search(title):
        return {"category": "other", "reason": "other_topic_without_explicit_fire"}
    return {"category": "uncertain", "reason": "no_unambiguous_fire_language"}
