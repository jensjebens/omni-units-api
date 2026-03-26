"""Units Inspector window for Omniverse Kit.

A standalone panel showing the unit context and converted values for
the currently selected prim. Provides audit, correct, and bake actions.
"""

import omni.ui as ui
import omni.usd
from pxr import Usd, UsdGeom, Sdf

from omni.units_api._lib import (
    MetricsAPI, UnitsLens, MetricsAssembler,
    get_dimension, Dimension, DIMENSION_REGISTRY, conversion_factor,
)
from .property_widget import _unit_name_for_mpu, _si_unit_for_dimension, _format_value


WINDOW_TITLE = "Units Inspector"


class UnitsInspectorWindow:
    """Standalone window showing unit context for selected prims."""

    def __init__(self):
        self._window = ui.Window(WINDOW_TITLE, width=420, height=600)
        self._stage_sub = None
        self._selection_sub = None
        self._build_ui()
        self._subscribe()

    def _subscribe(self):
        """Subscribe to selection changes."""
        usd_context = omni.usd.get_context()
        if usd_context:
            self._selection_sub = (
                usd_context.get_stage_event_stream().create_subscription_to_pop(
                    self._on_stage_event
                )
            )

    def _on_stage_event(self, event):
        """Refresh on selection change."""
        if event.type == int(omni.usd.StageEventType.SELECTION_CHANGED):
            self._refresh()

    def _get_selected_prim(self):
        """Get the first selected prim."""
        usd_context = omni.usd.get_context()
        if not usd_context:
            return None
        stage = usd_context.get_stage()
        if not stage:
            return None
        selection = usd_context.get_selection()
        paths = selection.get_selected_prim_paths()
        if not paths:
            return None
        prim = stage.GetPrimAtPath(paths[0])
        return prim if prim.IsValid() else None

    def _build_ui(self):
        """Build the window layout."""
        with self._window.frame:
            with ui.ScrollingFrame():
                self._root_frame = ui.VStack(spacing=8, height=0)
                with self._root_frame:
                    ui.Label("Select a prim to inspect units",
                             style={"color": 0xFF888888, "font_size": 14},
                             alignment=ui.Alignment.CENTER,
                             height=40)

    def _refresh(self):
        """Rebuild the UI for the current selection."""
        prim = self._get_selected_prim()

        # Clear and rebuild
        self._root_frame.clear()
        with self._root_frame:
            if prim is None:
                ui.Label("No prim selected",
                         style={"color": 0xFF888888},
                         alignment=ui.Alignment.CENTER, height=40)
                return

            self._build_header(prim)
            ui.Spacer(height=4)
            self._build_attributes_table(prim)
            ui.Spacer(height=8)
            self._build_actions(prim)

    def _build_header(self, prim):
        """Show prim path and effective metrics."""
        metrics = MetricsAPI.get_effective_metrics(prim)
        mpu = metrics["metersPerUnit"]
        up = metrics["upAxis"]
        kpu = metrics["kilogramsPerUnit"]
        unit_name = _unit_name_for_mpu(mpu)
        has_own = MetricsAPI.has_metrics(prim)

        with ui.CollapsableFrame("Unit Context", collapsed=False):
            with ui.VStack(spacing=4):
                ui.Label(f"Prim: {prim.GetPath()}",
                         style={"font_size": 13})

                with ui.HStack(spacing=8):
                    ui.Label(f"Units: {unit_name} ({mpu} m/unit)",
                             style={"font_size": 12})
                    ui.Label(f"Up: {up}", style={"font_size": 12})
                    ui.Label(f"Mass: {kpu} kg/unit", style={"font_size": 12})

                if has_own:
                    ui.Label("✓ MetricsAPI applied on this prim",
                             style={"color": 0xFF88BB88, "font_size": 11})
                else:
                    ui.Label("↑ Inherited from ancestor or stage metadata",
                             style={"color": 0xFFBBBB88, "font_size": 11})

    def _build_attributes_table(self, prim):
        """Show all unit-bearing attributes with conversions."""
        metrics = MetricsAPI.get_effective_metrics(prim)
        source_mpu = metrics["metersPerUnit"]
        source_kpu = metrics["kilogramsPerUnit"]
        native_unit = _unit_name_for_mpu(source_mpu)

        attrs_with_units = []
        for attr in prim.GetAttributes():
            if not attr.HasAuthoredValue():
                continue
            dim = get_dimension(attr.GetName())
            if dim is None or dim == Dimension(0, 0, 0):
                continue
            attrs_with_units.append((attr, dim))

        if not attrs_with_units:
            with ui.CollapsableFrame("Unit-Bearing Attributes", collapsed=False):
                ui.Label("No unit-bearing attributes with authored values",
                         style={"color": 0xFF888888, "font_size": 11})
            return

        with ui.CollapsableFrame(
            f"Unit-Bearing Attributes ({len(attrs_with_units)})", collapsed=False
        ):
            with ui.VStack(spacing=2):
                # Header row
                with ui.HStack(height=20):
                    ui.Label("Attribute", width=ui.Fraction(2),
                             style={"font_size": 11, "color": 0xFF888888})
                    ui.Label(f"Value ({native_unit})", width=ui.Fraction(2),
                             style={"font_size": 11, "color": 0xFF888888})
                    ui.Label("→ SI", width=ui.Fraction(2),
                             style={"font_size": 11, "color": 0xFF888888})
                    ui.Label("Dim", width=60,
                             style={"font_size": 11, "color": 0xFF888888})

                ui.Line(style={"color": 0xFF444444}, height=1)

                for attr, dim in attrs_with_units:
                    val = attr.Get()
                    if val is None:
                        continue

                    si_unit = _si_unit_for_dimension(dim)
                    factor = conversion_factor(source_mpu, 1.0, dim, source_kpu, 1.0)

                    if isinstance(val, (int, float)):
                        converted_val = val * factor
                    else:
                        try:
                            converted_val = UnitsLens.get_attr(attr, target_mpu=1.0)
                        except Exception:
                            converted_val = val

                    dim_str = ""
                    if dim.L != 0:
                        dim_str += f"L{dim.L:+d}"
                    if dim.M != 0:
                        dim_str += f"M{dim.M:+d}"
                    if dim.T != 0:
                        dim_str += f"T{dim.T:+d}"

                    with ui.HStack(height=18):
                        ui.Label(attr.GetName(), width=ui.Fraction(2),
                                 style={"font_size": 12})
                        ui.Label(_format_value(val), width=ui.Fraction(2),
                                 style={"font_size": 12})
                        ui.Label(
                            f"{_format_value(converted_val)} {si_unit}",
                            width=ui.Fraction(2),
                            style={"font_size": 12, "color": 0xFF88BB88},
                        )
                        ui.Label(dim_str, width=60,
                                 style={"font_size": 11, "color": 0xFFAAAA88})

    def _build_actions(self, prim):
        """Action buttons: audit, correct, bake."""
        stage = prim.GetStage()

        with ui.CollapsableFrame("Actions", collapsed=False):
            with ui.VStack(spacing=4):
                def _audit():
                    mismatches = MetricsAssembler.audit_stage(stage)
                    if mismatches:
                        for m in mismatches:
                            print(f"[Units Audit] {m['prim_path']}: "
                                  f"source={m['source_mpu']} target={m['target_mpu']} "
                                  f"scale={m['scale']:.6f}")
                    else:
                        print("[Units Audit] No mismatches found")

                def _correct():
                    corrections = MetricsAssembler.correct_stage(stage)
                    print(f"[Units Correct] Applied {len(corrections)} corrections")
                    self._refresh()

                def _bake():
                    result = MetricsAssembler.bake_to_units(stage, target_mpu=1.0)
                    print(f"[Units Bake] Converted {result['attrs_converted']} attrs, "
                          f"{result['time_samples_converted']} time samples")
                    self._refresh()

                ui.Button("Audit Stage", clicked_fn=_audit, height=28)
                ui.Button("Correct Stage (xformOps)", clicked_fn=_correct, height=28)
                ui.Button("Bake to Meters (overs)", clicked_fn=_bake, height=28)

    def destroy(self):
        """Clean up subscriptions."""
        self._selection_sub = None
        self._stage_sub = None
        if self._window:
            self._window.destroy()
            self._window = None
