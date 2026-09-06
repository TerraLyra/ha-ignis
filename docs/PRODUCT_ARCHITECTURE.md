# TerraLyra product architecture

TerraLyra is the umbrella project. Each hazard product is an independently
installable Home Assistant integration with its own repository, domain,
configuration and release lifecycle.

| Product | Purpose | Repository | Home Assistant domain |
|---|---|---|---|
| IGNIS | Wildfire detection, corroboration and fire risk | `ha-ignis` | `terralyra_ignis` |
| TREMOR | Earthquakes and related ground hazards | `ha-tremor` | `terralyra_tremor` |
| FLUMEN | Flood and hydrological monitoring | `ha-flumen` | `terralyra_flumen` |
| AERIS | Atmospheric and air-quality hazards | `ha-aeris` | `terralyra_aeris` |

Only IGNIS is implemented in this repository. The other names describe the
planned product boundary and do not promise a release date or feature set.

## Boundary rules

- The GitHub organization remains `TerraLyra`; product names do not replace the
  organization or human authorship shown in commits.
- A repository contains one Home Assistant integration domain and one primary
  hazard product.
- Entity IDs, events, actions, storage keys and diagnostics use that product's
  domain. Generic names such as `terralyra` are not reused.
- Provider adapters retain upstream provider, satellite, product, time,
  quality and licence attribution. TerraLyra product names identify the
  integration, not the source observations.
- A contextual observation belongs in a product when it directly improves that
  hazard workflow. For example, land-surface temperature may support IGNIS fire
  awareness without becoming a general environmental-data bundle.
- Cross-product cloud accounts, subscriptions and remote processing are not
  dependencies of the open-source integrations.

## Shared-code policy

Do not create a shared runtime package in anticipation of reuse. Extract a
small versioned library only after at least two products need the same stable
behaviour and can accept coordinated dependency releases. Until then, duplicate
a small abstraction rather than coupling independent integrations prematurely.

Candidate shared concepts include bounded HTTP transport, privacy-safe
diagnostics, monitored-location value objects and provider-health vocabulary.
Hazard scoring, incident correlation, entities, translations and configuration
remain product-owned unless proven otherwise.

## Compatibility policy

Released products evolve within their own domain. Breaking domain or repository
renames require an explicit migration guide and should happen before public
distribution. Cross-domain automatic config-entry migration is not attempted,
because Home Assistant loads and owns each integration domain independently.

The IGNIS migration in v0.14.0 is the naming reset that establishes these rules.
