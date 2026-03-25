# Omniverse Integration Plan: Units API POC in Kit App Template

**Status:** In Progress
**Repo:** `jensjebens/omni-units-api`
**Last Updated:** 2026-03-25

## Overview

A Kit extension (`omni.units_api`) that packages the Units API POC library and proves it works inside Omniverse — with real USD stages, real references, real physics, real cameras, real lights.

## Why KAT (Kit App Template)

- Clean scaffolding for a Kit extension with tests
- Ships with Kit SDK, RTX renderer, Physics, and all the USD schemas we need
- `repo.sh test` gives us headless Kit test execution — no GPU viewport required for the unit logic tests
- Can optionally add a UI panel for interactive demo later

## Architecture

```
kit-app-template/
  source/extensions/
    omni.units_api/               ← our extension
      config/extension.toml
      omni/units_api/
        __init__.py               ← extension startup (registers the library)
        extension.py              ← omni.ext.IExt lifecycle
        _lib/                     ← vendored units_api source (or git submodule)
          metrics_api.py
          dimensions.py
          units_lens.py
          assembly.py
          per_attribute.py
      tests/
        __init__.py
        test_omni_metrics_api.py
        test_omni_units_lens.py
        test_omni_assembly.py
        test_omni_physics.py
        test_omni_cameras_lights.py
        test_omni_point_instancer.py
        test_omni_materials.py
        test_omni_end_to_end.py
      data/test_stages/           ← pre-authored USD test stages
```

## Test Plan

### Phase 1: Core Validation _(does it work in Kit at all?)_

| # | Test | What it proves | Status |
|---|------|---------------|--------|
| 1.1 | **MetricsAPI round-trip in Kit** — Apply metrics via `MetricsAPI.apply()`, save stage, reload, verify `get_effective_metrics()` | customData survives Kit's save/load cycle | ⬜ |
| 1.2 | **MetricsAPI inheritance through references** — Reference a mm-scale asset into a meter-scale stage, verify ancestor walk resolves correctly through Kit's composition | POC's ancestor walk works with Kit's stage composition, not just programmatic stages | ⬜ |
| 1.3 | **UnitsLens get/set in Kit runtime** — Create prims via `omni.usd`, set values via UnitsLens, read back via raw USD and verify conversion | No interference from Kit's stage management | ⬜ |

### Phase 2: Assembly Correction _(MetricsAssembler in Omniverse)_

| # | Test | What it proves | Status |
|---|------|---------------|--------|
| 2.1 | **Corrective xformOp on reference** — Add a mm-scale reference to a meter-stage, run `MetricsAssembler.correct_stage()`, verify corrective `xformOp:scale:metricsCorrection` appears | Assembly correction works with Kit's reference handling | ⬜ |
| 2.2 | **Visual validation** — After correction, verify world-space positions via `UsdGeom.XformCache` match expected meter-scale values | Not just the op exists, but it produces correct transforms | ⬜ |
| 2.3 | **Audit without correction** — `audit_stage()` detects mismatches but doesn't modify the stage | Safe dry-run in a Kit context | ⬜ |
| 2.4 | **Up-axis correction** — Mix Y-up and Z-up assets, verify corrective rotation | Y↔Z correction in Kit's coordinate system | ⬜ |

### Phase 3: Physics Attributes _(the hard part)_

| # | Test | What it proves | Status |
|---|------|---------------|--------|
| 3.1 | **Density conversion** — Author `physics:density` on a mm-scale prim (steel = 7800 kg/m³ stored as 7.8e-6 kg/mm³), read via UnitsLens with `target_mpu=1.0`, verify 7800 | L⁻³·M¹ exponent works for real physics data | ⬜ |
| 3.2 | **Gravity magnitude** — Stage with `physics:gravityMagnitude = 9810` (mm/s²), read in meters via UnitsLens, verify 9.81 | L¹·T⁻² exponent | ⬜ |
| 3.3 | **Velocity** — `physics:velocity` on a mm-scale rigid body, verify correct m/s conversion | L¹·T⁻¹ exponent | ⬜ |
| 3.4 | **Mass passthrough** — `physics:mass` should not scale with length changes (M¹ only, no L component) | Mass is independent of metersPerUnit | ⬜ |
| 3.5 | **Cross-reference physics** — mm-scale rigid body referenced into m-scale stage, assembly correction + UnitsLens for derived quantities, verify both transforms and physics values are correct simultaneously | The full stack: assembly + lens compose correctly | ⬜ |

### Phase 4: Camera & Light Attributes

| # | Test | What it proves | Status |
|---|------|---------------|--------|
| 4.1 | **focusDistance conversion** — Camera on a cm-scale prim, read in meters | L¹ scene-unit camera attribute | ⬜ |
| 4.2 | **clippingRange conversion** — Near/far planes scale correctly | L¹ scene-unit camera attribute | ⬜ |
| 4.3 | **focalLength passthrough** — Should NOT scale (fixed mm per schema) | Registry correctly excludes fixed-unit attributes | ⬜ |
| 4.4 | **Light spatial dimensions** — `inputs:width`, `inputs:height`, `inputs:radius` on area/sphere lights | L¹ light attributes | ⬜ |

### Phase 5: PointInstancer & Animation

| # | Test | What it proves | Status |
|---|------|---------------|--------|
| 5.1 | **PointInstancer positions** — 1000+ instances on a cm-scale instancer, bulk read in meters | Array performance + correctness in Kit | ⬜ |
| 5.2 | **PointInstancer velocities** — L¹·T⁻¹ on instancer velocities array | Derived quantity on arrays | ⬜ |
| 5.3 | **Time-sampled translation** — Animated translate, bulk `get_time_samples()`, verify all frames convert | Animation + units | ⬜ |
| 5.4 | **Bezier spline conversion** — Animated focusDistance with bezier interpolation, verify values AND tangent slopes scale correctly | The spline finding from the POC | ⬜ |

### Phase 6: End-to-End Scenarios

| # | Test | What it proves | Status |
|---|------|---------------|--------|
| 6.1 | **Factory floor assembly** — Stage at 1.0 mpu, reference CAD bolt (mm), robot arm (cm), building shell (m). Run full audit → correct → verify all world positions in meters | Real-world multi-source scenario | ⬜ |
| 6.2 | **Physics simulation readiness** — After assembly correction + UnitsLens reads, verify gravity, density, velocity, mass are all self-consistent in meters | Simulation wouldn't explode | ⬜ |
| 6.3 | **Per-attribute annotation for custom attrs** — Add `myPipeline:flowRate` with L³·T⁻¹ annotation, verify UnitsLens converts it | Escape hatch works in Kit | ⬜ |
| 6.4 | **Comparison: MetricsAPI vs per-attribute overhead** — Annotate a stage both ways, count customData entries, measure timing | Reproduces the 2-vs-66 finding in Omniverse | ⬜ |

## Pre-authored Test Stages

| Stage | Contents | Status |
|-------|----------|--------|
| `bolt_mm.usda` | Simple mesh + physics, `metersPerUnit = 0.001` | ⬜ |
| `robot_arm_cm.usda` | Articulated hierarchy + joint limits, `metersPerUnit = 0.01` | ⬜ |
| `building_m.usda` | Simple structure, `metersPerUnit = 1.0` | ⬜ |
| `factory_floor.usda` | Root stage referencing all three above | ⬜ |
| `camera_scene.usda` | Camera with focusDistance, clippingRange, focalLength | ⬜ |
| `instancer_scene.usda` | PointInstancer with 1000 instances + velocities | ⬜ |

## Execution Steps

1. ~~Save plan~~ ✅
2. Create GitHub repo `jensjebens/omni-units-api`
3. Clone KAT, scaffold the extension with `repo.sh template new` → Extension → Basic Python
4. Vendor the POC library into the extension (or symlink during dev)
5. Author test stages programmatically in test setup + pre-authored USD files for complex scenarios
6. Implement Phase 1 tests
7. Implement Phase 2 tests
8. Implement Phase 3 tests
9. Implement Phase 4 tests
10. Implement Phase 5 tests
11. Implement Phase 6 tests
12. Run headless via `repo.sh test`
13. Optional: Add a simple UI panel for interactive audit/correct

## Success Criteria

- All 24 tests pass in Kit headless
- Factory floor end-to-end produces correct world-space values for every domain (transforms, physics, cameras, lights)
- Performance on the instancer test matches the POC's 1.3ms benchmark
- The 2-vs-66 annotation overhead finding reproduces

## Findings Log

| Date | Finding | Impact |
|------|---------|--------|
| | | |
