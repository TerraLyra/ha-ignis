# Migrating from TerraLyra to TerraLyra IGNIS

Release 0.14.0 intentionally changes the Home Assistant integration domain
from `terralyra` to `terralyra_ignis` and moves the project from
`TerraLyra/ha-terralyra` to `TerraLyra/ha-ignis`.

Home Assistant cannot safely transfer config entries or entity-registry records
between custom-integration domains. A clean reinstall is therefore required.
This avoids duplicate polling, duplicate notifications and a permanent legacy
namespace inside the new product.

## Before removing the old integration

1. Record the monitored-location names, coordinates and radii.
2. Record which optional sources and products are enabled.
3. Make sure the LSA SAF credentials and optional NASA FIRMS MAP_KEY are
   available. Diagnostics never reveal stored secrets.
4. Note any customized entity IDs, dashboard cards, automations and scripts
   that refer to `terralyra` or the older `lsa_saf` development domain.

## Clean migration

1. Remove the old **TerraLyra** integration from Home Assistant.
2. In HACS, remove the old custom repository entry if it still points to
   `TerraLyra/ha-terralyra`.
3. Add `TerraLyra/ha-ignis` as a custom **Integration** repository and install
   **TerraLyra IGNIS**.
4. Restart Home Assistant.
5. Add **TerraLyra IGNIS** under **Settings → Devices & services** and recreate
   the monitored locations and optional provider settings.
6. Confirm that only one active IGNIS config entry exists and that provider
   health is visible for the expected sources.

## Update Home Assistant references

- Replace the Map-card geolocation source with `terralyra_ignis`.
- Update generated entity IDs from `*.terralyra_*` to their new
  `*.terralyra_ignis_*` IDs. Customized entity IDs may differ, so verify each
  reference in Home Assistant rather than applying a blind text replacement.
- Replace event types:
  - `terralyra_new_fire` → `terralyra_ignis_new_fire`
  - `terralyra_fire_trend` → `terralyra_ignis_fire_trend`
  - `terralyra_fire_risk_increase` →
    `terralyra_ignis_fire_risk_increase`
- Replace action/service calls under `terralyra.*` with
  `terralyra_ignis.*`.

Historical entity and incident data remains in Home Assistant's recorder until
its normal retention policy removes it. The old registry entries may be removed
after the new installation and automations have been verified.

## Verification

- The integration is named **TerraLyra IGNIS**.
- Its diagnostics report the `terralyra_ignis` domain without exposing
  coordinates or credentials.
- The Map card shows current IGNIS markers after selecting the
  `terralyra_ignis` source. A source with no current geolocation entity may be
  absent from the visual picker; YAML can still contain the source explicitly.
- A restart does not recreate the old `terralyra` integration.

There is no compatibility shim. Running both domains would double provider
traffic and could create duplicate incidents and alerts.
