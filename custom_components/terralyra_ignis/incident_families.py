"""Conservative grouping of persistent source tracks into fire incidents."""

from __future__ import annotations

from datetime import timedelta

from .clustering import haversine_km
from .models import (
    ConfirmationLevel,
    DistanceTrend,
    FireCluster,
    FireLifecycle,
    IncidentLocationMatch,
    MetricTrend,
)

MIN_CROSS_SOURCE_LINK_KM = 8.0
MAX_FAMILY_DIAMETER_KM = 16.0


def consolidate_incident_families(
    clusters: list[FireCluster],
    *,
    home_latitude: float,
    home_longitude: float,
    matching_radius_km: float,
    matching_window: timedelta,
) -> list[FireCluster]:
    """Return one stable presentation incident for related source tracks.

    Raw source tracks are retained.  This second, deliberately conservative
    layer only controls the incident identity published to Home Assistant.
    Complete-link diameter protection prevents a chain of nearby hotspots from
    joining two genuinely separate fires.
    """
    ordered = sorted(
        (cluster for cluster in clusters if cluster.track_id),
        key=lambda item: (_first_seen(item), item.track_id or ""),
    )
    groups: list[list[FireCluster]] = []
    for cluster in ordered:
        candidates = [
            group
            for group in groups
            if _can_join(
                cluster,
                group,
                matching_radius_km=matching_radius_km,
                matching_window=matching_window,
            )
        ]
        if not candidates:
            groups.append([cluster])
            continue
        # Joining more than one group could bridge two distinct incidents.
        # Choose the nearest compatible family and leave the other untouched.
        target = min(candidates, key=lambda group: _distance_to_group(cluster, group))
        target.append(cluster)

    family_ids = _stable_family_ids(groups)
    result: list[FireCluster] = []
    for group, family_id in zip(groups, family_ids, strict=True):
        for member in group:
            member.family_id = family_id
        result.append(
            _family_cluster(
                group,
                family_id=family_id,
                home_latitude=home_latitude,
                home_longitude=home_longitude,
            )
        )
    return sorted(result, key=lambda item: item.distance_km)


def _can_join(
    candidate: FireCluster,
    group: list[FireCluster],
    *,
    matching_radius_km: float,
    matching_window: timedelta,
) -> bool:
    diameter_limit = max(MAX_FAMILY_DIAMETER_KM, matching_radius_km * 4)
    inherited_family = candidate.family_id
    if inherited_family and any(
        member.family_id == inherited_family for member in group
    ):
        return any(
            _temporally_related(candidate, member, matching_window) for member in group
        ) and all(
            haversine_km(
                candidate.latitude,
                candidate.longitude,
                member.latitude,
                member.longitude,
            )
            <= diameter_limit
            for member in group
        )
    if not any(
        _temporally_related(candidate, member, matching_window)
        and haversine_km(
            candidate.latitude,
            candidate.longitude,
            member.latitude,
            member.longitude,
        )
        <= _link_radius(candidate, member, matching_radius_km)
        for member in group
    ):
        return False
    return all(
        haversine_km(
            candidate.latitude,
            candidate.longitude,
            member.latitude,
            member.longitude,
        )
        <= diameter_limit
        for member in group
    )


def _temporally_related(
    left: FireCluster, right: FireCluster, window: timedelta
) -> bool:
    left_start, left_end = _first_seen(left), _last_seen(left)
    right_start, right_end = _first_seen(right), _last_seen(right)
    if left_start <= right_end and right_start <= left_end:
        return True
    gap = min(abs(left_start - right_end), abs(right_start - left_end))
    return gap <= window


def _link_radius(
    left: FireCluster, right: FireCluster, configured_radius_km: float
) -> float:
    left_families = _evidence_families(left)
    right_families = _evidence_families(right)
    independent = left_families.isdisjoint(right_families)
    already_corroborated = (
        left.confirmation_level is ConfirmationLevel.MULTI_SOURCE
        or right.confirmation_level is ConfirmationLevel.MULTI_SOURCE
    )
    if independent or already_corroborated:
        return max(configured_radius_km, MIN_CROSS_SOURCE_LINK_KM)
    return configured_radius_km


def _evidence_families(cluster: FireCluster) -> set[str]:
    aliases = {
        "eumetsat_lsa_saf": "lsa_saf_frp",
        "eumetsat_lsa_saf_iodc": "lsa_saf_frp",
    }
    return {aliases.get(provider, provider) for provider in cluster.providers}


def _stable_family_ids(groups: list[list[FireCluster]]) -> list[str]:
    proposals: list[tuple[str, bool]] = []
    for group in groups:
        inherited = [member.family_id for member in group if member.family_id]
        anchored = [
            family_id
            for family_id in inherited
            if any(member.track_id == family_id for member in group)
        ]
        proposals.append(
            (
                min(anchored or inherited)
                if inherited
                else min(
                    group, key=lambda item: (_first_seen(item), item.track_id or "")
                ).track_id
                or "unknown",
                bool(anchored),
            )
        )

    # A previously grouped family can split as observations move apart.  Give
    # the inherited ID to the group that still contains its original anchor,
    # regardless of iteration order; every other split gets a source-track ID.
    used: set[str] = set()
    result = ["" for _group in groups]
    allocation_order = sorted(
        range(len(groups)),
        key=lambda index: (
            not proposals[index][1],
            min(_first_seen(member) for member in groups[index]),
            proposals[index][0],
        ),
    )
    for index in allocation_order:
        group = groups[index]
        family_id = proposals[index][0]
        if family_id in used:
            family_id = next(
                (
                    candidate
                    for candidate in sorted(
                        member.track_id or "unknown" for member in group
                    )
                    if candidate not in used
                ),
                f"{family_id}-split-{index + 1}",
            )
        used.add(family_id)
        result[index] = family_id
    return result


def _family_cluster(
    members: list[FireCluster],
    *,
    family_id: str,
    home_latitude: float,
    home_longitude: float,
) -> FireCluster:
    representative = max(
        members,
        key=lambda item: (
            item.confirmation_level is ConfirmationLevel.MULTI_SOURCE,
            _last_seen(item),
            item.confidence,
        ),
    )
    providers = tuple(sorted({value for item in members for value in item.providers}))
    satellites = tuple(sorted({value for item in members for value in item.satellites}))
    source_track_ids = tuple(sorted(item.track_id or "unknown" for item in members))
    evidence_families = {
        value for member in members for value in _evidence_families(member)
    }
    confirmation_level = (
        ConfirmationLevel.MULTI_SOURCE
        if len(evidence_families) > 1
        or any(
            member.confirmation_level is ConfirmationLevel.MULTI_SOURCE
            for member in members
        )
        else _weakest_available_confirmation(members)
    )
    first_seen = min(_first_seen(item) for item in members)
    last_seen = max(_last_seen(item) for item in members)
    lifecycle = _family_lifecycle(members)
    extent = max(
        (
            haversine_km(
                left.latitude,
                left.longitude,
                right.latitude,
                right.longitude,
            )
            for index, left in enumerate(members)
            for right in members[index + 1 :]
        ),
        default=0.0,
    )
    return FireCluster(
        latitude=representative.latitude,
        longitude=representative.longitude,
        distance_km=haversine_km(
            home_latitude,
            home_longitude,
            representative.latitude,
            representative.longitude,
        ),
        confidence=max(item.confidence for item in members),
        frp_mw=max(item.frp_mw for item in members),
        acquired=last_seen,
        pixel_count=max(item.pixel_count for item in members),
        track_id=family_id,
        family_id=family_id,
        source_track_ids=source_track_ids,
        incident_extent_km=extent,
        peak_frp_mw=max(item.peak_frp_mw or item.frp_mw for item in members),
        place_name=representative.place_name,
        nearest_settlement=representative.nearest_settlement,
        location_description=representative.location_description,
        place_attribution=representative.place_attribution,
        lifecycle=lifecycle,
        first_seen=first_seen,
        last_seen=last_seen,
        minimum_distance_km=min(
            item.minimum_distance_km or item.distance_km for item in members
        ),
        maximum_frp_mw=max(item.maximum_frp_mw or item.frp_mw for item in members),
        maximum_pixel_count=max(
            item.maximum_pixel_count or item.pixel_count for item in members
        ),
        detections_total=max(
            item.detections_total or item.pixel_count for item in members
        ),
        maximum_confidence=max(
            item.maximum_confidence or item.confidence for item in members
        ),
        frp_trend=_strongest_metric_trend(members, "frp_trend"),
        activity_trend=_strongest_metric_trend(members, "activity_trend"),
        distance_trend=_strongest_distance_trend(members),
        trend_samples=max(item.trend_samples or 0 for item in members),
        trend_window_minutes=max(item.trend_window_minutes or 0.0 for item in members),
        confirmation_level=confirmation_level,
        providers=providers,
        satellites=satellites,
        corroborating_detections=sum(item.corroborating_detections for item in members),
        source_url=representative.source_url,
        location_matches=_merge_location_matches(members),
    )


def _merge_location_matches(
    members: list[FireCluster],
) -> tuple[IncidentLocationMatch, ...]:
    by_location: dict[str, IncidentLocationMatch] = {}
    for member in members:
        for match in member.location_matches:
            current = by_location.get(match.location_id)
            if current is None or match.distance_km < current.distance_km:
                by_location[match.location_id] = match
    return tuple(sorted(by_location.values(), key=lambda item: item.distance_km))


def _family_lifecycle(members: list[FireCluster]) -> FireLifecycle:
    for state in (
        FireLifecycle.NEW,
        FireLifecycle.CONTINUING,
        FireLifecycle.INACTIVE,
        FireLifecycle.ENDED,
    ):
        if any(member.lifecycle is state for member in members):
            return state
    return FireLifecycle.CONTINUING


def _weakest_available_confirmation(
    members: list[FireCluster],
) -> ConfirmationLevel:
    levels = {member.confirmation_level for member in members}
    if ConfirmationLevel.SINGLE_SOURCE in levels:
        return ConfirmationLevel.SINGLE_SOURCE
    if ConfirmationLevel.NOT_AVAILABLE in levels:
        return ConfirmationLevel.NOT_AVAILABLE
    return next(iter(levels), ConfirmationLevel.SINGLE_SOURCE)


def _strongest_metric_trend(members: list[FireCluster], field: str) -> MetricTrend:
    values = {getattr(member, field) for member in members}
    for value in (
        MetricTrend.INCREASING,
        MetricTrend.DECREASING,
        MetricTrend.STABLE,
        MetricTrend.UNKNOWN,
    ):
        if value in values:
            return value
    return MetricTrend.UNKNOWN


def _strongest_distance_trend(members: list[FireCluster]) -> DistanceTrend:
    values = {member.distance_trend for member in members}
    for value in (
        DistanceTrend.APPROACHING,
        DistanceTrend.RECEDING,
        DistanceTrend.STABLE,
        DistanceTrend.UNKNOWN,
    ):
        if value in values:
            return value
    return DistanceTrend.UNKNOWN


def _distance_to_group(candidate: FireCluster, group: list[FireCluster]) -> float:
    return min(
        haversine_km(
            candidate.latitude,
            candidate.longitude,
            member.latitude,
            member.longitude,
        )
        for member in group
    )


def _first_seen(cluster: FireCluster):
    return cluster.first_seen or cluster.acquired


def _last_seen(cluster: FireCluster):
    return cluster.last_seen or cluster.acquired
