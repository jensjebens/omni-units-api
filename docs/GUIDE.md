# Units API for Omniverse Kit

A Kit extension for unit-aware reading and authoring of USD attribute values.

## What It Does

When you compose USD assets from different sources — CAD parts in
millimeters, robot arms in centimeters, buildings in meters — the
authored numbers disagree. `translate = 100` means 100 mm on the bolt
but 100 m on the building.

The Units API gives you two things:

1. **Read any attribute in the units you want.** Ask for a density
   value in kg/m³ regardless of whether the prim is in millimeters.
2. **Write values in the units you think in.** Set a position in meters
   and have it stored correctly on a centimeter-scale prim.

It handles transforms, physics attributes (density, gravity, velocity,
mass), camera attributes (focus distance, clipping range), light
dimensions, PointInstancer arrays, animation curves, and custom
pipeline attributes.

## Quick Start

```python
from omni.units_api._lib import MetricsAPI, UnitsLens, MetricsAssembler

# --- Declare units on a subtree ---
MetricsAPI.apply(bolt_prim, meters_per_unit=0.001)   # "everything under /Bolt is in mm"

# --- Read a value in meters ---
pos = UnitsLens.get_attr(translate_attr, target_mpu=1.0)
# translate = (10, 0, 0) in mm → returns (0.01, 0, 0) in meters

# --- Read a derived quantity in meters ---
density = UnitsLens.get_attr(density_attr, target_mpu=1.0)
# 7.8e-6 kg/mm³ → 7800 kg/m³  (L⁻³·M¹ exponent applied automatically)

# --- Write a value, thinking in meters ---
UnitsLens.set_translate(shaft_prim, Gf.Vec3d(0.05, 0, 0), source_mpu=1.0)
# Prim is in mm → stores (50, 0, 0)

# --- Fix transforms at reference boundaries ---
corrections = MetricsAssembler.correct_stage(stage)
# Adds non-destructive xformOp:scale:metricsCorrection where needed

# --- Dry-run audit ---
mismatches = MetricsAssembler.audit_stage(stage)
# Reports what's wrong without touching the stage
```

## How It Works

Three layers, each solving a different part of the problem:

### 1. MetricsAPI — "What unit system is this subtree in?"

Stores `metersPerUnit`, `upAxis`, and `kilogramsPerUnit` as
`customData` on a prim. Inherits down the hierarchy: annotate the
root of a referenced asset, and every descendant resolves the correct
unit context via ancestor walk. Falls back to stage-level layer
metadata, then to USD defaults (cm, Y-up, 1 kg).

```python
MetricsAPI.apply(prim, meters_per_unit=0.001, up_axis="Z")
MetricsAPI.get_effective_metrics(child_prim)
# → {"metersPerUnit": 0.001, "upAxis": "Z", "kilogramsPerUnit": 1.0}
```

This mirrors the design direction of the
[MetricsAPI proposal (PR #45)](https://github.com/PixarAnimationStudios/OpenUSD-proposals/pull/45)
— prim-level unit declarations that survive flattening and are
discoverable per subtree.

### 2. Dimensional Registry — "How does this attribute scale?"

A mapping from attribute names to dimensional exponents:

| Attribute | Dimension | Exponents |
|-----------|-----------|-----------|
| `xformOp:translate`, `points`, `extent` | length | L¹ |
| `physics:velocity` | velocity | L¹·T⁻¹ |
| `physics:density` | density | L⁻³·M¹ |
| `physics:gravityMagnitude` | acceleration | L¹·T⁻² |
| `physics:mass` | mass | M¹ |
| `focusDistance`, `clippingRange` | length | L¹ |
| `inputs:width`, `inputs:height`, `inputs:radius` | length | L¹ |
| `focalLength`, `horizontalAperture` | — | *Not in registry* (fixed mm per schema) |

The registry is schema-invariant: `physics:density` is *always*
M¹·L⁻³, on every prim, in every stage. These are facts about the
schema definition, not the data.

**Why not read this from the schema?** Because USD schemas don't
declare dimensional exponents as structured metadata — yet.
UsdPhysics declares them as doc strings (`Units: mass/distance/distance/distance`),
but no tool can consume that programmatically. The registry is a
bridge until schemas self-describe their units.

### 3. Per-Attribute Metadata — "What about custom attributes?"

For attributes the registry doesn't know about (your pipeline's
custom `myPipeline:flowRate`), annotate them directly:

```python
from omni.units_api._lib import PerAttributeUnits, Dimension

PerAttributeUnits.annotate(flow_attr, Dimension(L=3, T=-1), meters_per_unit=0.01)
# Now UnitsLens converts it automatically
flow = UnitsLens.get_attr(flow_attr, target_mpu=1.0)
```

## Comparison with Omniverse Metrics Assembler

The existing Metrics Assembler in Omniverse and this Units API solve
**different parts** of the same problem. They complement each other.

### What Metrics Assembler does

Metrics Assembler detects `metersPerUnit` mismatches at reference
boundaries and authors **corrective `xformOps`** — a scale (and
optionally rotation for up-axis) on the referencing prim. It also
handles a subset of physics attributes via registered rules where
the physics schema provides unit exponent annotations. Corrections
are written to a dedicated sublayer (identified by the `metrics:`
prefix), which Kit's Layer widget hides by default to keep the layer
stack clean.

**Strengths:**
- Proven in production at factory scale
- Non-destructive (corrections live in a separate layer)
- Runs at assembly time — fixes are baked before interactive use
- Physics attribute rules are schema-driven (new physics attributes
  can be handled without code changes)

**Limitations:**
- Operates only on references and payloads (not sublayers)
- Requires deep hierarchy traversal (measured at 80+ seconds on
  production stages)
- Does not cover camera spatial attributes (focus distance, clipping
  range), light spatial attributes (width, radius), material spatial
  properties (displacement, SSS distances), or stage-level physics
  constants
- Transform-only correction doesn't help you *read* a density value
  in the right units — it fixes where things appear, not what the
  numbers mean

### What Units API adds

| Capability | Metrics Assembler | Units API |
|-----------|:-:|:-:|
| Corrective xformOps at reference boundaries | ✅ | ✅ |
| Up-axis correction | ✅ | ✅ |
| Physics attribute correction (schema-driven) | ✅ (subset) | ✅ (registry) |
| Read any attribute in target units | — | ✅ |
| Write values in source units | — | ✅ |
| Camera attributes (focusDistance, clippingRange) | — | ✅ |
| Light spatial attributes (width, height, radius) | — | ✅ |
| PointInstancer arrays (positions, velocities) | — | ✅ |
| Animation curves / bezier splines | — | ✅ |
| Custom pipeline attributes | — | ✅ |
| Prim-level unit declarations (MetricsAPI) | Layer metadata | Prim customData |
| Dry-run audit | — | ✅ |

### How they work together

The recommended workflow is:

1. **MetricsAPI.apply()** on asset roots when ingesting content —
   declare the unit context.
2. **MetricsAssembler.correct_stage()** at assembly time — fix
   transforms at reference boundaries. (This is the same concept as
   the existing Metrics Assembler; the Units API includes its own
   implementation.)
3. **UnitsLens.get_attr()** at read time — for any attribute that
   isn't a transform (density, gravity, velocity, camera, lights,
   custom attributes), read it in the units you need.

Assembly correction handles *where things are*. UnitsLens handles
*what the numbers mean*.

### Where it overlaps

Both can author corrective `xformOps` at reference boundaries. The
Units API's `MetricsAssembler` is a clean-room implementation that
follows the same pattern. If you're already using the Omniverse
Metrics Assembler for transform correction, keep using it — the
Units API's value is in the **lens** (attribute-level conversion) and
the **MetricsAPI** (prim-level unit declarations), not in replacing
your existing assembly pipeline.

## What It Doesn't Do

- **Render-time correction.** This is a data-layer API. It doesn't
  patch the render delegate or viewport.
- **Automatic conversion on stage open.** You call the API explicitly.
  There is no implicit magic.
- **Sublayer unit reconciliation.** Sublayers compose directly into
  the root namespace with no natural boundary for correction. This is
  an open problem in USD itself.
- **Historical/versioned unit tracking.** It tells you what the units
  are *now*, not what they were before someone changed them.

## API Reference

### MetricsAPI

```python
MetricsAPI.apply(prim, meters_per_unit, up_axis, kilograms_per_unit)
MetricsAPI.has_metrics(prim) → bool
MetricsAPI.get_metrics(prim) → dict            # direct, not inherited
MetricsAPI.get_effective_metrics(prim) → dict   # inherited + fallback
MetricsAPI.get_meters_per_unit(prim) → float
MetricsAPI.get_up_axis(prim) → str
MetricsAPI.get_kilograms_per_unit(prim) → float
```

### UnitsLens

```python
# Scalar / vector / array attributes
UnitsLens.get_attr(attr, target_mpu=1.0, target_kpu=1.0, time=None)
UnitsLens.set_attr(attr, value, source_mpu=1.0, source_kpu=1.0, time=None)

# Transforms
UnitsLens.get_translate(prim, target_mpu=1.0, time=None) → Gf.Vec3d
UnitsLens.set_translate(prim, value, source_mpu=1.0, time=None)
UnitsLens.get_world_position(prim, target_mpu=1.0, time=None) → Gf.Vec3d
UnitsLens.get_local_transform(prim, target_mpu=1.0, time=None) → Gf.Matrix4d

# Time samples (bulk — conversion factor resolved once)
UnitsLens.get_time_samples(attr, target_mpu=1.0) → [(time, value), ...]

# Animation curves (bezier — values + tangent slopes scale, widths preserved)
UnitsLens.get_spline(attr, target_mpu=1.0) → Ts.Spline

# Convenience
UnitsLens.get_in_meters(attr, time=None)
UnitsLens.get_conversion_info(attr) → dict
UnitsLens.clear_cache()
```

### MetricsAssembler

```python
MetricsAssembler.audit_stage(stage) → [dict, ...]       # dry run
MetricsAssembler.correct_stage(stage) → [dict, ...]     # apply corrections
MetricsAssembler.correct_reference_boundary(prim) → dict | None
```

### PerAttributeUnits

```python
PerAttributeUnits.annotate(attr, Dimension(L=3, T=-1), meters_per_unit=1.0)
PerAttributeUnits.get_attr(attr, target_mpu=1.0, time=None)
PerAttributeUnits.has_annotation(attr) → bool
```

## Performance

| Operation | Time |
|-----------|------|
| Scalar get_attr (cached metrics) | ~8 µs |
| 100k Vec3f array (numpy path) | ~1.3 ms |
| 240-frame time samples (bulk) | ~1.1 ms |
| Bezier spline conversion | <0.1 ms |

## Related

- [Units & Scale proposal](https://github.com/jensjebens/OpenUSD-proposals/blob/jjebens/units-and-scale/proposals/units_and_scale/README.md)
- [Units API POC (standalone)](https://github.com/jensjebens/OpenUSD/tree/jjebens/units-api-poc/extras/units_api)
- [MetricsAPI proposal (PR #45)](https://github.com/PixarAnimationStudios/OpenUSD-proposals/pull/45)
