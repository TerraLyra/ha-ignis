# Understanding an empty location map

Open the location's active-fire observation entity details. Its `source_health`
attribute lists only sources assigned to that location, including provider name,
satellite, status, stable reason code, failure type, consecutive failures,
retry time and the last successful product/receipt timestamps.

| Reason | Meaning |
| --- | --- |
| `source_data_available` | The source reports available data; not proof of clear skies or complete pixel coverage. |
| `source_data_delayed` | The source reports delayed data. |
| `source_product_not_available` | No usable product is currently available from this source. |
| `source_fetch_failed` | Retrieval failed; inspect failure type and retry time. |
| `source_authentication_failed` | Source authentication failed. |
| `awaiting_first_source_result` | No result is available yet. |

`last_product_at` and `last_received_at` are the latest successful timestamps
among the location's assigned sources, not the entire installation. A healthy
Home-only source cannot make Tokyo or California look recently updated.
An outage may retain the last successful timestamps; inspect source status too.
A provider shared by locations may publish one shared product timestamp: it is
not a local satellite overpass time or a local pixel acquisition guarantee.

Fresh source counts and active incident counts remain separate. An empty map
does not prove there is no fire, and an existing marker does not prove all
sources are currently healthy. Weather/cloud obstruction cannot be diagnosed
from these health fields; do not display it as the cause without additional
evidence. No extra network requests are introduced by these attributes.

Existing entity IDs and enum states remain unchanged. No Recorder cleanup or
dashboard migration is required. These details are also suitable inputs for a
future location summary card; this change does not install a custom card.
