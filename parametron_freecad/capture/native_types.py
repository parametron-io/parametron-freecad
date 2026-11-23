"""Shared FreeCAD native property type sets for capture and semantic maps.

These sets mirror the implemented FreeCAD capture contract. Parameter
candidates may use scalar and Quantity-family native types. Metadata mutation
and observation support exactly six native types. The semantic-map template
uses the same metadata table so discovery and generated mapping policy cannot
drift silently.
"""

from __future__ import annotations

from types import MappingProxyType

NATIVE_VALUE_KIND_BY_TYPE = MappingProxyType(
    {
        "App::PropertyString": "string",
        "App::PropertyBool": "boolean",
        "App::PropertyFloat": "float",
        "App::PropertyFloatConstraint": "float",
        "App::PropertyInteger": "integer",
        "App::PropertyIntegerConstraint": "integer",
        "App::PropertyLength": "length",
        "App::PropertyDistance": "distance",
        "App::PropertyAngle": "angle",
        "App::PropertyQuantity": "quantity",
    }
)

QUANTITY_NATIVE_TYPES = frozenset(
    {
        "App::PropertyLength",
        "App::PropertyDistance",
        "App::PropertyAngle",
        "App::PropertyQuantity",
    }
)
QUANTITY_NATIVE_KINDS = frozenset({"length", "distance", "angle", "quantity"})

PARAMETER_NATIVE_TYPES = frozenset(NATIVE_VALUE_KIND_BY_TYPE)

METADATA_RESOLVED_VALUE_KINDS = MappingProxyType(
    {
        "App::PropertyString": "string",
        "App::PropertyBool": "boolean",
        "App::PropertyFloat": "number",
        "App::PropertyFloatConstraint": "number",
        "App::PropertyInteger": "integer",
        "App::PropertyIntegerConstraint": "integer",
    }
)
METADATA_NATIVE_TYPES = frozenset(METADATA_RESOLVED_VALUE_KINDS)


__all__ = [
    "METADATA_NATIVE_TYPES",
    "METADATA_RESOLVED_VALUE_KINDS",
    "NATIVE_VALUE_KIND_BY_TYPE",
    "PARAMETER_NATIVE_TYPES",
    "QUANTITY_NATIVE_KINDS",
    "QUANTITY_NATIVE_TYPES",
]
