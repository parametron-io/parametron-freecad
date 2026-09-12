"""Engine-to-FreeCAD environment-variable contract metadata."""

from __future__ import annotations

from dataclasses import dataclass

ENVIRONMENT_CONTRACT_VERSION = "1.0"

PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE = "PARAMETRON_FREECAD_BIN"
PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE = "PARAMETRON_FREECAD_STRICT_SMOKE"

ENVIRONMENT_VARIABLE_SCOPE_ENGINE_INTEGRATION_LAUNCH = "engine_integration_launch"
ENVIRONMENT_VARIABLE_SCOPE_SMOKE_TEST = "smoke_test"

PARAMETRON_FREECAD_BIN_VALUE_CONTRACT = (
    "path to an executable freecadcmd binary or wrapper"
)
PARAMETRON_FREECAD_STRICT_SMOKE_VALUE_CONTRACT = (
    'exact string "1" enables strict smoke failure behavior in optional '
    "real-FreeCAD smoke coverage"
)


@dataclass(frozen=True, slots=True)
class EnvironmentVariableSpec:
    """Immutable metadata for one Engine-to-FreeCAD environment variable."""

    name: str
    required: bool
    scope: str
    purpose: str
    value_contract: str


@dataclass(frozen=True, slots=True)
class EngineEnvironmentContract:
    """Engine-to-FreeCAD environment-variable contract metadata."""

    version: str
    required_engine_environment_variables: tuple[str, ...]
    required_runtime_process_environment_variables: tuple[str, ...]
    optional_smoke_test_environment_variables: tuple[str, ...]
    variables: tuple[EnvironmentVariableSpec, ...]


REQUIRED_ENGINE_ENVIRONMENT_VARIABLES: tuple[str, ...] = ()
REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES: tuple[str, ...] = ()

OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES = (
    PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE,
    PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE,
)

PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE_SPEC = EnvironmentVariableSpec(
    name=PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE,
    required=False,
    scope=ENVIRONMENT_VARIABLE_SCOPE_ENGINE_INTEGRATION_LAUNCH,
    purpose=(
        "optional launch boundary for local development and integration "
        "harnesses that locate FreeCAD through environment configuration"
    ),
    value_contract=PARAMETRON_FREECAD_BIN_VALUE_CONTRACT,
)

PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE_SPEC = EnvironmentVariableSpec(
    name=PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE,
    required=False,
    scope=ENVIRONMENT_VARIABLE_SCOPE_SMOKE_TEST,
    purpose=(
        "optional smoke/test strictness switch; not an Engine runtime requirement"
    ),
    value_contract=PARAMETRON_FREECAD_STRICT_SMOKE_VALUE_CONTRACT,
)

ENGINE_ENVIRONMENT_VARIABLE_SPECS = (
    PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE_SPEC,
    PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE_SPEC,
)

ENGINE_ENVIRONMENT_CONTRACT = EngineEnvironmentContract(
    version=ENVIRONMENT_CONTRACT_VERSION,
    required_engine_environment_variables=REQUIRED_ENGINE_ENVIRONMENT_VARIABLES,
    required_runtime_process_environment_variables=(
        REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES
    ),
    optional_smoke_test_environment_variables=OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES,
    variables=ENGINE_ENVIRONMENT_VARIABLE_SPECS,
)


__all__ = [
    "ENGINE_ENVIRONMENT_CONTRACT",
    "ENGINE_ENVIRONMENT_VARIABLE_SPECS",
    "ENVIRONMENT_CONTRACT_VERSION",
    "ENVIRONMENT_VARIABLE_SCOPE_ENGINE_INTEGRATION_LAUNCH",
    "ENVIRONMENT_VARIABLE_SCOPE_SMOKE_TEST",
    "EngineEnvironmentContract",
    "EnvironmentVariableSpec",
    "OPTIONAL_SMOKE_TEST_ENVIRONMENT_VARIABLES",
    "PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE",
    "PARAMETRON_FREECAD_BIN_ENVIRONMENT_VARIABLE_SPEC",
    "PARAMETRON_FREECAD_BIN_VALUE_CONTRACT",
    "PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE",
    "PARAMETRON_FREECAD_STRICT_SMOKE_ENVIRONMENT_VARIABLE_SPEC",
    "PARAMETRON_FREECAD_STRICT_SMOKE_VALUE_CONTRACT",
    "REQUIRED_ENGINE_ENVIRONMENT_VARIABLES",
    "REQUIRED_RUNTIME_PROCESS_ENVIRONMENT_VARIABLES",
]
