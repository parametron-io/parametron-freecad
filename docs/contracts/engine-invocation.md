# In-process Engine Invocation Contract

`parametron_freecad.runtime.invocation.run_engine_invocation(invocation)` is
the implemented in-process dispatcher. It returns `None` on success; outputs
are written through the delegated runtime entrypoints. Contract metadata in
`runtime/invocation_contract.py` has version `1.0`.

This callable is separate from the external executable described in
[runtime.md](../runtime.md). Importing the invocation module does not import
FreeCAD, and constructing its request objects does not access files or execute
runtime work.

## Request types and modes

All three request types are frozen, slotted dataclasses exported from
`parametron_freecad.runtime.invocation`.

`EngineRuntimeInvocation(mode, execution=None, observation=None)` accepts
exactly the modes `execute` and `observe` (`RuntimeInvocationMode`). Execute
requires only an `ExecutionInvocation`; observe requires only an
`ObservationInvocation`. Missing or mixed payloads are rejected before dispatch.
Unknown modes are rejected. `combined` is explicitly unsupported and raises
`EngineInvocationRequestError` with
`combined execute+observe runtime invocation is not supported`.

### ExecutionInvocation

| Field | Type / default | Meaning |
| --- | --- | --- |
| `working_copy` | `Path`, required | Prepared execution context directory |
| `manifest_path` | `Path`, required | Input execution manifest |
| `result_path` | `Path \| None`, required argument | Result destination; supply a writable path for successful execution |
| `freecad_module` | `Any \| None = None` | Injected FreeCAD runtime module |
| `resolve_freecad_module` | `Callable[[], Any \| None] \| None = None` | Runtime module resolver |

Execution delegates to `run_execution_entrypoint`: load and validate the
[manifest](manifest.md), resolve the contained source document, open it,
apply assignments, recompute, save, export declared artifacts, close, and
write the [result](result-and-failure.md). A supplied module takes precedence
over the resolver. There is no observation or traversal request field on
`ExecutionInvocation`.

The dispatcher validates mode/payload combinations; it does not run CLI path
validation. Callers must supply prepared, validated runtime paths. Delegated
source-document and artifact resolution enforce their containment rules.
Although the request annotation permits `result_path=None`, this is not a
successful no-result execution mode: the success writer requires a path.

### ObservationInvocation

| Field | Type | Meaning |
| --- | --- | --- |
| `document` | `Any` | Already available document state |
| `verification_data` | `Mapping[str, Any]` | Already-decoded verification request |
| `working_copy_path` | `str \| os.PathLike[str]` | Caller-supplied context metadata |
| `working_copy_sha256` | `str` | Caller-supplied digest metadata |
| `output_directory` | `str \| os.PathLike[str]` | Destination directory for observed JSON |

All fields are required. Observation delegates to `run_observation_entrypoint`
and the Engine-compatible requested-scope observation helper. It uses the
injected document without opening, mutating, recomputing, or closing it, and
writes `<output_directory>/parametron.observed.json` atomically. It does not
load a verification file or compute the supplied digest. `working_copy_path`
is payload context, not a validated containment root for this invocation.
The caller owns document lifecycle and the supplied context/digest.

The external `execute --observation-request` path additionally loads and
checks request compatibility and computes the source-file digest, as described
in [observation.md](observation.md). Those external guarantees must not be
inferred for already-decoded in-process inputs. There is no standalone external
`observe` command, although this in-process mode is implemented. External
execute-plus-observation support does not enable the callable's `combined` mode.

## Files and environment

`runtime/file_argument_contract.py` and `runtime/output_file_contract.py`
describe the file boundaries. Execution consumes the
`export_manifest_v1.json` contract and produces `result.json` plus the declared
STEP/CSV/PDF [artifacts](artifacts.md). Paths are supplied by the caller;
canonical contract filenames do not cause automatic file discovery.
Handled execution failures attempt a structured failed result; success-result
writing occurs only after successful execution. Observation produces the
canonical observed file and no execution result.

`runtime/environment_contract.py` declares no required Engine or runtime
process environment variables. The dispatcher does not read environment
configuration. External host selection via `PARAMETRON_FREECAD_BIN` is
documented in [runtime.md](../runtime.md#freecad-host-resolution).
`PARAMETRON_FREECAD_STRICT_SMOKE=1` controls optional real-FreeCAD smoke-test
strictness; it is not an invocation requirement.

## Controlled errors

The stable public error classes live in
`parametron_freecad.runtime.error_contract` and are re-exported by
`parametron_freecad.runtime.invocation`:

| Class | Boundary |
| --- | --- |
| `EngineInvocationError` | Common base, derived from `ValueError` |
| `EngineInvocationRequestError` | Invalid mode or payload combination |
| `EngineInvocationExecutionError` | Wraps delegated `ExecutionEntrypointError` |
| `EngineInvocationObservationError` | Wraps delegated `ObservationEntrypointError` |

The three specific errors derive from `EngineInvocationError`. Delegated
wrappers preserve the message and original exception through `__cause__`;
request validation raises directly. Other exception types propagate unchanged,
so this family is not a blanket wrapper for arbitrary Python failures.
These exceptions are separate from subprocess exit codes and structured
failure-file payloads.

The callable performs runtime execution or observation, not check evaluation,
expected/observed comparison, or verification decisions; those remain
Engine-owned.

Source coverage includes `tests/test_runtime_invocation.py`,
`tests/test_invocation_contract.py`, `tests/test_error_contract.py`, and the
environment, file-argument, and output-file contract tests.
