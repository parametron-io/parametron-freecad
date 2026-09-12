"""Deterministic ordering for already-observed Phase 2 observation payloads."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from parametron_freecad.observation.observed_contract import OBSERVATION_CONTRACT


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


def order_observation_payload(
    observation_data: Mapping[str, Any],
) -> dict[str, tuple[dict[str, Any], ...]]:
    """Return observation_data ordered according to the observed contract.

    Unknown top-level categories and unknown item fields are ignored. Category
    and item mappings are rebuilt without mutating the supplied objects.
    """
    if not isinstance(observation_data, Mapping):
        raise ObservationOrderingRequestError(
            f"observation_data must be a mapping, "
            f"got {type(observation_data).__name__!r}"
        )

    ordered_observation: dict[str, tuple[dict[str, Any], ...]] = {}
    for category in OBSERVATION_CONTRACT.fields:
        if category not in observation_data:
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
