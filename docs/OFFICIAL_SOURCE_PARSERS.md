# Offline official-report model and parsers

Local implementation based on v0.25.0. The parser now feeds an optional QFD calendar;
see `QFD_CALENDAR.md`. No source has been activated in a live HA instance.

## Implemented

- `official_sources/models.py`: frozen source report, record kind and geometry role;
  separate event/publication/expiry/receipt timestamps; source date/raw time fallback;
  explicit source-expiry check returning unknown when expiry is absent.
- `official_sources/nsw.py`: pure conversion of existing accepted NSW dictionaries.
  Does not mutate input or infer UTC from the publisher's local date. The existing
  NSW client/calendar continues using its original dictionaries; IDs are preserved.
- `official_sources/queensland.py`: standalone mixed-feed parser, no HTTP client or
  HA entity. Allowlisted fire types and warning classes; Point incident information
  and Polygon warning area are kept distinct. Planned burns remain explicit context.

Upstream records are parsed at bounded byte, feature, text and polygon-vertex limits.
Coordinates, offset-aware timestamps, rings and duplicate JSON keys are checked.
All-invalid documents fail; empty valid documents and filtered records remain distinct.
Unknown classifications are omitted with a counter, not translated into safe/no warning.
Repeated identical records coalesce. For a source ID, the newest event revision wins;
conflicting records at that same revision omit the identity with a conflict counter.
Publication time alone does not supersede an event revision or reactivate expired data.

The internal dataclasses are trusted typed containers; adapters validate upstream input.
Geometry tuples contain no mutable lists. Polygon checks establish structural validity,
not topology (e.g. self-intersection/hole placement) or location relevance. No polygon
intersection, warning-to-incident association or centroid-based matching is implemented.
A future spatial consumer must add topology validation before using warning areas.

This parser layer introduces no warning severity enum, satellite detection, alarm
suppression or archive. Transport and the optional calendar are separate modules.
`expired_at=False` means only that explicit expiry is in the future; it does not certify
freshness or current danger. `expired_at=None` means expiry is unknown. Future consumers
must assess source health, record time and expiry separately and disclose omissions.

## Verification — 2026-09-14

822 tests passed locally, including 31 new cases; config-flow coverage 100%.
Two existing local NumPy/h5py reload warnings remain. Python compilation, JSON and
whitespace checks passed. HACS/Hassfest and HA deployment remain pending.

A bounded no-redirect read of the official QFD endpoint at 19:31 UTC parsed 37 records:
33 incident points and 4 warning areas, including 5 permitted burns and 29 records
whose explicit source expiry was already past. No invalid or conflicting records.
These are one-time sample counts; accepted is NOT an active-fire count. The many past
expiry values require explicit handling/validation before a live calendar is enabled.
See `QUEENSLAND_PARSER_CHECK_2026_09_14.json`. Only summary metadata was retained.

## Next package

Verify QFD expiry and update semantics against official documentation; add dedicated
fetch/cache/health behavior and a conservative display policy. Add point filtering for
incident records separately from validated polygon relevance for warning records.
Keep the new source opt-in. Live deployment and release remain separate steps.
