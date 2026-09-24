"""Deterministic ordering for already-observed Phase 2 observation payloads."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from parametron_freecad.observation.observed_contract import (
    OBSERVATION_CONTRACT,
    TARGET_STATE_BOOLEAN_FIELDS,
    TARGET_STATE_EXISTENCE_FIELDS,
    TARGET_STATE_FAMILIES,
)


class ObservationOrderingError(ValueError):
    """Base class for observation ordering errors."""


class ObservationOrderingRequestError(ObservationOrderingError):
    """Raised when the supplied observation payload shape is malformed."""


_CATEGORY_ITEM_FIELDS: dict[str, tuple[str, ...]] = {
    OBSERVATION_CONTRACT.parameters_field: OBSERVATION_CONTRACT.parameter.fields,
    OBSERVATION_CONTRACT.metadata_field: OBSERVATION_CONTRACT.metadata.fields,
    OBSERVATION_CONTRACT.references_field: OBSERVATION_CONTRACT.reference.fields,
    OBSERVATION_CONTRACT.components_field: OBSERVATION_CONTRACT.component.fields,
}


def _read_category_items(category: str, value: Any) -> tuple[Any, ...]:
    if isinstance(value, (str, bytes)) or isinstance(value, Mapping):
        raise ObservationOrderingRequestError(
            f"observation category {category!r} must be an iterable of mappings, "
            f"got {type(value).__name__!r}"
        )
    if not isinstance(value, Iterable):
        raise ObservationOrderingRequestError(
            f"observation category {category!r} must be an iterable of mappings, "
            f"got {type(value).__name__!r}"
        )
    return tuple(value)


def _order_item(
    category: str,
    index: int,
    item: Any,
    fields: tuple[str, ...],
) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise ObservationOrderingRequestError(
            f"observation category {category!r} item at index {index} "
            f"must be a mapping, got {type(item).__name__!r}"
        )

    ordered_item: dict[str, Any] = {}
    for field in fields:
        if field not in item:
            raise ObservationOrderingRequestError(
                f"observation category {category!r} item at index {index} "
                f"missing required field {field!r}"
            )
        ordered_item[field] = item[field]
    return ordered_item


def _order_target_state(value: Any) -> dict[str, tuple[dict[str, Any], ...]]:
    if not isinstance(value, Mapping) or set(value) != set(TARGET_STATE_FAMILIES):
        raise ObservationOrderingRequestError("observation.targetState must contain exactly the three fact arrays")
    result: dict[str, tuple[dict[str, Any], ...]] = {}
    for family in TARGET_STATE_FAMILIES:
        raw = value[family]
        if not isinstance(raw, (list, tuple)):
            raise ObservationOrderingRequestError(f"observation.targetState.{family} must be an array")
        ordered: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for index, item in enumerate(raw):
            location = f"observation.targetState.{family}[{index}]"
            if not isinstance(item, Mapping):
                raise ObservationOrderingRequestError(f"{location} must be a mapping")
            destination, object_name, status = (item.get("destination"), item.get("object"), item.get("status"))
            if destination not in ("assembly", "part") or not isinstance(destination, str):
                raise ObservationOrderingRequestError(f"{location}.destination is invalid")
            if (not isinstance(object_name, str) or not object_name.strip()
                    or object_name.strip() != object_name or "\x00" in object_name):
                raise ObservationOrderingRequestError(f"{location}.object is invalid")
            identity = (destination, object_name)
            if identity in seen:
                raise ObservationOrderingRequestError(f"{location} duplicates an earlier identity")
            seen.add(identity)
            if family == "existence":
                fields = TARGET_STATE_EXISTENCE_FIELDS
                valid = status in ("exists", "absent", "unavailable") and set(item) == set(fields)
            else:
                fields = TARGET_STATE_BOOLEAN_FIELDS
                valid = (status == "observed" and type(item.get("value")) is bool and set(item) == set(fields)) or (
                    status in ("target_missing", "unavailable") and set(item) == set(fields[:-1])
                )
            if not valid:
                raise ObservationOrderingRequestError(f"{location} has invalid status or value")
            ordered.append({field: item[field] for field in fields if field in item})
        result[family] = tuple(sorted(ordered, key=lambda item: (item["destination"], item["object"])))
    return result


def order_observation_payload(
    observation_data: Mapping[str, Any],
) -> dict[str, Any]:
    """Return observation_data ordered according to the observed contract.

    Unknown top-level categories and unknown item fields are ignored. Category
    and item mappings are rebuilt without mutating the supplied objects.
    """
    if not isinstance(observation_data, Mapping):
        raise ObservationOrderingRequestError(
            f"observation_data must be a mapping, "
            f"got {type(observation_data).__name__!r}"
        )

    ordered_observation: dict[str, Any] = {}
    for category in OBSERVATION_CONTRACT.fields:
        if category not in observation_data:
            continue

        if category == OBSERVATION_CONTRACT.target_state_field:
            ordered_observation[category] = _order_target_state(observation_data[category])
            continue

        fields = _CATEGORY_ITEM_FIELDS[category]
        items = _read_category_items(category, observation_data[category])
        ordered_observation[category] = tuple(
            _order_item(category, index, item, fields)
            for index, item in enumerate(items)
        )

    return ordered_observation


__all__ = [
    "ObservationOrderingError",
    "ObservationOrderingRequestError",
    "order_observation_payload",
]
