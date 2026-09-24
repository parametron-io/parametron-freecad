"""Request-scoped reads of live FreeCAD target state."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from parametron_freecad.observation.verification_contract import (
    OBSERVATION_CONTEXT_FIELD_TARGET_STATE,
    OBSERVE_FIELD_TARGET_STATE,
    TARGET_IDENTITY_FIELDS,
    TARGET_STATE_FAMILIES,
)


class TargetStateObservationError(ValueError):
    """Invalid target-state request or failed native observation."""


def requested_target_state(verification_data: Mapping[str, Any]) -> dict[str, tuple[dict[str, str], ...]] | None:
    """Validate the canonical optional request before any native lookup."""
    if not isinstance(verification_data, Mapping):
        raise TargetStateObservationError("verification request must be an object")
    observe = verification_data.get("observe")
    context = verification_data.get("observationContext", {})
    if (not isinstance(observe, Mapping) or OBSERVE_FIELD_TARGET_STATE not in observe) and (
        not isinstance(context, Mapping) or OBSERVATION_CONTEXT_FIELD_TARGET_STATE not in context
    ):
        return None
    if verification_data.get("schemaVersion") != "1.0":
        raise TargetStateObservationError("unsupported verification schemaVersion")
    if not isinstance(observe, Mapping) or not isinstance(context, Mapping):
        raise TargetStateObservationError("observe and observationContext must be objects")
    enabled = observe.get(OBSERVE_FIELD_TARGET_STATE, False)
    if type(enabled) is not bool:
        raise TargetStateObservationError("observe.targetState must be a boolean")
    present = OBSERVATION_CONTEXT_FIELD_TARGET_STATE in context
    if enabled != present:
        raise TargetStateObservationError(
            "observe.targetState must be true exactly when observationContext.targetState is present"
        )
    if not present:
        return None
    raw = context[OBSERVATION_CONTEXT_FIELD_TARGET_STATE]
    if not isinstance(raw, Mapping) or set(raw) != set(TARGET_STATE_FAMILIES):
        raise TargetStateObservationError("observationContext.targetState must contain exactly the three fact arrays")
    result: dict[str, tuple[dict[str, str], ...]] = {}
    for family in TARGET_STATE_FAMILIES:
        entries = raw[family]
        if not isinstance(entries, list):
            raise TargetStateObservationError(f"observationContext.targetState.{family} must be an array")
        seen: set[tuple[str, str]] = set()
        canonical: list[dict[str, str]] = []
        for index, entry in enumerate(entries):
            location = f"observationContext.targetState.{family}[{index}]"
            if not isinstance(entry, Mapping) or set(entry) != set(TARGET_IDENTITY_FIELDS):
                raise TargetStateObservationError(f"{location} must contain exactly destination and object")
            destination, object_name = entry["destination"], entry["object"]
            if destination not in ("assembly", "part") or not isinstance(destination, str):
                raise TargetStateObservationError(f"{location}.destination must be assembly or part")
            if (not isinstance(object_name, str) or not object_name.strip()
                    or object_name.strip() != object_name or "\x00" in object_name):
                raise TargetStateObservationError(f"{location}.object must be a non-blank exact native object name")
            identity = (destination, object_name)
            if identity in seen:
                raise TargetStateObservationError(f"{location} duplicates an earlier identity")
            seen.add(identity)
            canonical.append({"destination": destination, "object": object_name})
        result[family] = tuple(sorted(canonical, key=lambda item: (item["destination"], item["object"])))
    if not any(result.values()):
        raise TargetStateObservationError("observationContext.targetState must request at least one fact")
    return result


def _native_bool(target: Any, property_name: str) -> bool | None:
    """Return None only when the supported App::PropertyBool is absent."""
    try:
        properties = target.PropertiesList
    except AttributeError:
        return None
    if property_name not in properties:
        return None
    try:
        property_type = target.getTypeIdOfProperty
    except AttributeError:
        return None
    if not callable(property_type):
        return None
    if property_type(property_name) != "App::PropertyBool":
        return None
    try:
        value = getattr(target, property_name)
    except AttributeError:
        return None
    return value if type(value) is bool else None


def observe_target_state(
    document: Any, request: Mapping[str, tuple[dict[str, str], ...]]
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Read only the requested native facts using exact getObject lookup."""
    try:
        get_object = document.getObject
        if not callable(get_object):
            raise TypeError("document.getObject is not callable")
    except Exception as exc:
        raise TargetStateObservationError("native getObject access failed") from exc

    result: dict[str, tuple[dict[str, Any], ...]] = {}
    for family in TARGET_STATE_FAMILIES:
        entries: list[dict[str, Any]] = []
        for identity in request[family]:
            evidence: dict[str, Any] = dict(identity)
            try:
                target = get_object(identity["object"])
                if family == "existence":
                    evidence["status"] = "absent" if target is None else "exists"
                elif target is None:
                    evidence["status"] = "target_missing"
                else:
                    property_name = "Suppressed" if family == "suppression" else "Visibility"
                    value = _native_bool(target, property_name)
                    evidence["status"] = "unavailable" if value is None else "observed"
                    if value is not None:
                        evidence["value"] = value
            except Exception as exc:
                raise TargetStateObservationError(
                    f"native {family} observation failed for {identity['object']!r}"
                ) from exc
            entries.append(evidence)
        result[family] = tuple(entries)
    return result
