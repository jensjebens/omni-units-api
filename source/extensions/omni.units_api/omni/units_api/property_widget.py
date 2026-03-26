"""Units-aware property widget for Omniverse Kit.

Extends the standard property panel to show unit annotations and
converted values for unit-bearing attributes. Inspired by Blender's
unit display in the properties panel.

When a prim has MetricsAPI applied (or is in a subtree with MetricsAPI),
unit-bearing attributes display:
  - The attribute label with a unit suffix: "focusDistance (m)"
  - The authored value with its native unit label
  - A secondary label showing the SI-converted value

This gives users immediate visibility into what units they're working in,
without needing to mentally convert between mm/cm/m.
"""

import omni.ui as ui
from pxr import Usd, Sdf

from omni.units_api._lib import (
    MetricsAPI, UnitsLens, get_dimension, Dimension,
    DIMENSION_REGISTRY, conversion_factor,
)

# ---------------------------------------------------------------------------
# Unit display names
# ---------------------------------------------------------------------------

_MPU_TO_UNIT_NAME = {
    0.001: "mm",
    0.01: "cm",
    0.0254: "in",
    0.1: "dm",
    0.3048: "ft",
    1.0: "m",
    1000.0: "km",
}

_DIMENSION_TO_SI_UNIT = {
    (1, 0, 0): "m",           # length
    (-3, 1, 0): "kg/m³",      # density
    (1, 0, -1): "m/s",        # velocity
    (1, 0, -2): "m/s²",       # acceleration
    (0, 1, 0): "kg",          # mass
    (3, 0, -1): "m³/s",       # volumetric flow
    (0, 0, 0): "",            # unitless
}


def _unit_name_for_mpu(mpu: float) -> str:
    """Get human-readable unit name for a metersPerUnit value."""
    for threshold_mpu, name in sorted(_MPU_TO_UNIT_NAME.items()):
        if abs(mpu - threshold_mpu) < threshold_mpu * 0.01:
            return name
    return f"{mpu} m/unit"


def _si_unit_for_dimension(dim: Dimension) -> str:
    """Get SI unit label for a dimension."""
    key = (dim.L, dim.M, dim.T)
    return _DIMENSION_TO_SI_UNIT.get(key, "")


def _format_value(val, precision=4) -> str:
    """Format a value for display."""
    if isinstance(val, float):
        if abs(val) < 0.001 or abs(val) > 1e6:
            return f"{val:.{precision}e}"
        return f"{val:.{precision}f}"
    if hasattr(val, '__len__') and len(val) <= 4:
        parts = [_format_value(v, precision=2) for v in val]
        return f"({', '.join(parts)})"
    return str(val)


# ---------------------------------------------------------------------------
# Unit-aware property label builder
# ---------------------------------------------------------------------------

def build_unit_aware_float(
    stage,
    attr_name,
    type_name,
    metadata,
    prim_paths,
    additional_label_kwargs=None,
    additional_widget_kwargs=None,
):
    """Custom build function for unit-bearing float attributes.

    Shows the standard float editor plus a unit annotation label.
    """
    from omni.kit.property.usd import UsdPropertiesWidgetBuilder

    dim = get_dimension(attr_name)
    if dim is None or dim == Dimension(0, 0, 0):
        # Not unit-bearing — fall back to default builder
        return UsdPropertiesWidgetBuilder.floating_point_builder(
            stage, attr_name, type_name, metadata, prim_paths,
            additional_label_kwargs, additional_widget_kwargs,
        )

    si_unit = _si_unit_for_dimension(dim)

    # Get the prim's effective metrics
    prim = stage.GetPrimAtPath(prim_paths[0]) if prim_paths else None
    if prim and prim.IsValid():
        metrics = MetricsAPI.get_effective_metrics(prim)
        source_mpu = metrics["metersPerUnit"]
        source_kpu = metrics["kilogramsPerUnit"]
        native_unit = _unit_name_for_mpu(source_mpu)
    else:
        source_mpu = 1.0
        source_kpu = 1.0
        native_unit = "m"

    # Modify label to include unit suffix
    if additional_label_kwargs is None:
        additional_label_kwargs = {}

    # Build the standard float widget with unit-enhanced label
    label_suffix = f" ({native_unit})" if native_unit != "m" else ""
    original_label_kwargs = dict(additional_label_kwargs)

    with ui.HStack(spacing=4):
        # Standard float editor (takes most of the width)
        with ui.HStack(width=ui.Fraction(3)):
            model = UsdPropertiesWidgetBuilder.floating_point_builder(
                stage, attr_name, type_name, metadata, prim_paths,
                additional_label_kwargs, additional_widget_kwargs,
            )

        # Unit annotation column
        with ui.VStack(width=80):
            if native_unit != "m" and si_unit:
                # Show converted value in SI
                attr = prim.GetAttribute(attr_name) if prim else None
                if attr and attr.IsValid() and attr.HasAuthoredValue():
                    val = attr.Get()
                    if val is not None:
                        factor = conversion_factor(
                            source_mpu, 1.0, dim, source_kpu, 1.0
                        )
                        converted = val * factor if isinstance(val, (int, float)) else val
                        ui.Label(
                            f"→ {_format_value(converted)} {si_unit}",
                            name="units_converted",
                            style={"color": 0xFF88BB88, "font_size": 11},
                            alignment=ui.Alignment.RIGHT_CENTER,
                        )
                    else:
                        ui.Label(
                            si_unit,
                            name="units_label",
                            style={"color": 0xFF888888, "font_size": 11},
                            alignment=ui.Alignment.RIGHT_CENTER,
                        )
                else:
                    ui.Label(
                        si_unit,
                        name="units_label",
                        style={"color": 0xFF888888, "font_size": 11},
                        alignment=ui.Alignment.RIGHT_CENTER,
                    )
            elif si_unit:
                ui.Label(
                    si_unit,
                    name="units_label",
                    style={"color": 0xFF888888, "font_size": 11},
                    alignment=ui.Alignment.RIGHT_CENTER,
                )

    return model


def build_unit_aware_vec3(
    stage,
    attr_name,
    type_name,
    metadata,
    prim_paths,
    additional_label_kwargs=None,
    additional_widget_kwargs=None,
):
    """Custom build function for unit-bearing vec3 attributes."""
    from omni.kit.property.usd import UsdPropertiesWidgetBuilder

    dim = get_dimension(attr_name)
    if dim is None or dim == Dimension(0, 0, 0):
        return UsdPropertiesWidgetBuilder.vec_builder(
            stage, attr_name, type_name, metadata, prim_paths,
            additional_label_kwargs, additional_widget_kwargs,
        )

    si_unit = _si_unit_for_dimension(dim)

    prim = stage.GetPrimAtPath(prim_paths[0]) if prim_paths else None
    if prim and prim.IsValid():
        metrics = MetricsAPI.get_effective_metrics(prim)
        source_mpu = metrics["metersPerUnit"]
        source_kpu = metrics["kilogramsPerUnit"]
        native_unit = _unit_name_for_mpu(source_mpu)
    else:
        source_mpu = 1.0
        source_kpu = 1.0
        native_unit = "m"

    with ui.HStack(spacing=4):
        with ui.HStack(width=ui.Fraction(3)):
            model = UsdPropertiesWidgetBuilder.vec_builder(
                stage, attr_name, type_name, metadata, prim_paths,
                additional_label_kwargs, additional_widget_kwargs,
            )

        with ui.VStack(width=80):
            if native_unit != "m" and si_unit:
                attr = prim.GetAttribute(attr_name) if prim else None
                if attr and attr.IsValid() and attr.HasAuthoredValue():
                    converted = UnitsLens.get_attr(attr, target_mpu=1.0)
                    if converted is not None:
                        ui.Label(
                            f"→ {_format_value(converted)} {si_unit}",
                            name="units_converted",
                            style={"color": 0xFF88BB88, "font_size": 11},
                            alignment=ui.Alignment.RIGHT_CENTER,
                        )
            elif si_unit:
                ui.Label(
                    si_unit,
                    name="units_label",
                    style={"color": 0xFF888888, "font_size": 11},
                    alignment=ui.Alignment.RIGHT_CENTER,
                )

    return model
