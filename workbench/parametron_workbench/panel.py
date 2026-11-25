"""FreeCAD/Qt top-down capture panel.

This is the GUI layer. All capture state, validation, preview, drift, and
writing logic lives in the GUI-free ``parametron_workbench.state`` and
``parametron_workbench.session`` modules and the ``parametron_freecad.capture``
core. The panel only renders snapshots and forwards user edits.

The panel never mutates the source document or the project mapping. Writing
project-root capture outputs happens only through the core atomic writer after
the user reviews the diff and confirms.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from typing import Any

from parametron_freecad.capture import (
    CaptureDriftError,
    CaptureError,
    CaptureOrchestrationError,
    CaptureWriteError,
    SemanticMapError,
)
from parametron_workbench.qt import QtCore, QtWidgets
from parametron_workbench.state import CapturePanelError, CaptureTab

_NAME_COLUMN = {
    CaptureTab.PARTS: 4,
    CaptureTab.FEATURES: 4,
    CaptureTab.PARAMETERS: 5,
}


def _console_message(message: str) -> None:
    try:
        import FreeCAD

        FreeCAD.Console.PrintMessage("Parametron: " + message + "\n")
    except Exception:
        pass


def _console_error(message: str) -> None:
    try:
        import FreeCAD

        FreeCAD.Console.PrintError("Parametron: " + message + "\n")
    except Exception:
        pass


class CapturePanel(QtWidgets.QDialog):
    """Top-down capture panel for the active project source."""

    def __init__(self, session: Any, parent: Any = None) -> None:
        super().__init__(parent)
        self._session = session
        self._rendering = False
        self.setWindowTitle("Parametron Capture")
        self.resize(1100, 700)
        self._build_ui()
        self._render()

    # -- construction ----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        self._tabs = QtWidgets.QTabWidget()
        self._part_table = self._make_table(
            [
                "Capture",
                "Kind",
                "Native Ref",
                "CAD Type",
                "Semantic Name",
                "Display Name",
                "ID Preview",
                "Notes",
            ]
        )
        self._feature_table = self._make_table(
            [
                "Capture",
                "Component",
                "Native Ref",
                "CAD Type",
                "Semantic Name",
                "ID Preview",
                "Captured Actions",
                "Authorized Actions",
                "Notes",
            ]
        )
        self._parameter_table = self._make_table(
            [
                "Capture",
                "Owner",
                "Native Key",
                "CAD Type",
                "Value Type",
                "Semantic Name",
                "Semantic Type",
                "Unit / Observability",
                "ID Preview",
                "Notes",
            ]
        )
        self._metadata_table = self._make_table(
            [
                "Capture",
                "Owner",
                "Native Key",
                "CAD Type",
                "Value Type",
                "Display Name",
                "Observable / Writable",
                "ID Preview",
                "Notes",
            ]
        )

        drawings_tab = QtWidgets.QWidget()
        drawings_layout = QtWidgets.QVBoxLayout(drawings_tab)
        drawing_buttons = QtWidgets.QHBoxLayout()
        add_drawing_button = QtWidgets.QPushButton("Add Drawing")
        add_drawing_button.clicked.connect(self._on_add_drawing)
        remove_drawing_button = QtWidgets.QPushButton("Remove Drawing")
        remove_drawing_button.clicked.connect(self._on_remove_drawing)
        drawing_buttons.addWidget(add_drawing_button)
        drawing_buttons.addWidget(remove_drawing_button)
        drawing_buttons.addStretch(1)
        drawings_layout.addLayout(drawing_buttons)
        self._drawing_table = self._make_table(
            [
                "Drawing",
                "Semantic Name",
                "Display Name",
                "Sheets",
                "ID Preview",
                "Notes",
            ]
        )
        drawings_layout.addWidget(QtWidgets.QLabel("Logical drawings"))
        drawings_layout.addWidget(self._drawing_table, 1)
        self._drawing_sheet_table = self._make_table(
            [
                "Capture",
                "Page",
                "CAD Type",
                "Drawing",
                "Semantic Name",
                "Order",
                "Display Name",
                "Targets",
                "ID Preview",
                "Notes",
            ]
        )
        drawings_layout.addWidget(QtWidgets.QLabel("Discovered sheets/pages"))
        drawings_layout.addWidget(self._drawing_sheet_table, 2)

        self._tabs.addTab(self._part_table, "Part/Assembly")
        self._tabs.addTab(self._feature_table, "Features")
        self._tabs.addTab(self._parameter_table, "Parameters")
        self._tabs.addTab(self._metadata_table, "Metadata")
        self._tabs.addTab(drawings_tab, "Drawings")
        layout.addWidget(self._tabs, 1)

        options_row = QtWidgets.QHBoxLayout()
        options_row.addWidget(QtWidgets.QLabel("Capture ID"))
        self._capture_id = QtWidgets.QLineEdit(self._session.state.options.capture_id)
        self._capture_id.editingFinished.connect(self._on_capture_id_changed)
        options_row.addWidget(self._capture_id, 1)
        layout.addLayout(options_row)

        self._status = QtWidgets.QLabel("")
        self._status.setWordWrap(True)
        layout.addWidget(self._status)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        self._review_button = QtWidgets.QPushButton("Review && Write")
        self._review_button.clicked.connect(self._on_review)
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.reject)
        buttons.addWidget(self._review_button)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _make_table(self, headers: list[str]) -> Any:
        table = QtWidgets.QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked
            | QtWidgets.QAbstractItemView.EditKeyPressed
            | QtWidgets.QAbstractItemView.SelectedClicked
        )
        table.horizontalHeader().setStretchLastSection(True)
        table.itemChanged.connect(self._on_item_changed)
        return table

    # -- rendering -------------------------------------------------------

    def _render(self) -> None:
        self._rendering = True
        try:
            snapshot = self._session.state.snapshot()
            for tab in (
                CaptureTab.FEATURES,
                CaptureTab.PARAMETERS,
                CaptureTab.METADATA,
                CaptureTab.DRAWINGS,
            ):
                index = list(CaptureTab).index(tab)
                availability = snapshot.tabs[tab]
                self._tabs.setTabEnabled(index, availability.enabled)
                self._tabs.setTabToolTip(index, availability.reason)

            self._render_parts(snapshot)
            self._render_features(snapshot)
            self._render_parameters(snapshot)
            self._render_metadata(snapshot)
            self._render_drawings(snapshot)
            self._render_drawing_sheets(snapshot)

            if snapshot.errors:
                self._status.setText("\n".join(snapshot.errors))
                self._status.setStyleSheet("color: #b00020;")
            else:
                self._status.setText("Ready to review." if snapshot.can_review else "")
                self._status.setStyleSheet("")
            self._review_button.setEnabled(snapshot.can_review)
            self._capture_id.setText(self._session.state.options.capture_id)
        finally:
            self._rendering = False

    def _render_parts(self, snapshot: Any) -> None:
        table = self._part_table
        rows = snapshot.components
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self._set_item(table, index, 0, row, checkable=True)
            self._set_text(table, index, 1, row.kind)
            self._set_text(table, index, 2, row.native_ref)
            self._set_text(table, index, 3, row.cad_type)
            self._set_editable_name(table, index, 4, row)
            self._set_text(table, index, 5, row.display_name)
            self._set_text(table, index, 6, row.id_preview or "")
            self._set_text(table, index, 7, self._notes(row))

    def _render_features(self, snapshot: Any) -> None:
        table = self._feature_table
        rows = snapshot.features
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self._set_item(table, index, 0, row, checkable=True)
            self._set_text(table, index, 1, row.component_native_ref)
            self._set_text(table, index, 2, row.native_ref)
            self._set_text(table, index, 3, row.cad_type)
            self._set_editable_name(table, index, 4, row)
            self._set_text(table, index, 5, row.id_preview or "")
            self._set_text(table, index, 6, ", ".join(row.captured_actions))
            self._set_text(table, index, 7, ", ".join(row.authorized_actions))
            self._set_text(table, index, 8, self._feature_notes(row))

    def _render_parameters(self, snapshot: Any) -> None:
        table = self._parameter_table
        rows = snapshot.parameters
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self._set_item(table, index, 0, row, checkable=True)
            self._set_text(table, index, 1, f"{row.owner_kind}:{row.owner_native_ref}")
            self._set_text(table, index, 2, row.native_key)
            self._set_text(table, index, 3, row.cad_type)
            self._set_text(table, index, 4, row.value_type)
            self._set_editable_name(table, index, 5, row)
            self._set_semantic_type_combo(table, index, 6, row)
            unit = row.semantic_unit or row.native_unit or "none"
            self._set_text(
                table,
                index,
                7,
                f"{unit} | "
                f"{'observable' if row.observable else 'not observable'}, "
                f"{'writable' if row.writable else 'read-only'}",
            )
            self._set_text(table, index, 8, row.id_preview or "")
            self._set_text(table, index, 9, self._notes(row))

    def _render_metadata(self, snapshot: Any) -> None:
        table = self._metadata_table
        rows = snapshot.metadata
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self._set_item(table, index, 0, row, checkable=True)
            self._set_text(table, index, 1, f"{row.owner_kind}:{row.owner_native_ref}")
            self._set_text(table, index, 2, row.native_key)
            self._set_text(table, index, 3, row.cad_type)
            self._set_text(table, index, 4, row.value_type)
            self._set_text(table, index, 5, row.display_name)
            self._set_text(
                table,
                index,
                6,
                f"{'observable' if row.observable else 'not observable'}, "
                f"{'writable' if row.writable else 'read-only'}",
            )
            self._set_text(table, index, 7, row.id_preview or "")
            self._set_text(table, index, 8, self._notes(row))

    def _render_drawings(self, snapshot: Any) -> None:
        table = self._drawing_table
        rows = snapshot.drawings
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self._set_drawing_key(table, index, 0, row.drawing_key)
            self._set_editable_drawing_text(table, index, 1, row.name, row.drawing_key)
            self._set_editable_drawing_text(
                table, index, 2, row.display_name, row.drawing_key
            )
            self._set_text(table, index, 3, str(row.included_sheet_count))
            self._set_text(table, index, 4, row.id_preview or "")
            self._set_text(table, index, 5, self._drawing_notes(row))

    def _render_drawing_sheets(self, snapshot: Any) -> None:
        table = self._drawing_sheet_table
        rows = snapshot.drawing_sheets
        labels = {item.drawing_key: item.name for item in snapshot.drawings}
        table.setRowCount(len(rows))
        for index, row in enumerate(rows):
            self._set_item(table, index, 0, row, checkable=True)
            self._set_text(table, index, 1, f"{row.native_ref} ({row.native_label})")
            self._set_text(table, index, 2, row.cad_type)
            self._set_drawing_group_combo(table, index, 3, row, labels)
            self._set_editable_text(table, index, 4, row.name, row.native_ref)
            self._set_editable_text(table, index, 5, str(row.order), row.native_ref)
            self._set_editable_text(table, index, 6, row.display_name, row.native_ref)
            self._set_text(table, index, 7, "; ".join(row.targets))
            self._set_text(table, index, 8, row.id_preview or "")
            self._set_text(table, index, 9, self._drawing_sheet_notes(row))

    @staticmethod
    def _drawing_notes(row: Any) -> str:
        return "; ".join(
            value
            for value in (
                getattr(row, "name_error", None),
                getattr(row, "id_error", None),
                getattr(row, "component_error", None),
            )
            if value
        )

    @staticmethod
    def _drawing_sheet_notes(row: Any) -> str:
        return "; ".join(
            value
            for value in (
                getattr(row, "name_error", None),
                getattr(row, "order_error", None),
                getattr(row, "id_error", None),
            )
            if value
        )

    @staticmethod
    def _notes(row: Any) -> str:
        parts = [
            value
            for value in (
                getattr(row, "disabled_reason", ""),
                getattr(row, "name_error", None),
                getattr(row, "id_error", None),
            )
            if value
        ]
        return "; ".join(parts)

    @staticmethod
    def _feature_notes(row: Any) -> str:
        notes = [CapturePanel._notes(row)]
        if not row.dependency_evidence_available:
            notes.append("delete dependency evidence unavailable")
        elif row.delete_dependents:
            notes.append(
                "delete blocked by dependents: " + ", ".join(row.delete_dependents)
            )
        elif "delete" in row.captured_actions:
            notes.append("delete dependency-free")
        return "; ".join(note for note in notes if note)

    def _set_semantic_type_combo(
        self, table: Any, index: int, column: int, row: Any
    ) -> None:
        combo = QtWidgets.QComboBox()
        combo.addItem("unmapped", "")
        for name in self._session.state.semantic_parameter_type_names():
            combo.addItem(name, name)
        current = row.semantic_type or ""
        position = combo.findData(current)
        combo.setCurrentIndex(position if position >= 0 else 0)
        combo.setEnabled(bool(row.authorable))
        if not row.authorable:
            combo.setToolTip(row.disabled_reason)
        combo.currentIndexChanged.connect(
            lambda _position, widget=combo, native_type=row.cad_type: (
                self._on_semantic_type_changed(widget, native_type)
            )
        )
        table.setCellWidget(index, column, combo)

    def _on_semantic_type_changed(self, combo: Any, native_type: str) -> None:
        if self._rendering:
            return
        try:
            self._session.state.set_parameter_semantic_type(
                native_type, combo.currentData() or ""
            )
        except CapturePanelError as exc:
            _console_error(str(exc))
            self._status.setText(str(exc))
            self._status.setStyleSheet("color: #b00020;")
        self._render()

    def _set_item(
        self, table: Any, index: int, column: int, row: Any, *, checkable: bool
    ) -> None:
        item = QtWidgets.QTableWidgetItem()
        item.setFlags(QtWidgets.QTableWidgetItem().flags())
        if checkable:
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            item.setCheckState(
                QtCore.Qt.Checked if row.included else QtCore.Qt.Unchecked
            )
        if getattr(row, "disabled", False):
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
            item.setToolTip(getattr(row, "disabled_reason", ""))
        item.setData(
            QtCore.Qt.UserRole,
            row.native_ref if hasattr(row, "native_ref") else row.native_path,
        )
        table.setItem(index, column, item)

    def _set_text(self, table: Any, index: int, column: int, text: str) -> None:
        item = QtWidgets.QTableWidgetItem(text)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
        table.setItem(index, column, item)

    def _set_editable_name(self, table: Any, index: int, column: int, row: Any) -> None:
        item = QtWidgets.QTableWidgetItem(row.name)
        if row.disabled:
            item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
            item.setToolTip(row.disabled_reason)
        item.setData(
            QtCore.Qt.UserRole,
            getattr(row, "native_ref", None) or getattr(row, "native_path", None),
        )
        table.setItem(index, column, item)

    def _set_editable_text(
        self, table: Any, index: int, column: int, text: str, key: str
    ) -> None:
        item = QtWidgets.QTableWidgetItem(text)
        item.setData(QtCore.Qt.UserRole, key)
        table.setItem(index, column, item)

    def _set_drawing_key(
        self, table: Any, index: int, column: int, drawing_key: str
    ) -> None:
        item = QtWidgets.QTableWidgetItem(drawing_key)
        item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEditable)
        item.setData(QtCore.Qt.UserRole, drawing_key)
        table.setItem(index, column, item)

    def _set_editable_drawing_text(
        self,
        table: Any,
        index: int,
        column: int,
        text: str,
        drawing_key: str,
    ) -> None:
        item = QtWidgets.QTableWidgetItem(text)
        item.setData(QtCore.Qt.UserRole, drawing_key)
        table.setItem(index, column, item)

    def _set_drawing_group_combo(
        self, table: Any, index: int, column: int, row: Any, labels: Mapping
    ) -> None:
        combo = QtWidgets.QComboBox()
        keys = self._session.state.drawing_group_keys()
        for key in keys:
            name = labels.get(key, "")
            combo.addItem(f"{name} ({key})" if name else key, key)
        current = row.drawing_key or (keys[0] if keys else "")
        position = combo.findData(current)
        combo.setCurrentIndex(position if position >= 0 else 0)
        combo.setEnabled(bool(keys))
        combo.currentIndexChanged.connect(
            lambda _position, widget=combo, native_ref=row.native_ref: (
                self._on_drawing_group_changed(widget, native_ref)
            )
        )
        table.setCellWidget(index, column, combo)

    # -- interaction -----------------------------------------------------

    def _on_item_changed(self, item: Any) -> None:
        if self._rendering or item is None:
            return
        key = item.data(QtCore.Qt.UserRole)
        if key is None:
            return
        table = self.sender()
        try:
            if table is self._part_table:
                self._apply_component(item, key)
            elif table is self._feature_table:
                self._apply_feature(item, key)
            elif table is self._parameter_table:
                self._apply_parameter(item, key)
            elif table is self._metadata_table:
                self._apply_metadata(item, key)
            elif table is self._drawing_table:
                self._apply_drawing(item, key)
            elif table is self._drawing_sheet_table:
                self._apply_drawing_sheet(item, key)
        except CapturePanelError as exc:
            _console_error(str(exc))
            self._status.setText(str(exc))
            self._status.setStyleSheet("color: #b00020;")
        self._render()

    def _apply_component(self, item: Any, key: str) -> None:
        state = self._session.state
        if item.column() == 0:
            state.set_component_included(key, item.checkState() == QtCore.Qt.Checked)
        elif item.column() == _NAME_COLUMN[CaptureTab.PARTS]:
            state.set_component_name(key, item.text())
        elif item.column() == 5:
            state.set_component_display_name(key, item.text() or None)

    def _apply_feature(self, item: Any, key: str) -> None:
        state = self._session.state
        if item.column() == 0:
            state.set_feature_included(key, item.checkState() == QtCore.Qt.Checked)
        elif item.column() == _NAME_COLUMN[CaptureTab.FEATURES]:
            state.set_feature_name(key, item.text())

    def _apply_parameter(self, item: Any, key: str) -> None:
        state = self._session.state
        if item.column() == 0:
            state.set_parameter_included(key, item.checkState() == QtCore.Qt.Checked)
        elif item.column() == _NAME_COLUMN[CaptureTab.PARAMETERS]:
            state.set_parameter_name(key, item.text())

    def _apply_metadata(self, item: Any, key: str) -> None:
        state = self._session.state
        if item.column() == 0:
            state.set_metadata_included(key, item.checkState() == QtCore.Qt.Checked)
        elif item.column() == 5:
            state.set_metadata_display_name(key, item.text())

    def _apply_drawing(self, item: Any, key: str) -> None:
        state = self._session.state
        if item.column() == 1:
            state.set_drawing_name(key, item.text())
        elif item.column() == 2:
            state.set_drawing_display_name(key, item.text())

    def _apply_drawing_sheet(self, item: Any, key: str) -> None:
        state = self._session.state
        if item.column() == 0:
            state.set_drawing_sheet_included(
                key, item.checkState() == QtCore.Qt.Checked
            )
        elif item.column() == 4:
            state.set_drawing_sheet_name(key, item.text())
        elif item.column() == 5:
            try:
                order = int(item.text())
            except ValueError as exc:
                raise CapturePanelError(
                    "drawing sheet order must be an integer"
                ) from exc
            state.set_drawing_sheet_order(key, order)
        elif item.column() == 6:
            state.set_drawing_sheet_display_name(key, item.text() or None)

    def _on_drawing_group_changed(self, combo: Any, native_ref: str) -> None:
        if self._rendering:
            return
        drawing_key = combo.currentData()
        if not drawing_key:
            return
        try:
            self._session.state.set_drawing_sheet_group(native_ref, drawing_key)
        except CapturePanelError as exc:
            _console_error(str(exc))
            self._status.setText(str(exc))
            self._status.setStyleSheet("color: #b00020;")
        self._render()

    def _on_add_drawing(self) -> None:
        self._session.state.add_drawing_group()
        self._render()

    def _on_remove_drawing(self) -> None:
        row = self._drawing_table.currentRow()
        if row < 0:
            return
        item = self._drawing_table.item(row, 0)
        if item is None:
            return
        drawing_key = item.data(QtCore.Qt.UserRole)
        if not drawing_key:
            return
        try:
            self._session.state.remove_drawing_group(str(drawing_key))
        except CapturePanelError as exc:
            _console_error(str(exc))
            self._status.setText(str(exc))
            self._status.setStyleSheet("color: #b00020;")
        self._render()

    def _on_capture_id_changed(self) -> None:
        options = dataclasses.replace(
            self._session.state.options,
            capture_id=self._capture_id.text().strip(),
        )
        self._session.state.set_options(options)

    def _on_review(self) -> None:
        snapshot = self._session.state.snapshot()
        if not snapshot.can_review:
            QtWidgets.QMessageBox.warning(
                self,
                "Parametron Capture",
                "Fix the reported problems before reviewing.",
            )
            return

        try:
            plan = self._session.preview()
        except CaptureDriftError as exc:
            lines = "\n".join(f"- {entry.to_mapping()}" for entry in exc.entries)
            QtWidgets.QMessageBox.critical(
                self,
                "Capture drift detected",
                "Retained capture no longer matches native evidence. Rebinding "
                "or review is required.\n\n" + lines,
            )
            return
        except (
            CaptureError,
            CaptureOrchestrationError,
            SemanticMapError,
            OSError,
        ) as exc:
            QtWidgets.QMessageBox.critical(self, "Capture preview failed", str(exc))
            return

        detail = self._format_plan(plan)
        confirm = False
        if plan.requires_confirmation:
            answer = QtWidgets.QMessageBox.question(
                self,
                "Replace existing capture outputs?",
                detail + "\n\nThis replaces existing files. Continue?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No,
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return
            confirm = True
        else:
            answer = QtWidgets.QMessageBox.question(
                self,
                "Write capture outputs?",
                detail + "\n\nWrite these files?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.Yes,
            )
            if answer != QtWidgets.QMessageBox.Yes:
                return

        try:
            summary = self._session.commit(confirm_replace=confirm)
        except (CaptureWriteError, OSError) as exc:
            QtWidgets.QMessageBox.critical(self, "Capture write failed", str(exc))
            return
        except (CaptureError, CaptureOrchestrationError, SemanticMapError) as exc:
            QtWidgets.QMessageBox.critical(self, "Capture write failed", str(exc))
            return

        _console_message(
            f"capture status={summary.capture_status} "
            f"semantic status={summary.semantic_status}"
        )
        QtWidgets.QMessageBox.information(
            self,
            "Parametron Capture",
            f"Capture written.\n\nprm.cad.json: {summary.capture_path}\n"
            f"prm.semantic-map.json: {summary.semantic_path}",
        )
        self._render()

    @staticmethod
    def _format_plan(plan: Any) -> str:
        lines = [
            f"capture: {plan.capture_status}",
            f"semantic map: {plan.semantic_status}",
        ]
        for entry in plan.capture_diff:
            lines.append(f"  {entry.change} {entry.path or '/'}")
        for entry in plan.semantic_plan.diff:
            lines.append(f"  {entry.change} {entry.path or '/'} (semantic map)")
        return "\n".join(lines)


__all__ = ["CapturePanel"]
