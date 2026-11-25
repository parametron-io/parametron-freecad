"""GUI-free capture session that ties panel state to core orchestration.

The session owns the project context, explicit model selection, native
discovery, and the top-down panel state. It exposes review previews and the
confirmed atomic write from the GUI-free capture orchestration layer. It never
imports FreeCAD, FreeCADGui, or Qt.

The native caller must verify the active document is the declared saved source
before creating a session. Capture never mutates the source document or the
project mapping.
"""

from __future__ import annotations

from parametron_workbench.state import (
    CapturePanelOptions,
    CapturePanelSnapshot,
    CapturePanelState,
)

from parametron_freecad.capture import (
    CaptureDiscovery,
    CaptureOutputPlan,
    CaptureProjectContext,
    CaptureWriteSummary,
    EnginePreflightRunner,
    FreeCADSemanticMapSelection,
    ProjectModel,
    plan_capture_outputs,
    write_capture_outputs,
)
from parametron_freecad.capture.decisions import derive_capture_id


class CaptureSession:
    """One capture operation for an explicit project source document."""

    def __init__(
        self,
        *,
        context: CaptureProjectContext,
        model: ProjectModel,
        discovery: CaptureDiscovery,
        semantic_selection: FreeCADSemanticMapSelection,
        options: CapturePanelOptions | None = None,
    ) -> None:
        if not isinstance(context, CaptureProjectContext):
            raise TypeError("CaptureSession requires CaptureProjectContext")
        if not isinstance(model, ProjectModel):
            raise TypeError("CaptureSession requires ProjectModel")
        if not isinstance(discovery, CaptureDiscovery):
            raise TypeError("CaptureSession requires CaptureDiscovery")

        self._context = context
        self._model = model
        self._discovery = discovery
        self._semantic_selection = semantic_selection
        self.state = CapturePanelState(
            discovery,
            semantic_selection,
            options=options or default_options(context, model),
        )

    @property
    def context(self) -> CaptureProjectContext:
        return self._context

    @property
    def model(self) -> ProjectModel:
        return self._model

    @property
    def discovery(self) -> CaptureDiscovery:
        return self._discovery

    def snapshot(self) -> CapturePanelSnapshot:
        return self.state.snapshot()

    def preview(self) -> CaptureOutputPlan:
        """Build the deterministic review plan without writing anything."""

        return plan_capture_outputs(
            context=self._context,
            model=self._model,
            discovery=self._discovery,
            decisions=self.state.build_decisions(),
            semantic_selection=self.state.build_semantic_selection(),
        )

    def commit(
        self,
        *,
        confirm_replace: bool,
        preflight: EnginePreflightRunner | None = None,
    ) -> CaptureWriteSummary:
        """Write both project-root outputs after explicit confirmation."""

        return write_capture_outputs(
            self.preview(),
            confirm_replace=confirm_replace,
            preflight=preflight,
        )


def default_options(
    context: CaptureProjectContext,
    model: ProjectModel,
    *,
    cad_system_version: str = "",
) -> CapturePanelOptions:
    """Return capture options with a deterministic default capture ID."""

    return CapturePanelOptions(
        capture_id=derive_capture_id(context.project_id, model.logical_id),
        cad_system_version=cad_system_version,
    )


__all__ = ["CaptureSession", "default_options"]
