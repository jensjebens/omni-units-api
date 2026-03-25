# omni-units-api

Omniverse Kit extension proving out the [Units API POC](https://github.com/jensjebens/OpenUSD/tree/jjebens/units-api-poc/extras/units_api) for OpenUSD.

Companion to the [Units & Scale proposal](https://github.com/jensjebens/OpenUSD-proposals/blob/jjebens/units-and-scale/proposals/units_and_scale/README.md).

## What This Is

A Kit extension (`omni.units_api`) that packages the Units API proof-of-concept library and validates it inside Omniverse — with real USD stages, real references, real physics, cameras, lights, and PointInstancers.

## Structure

```
source/extensions/omni.units_api/
  config/extension.toml          # Kit extension manifest
  omni/units_api/
    extension.py                 # IExt lifecycle
    _lib/                        # Vendored units_api POC library
      metrics_api.py             # Prim-level unit declarations
      dimensions.py              # Dimensional registry (L, M, T exponents)
      units_lens.py              # Unit-aware get/set for any attribute
      assembly.py                # Non-destructive corrective xformOps
      per_attribute.py           # Per-attribute unit annotations
  tests/
    test_omni_metrics_api.py     # Phase 1: Core validation
    test_omni_assembly.py        # Phase 2: Assembly correction
    test_omni_physics.py         # Phase 3: Physics attributes
    test_omni_cameras_lights.py  # Phase 4: Camera & light attributes
    test_omni_point_instancer.py # Phase 5: PointInstancer & animation
    test_omni_end_to_end.py      # Phase 6: End-to-end scenarios
```

## Test Coverage (24 tests across 6 phases)

| Phase | Tests | Domain |
|-------|-------|--------|
| 1 | MetricsAPI round-trip, inheritance, UnitsLens get/set | Core validation |
| 2 | Corrective xformOp, visual validation, audit, up-axis | Assembly correction |
| 3 | Density, gravity, velocity, mass, cross-reference | Physics attributes |
| 4 | focusDistance, clippingRange, focalLength, light dimensions | Camera & lights |
| 5 | PointInstancer positions/velocities, time samples, splines | Arrays & animation |
| 6 | Factory floor, physics readiness, custom attrs, overhead | End-to-end |

## Running

Requires [Kit App Template](https://github.com/NVIDIA-Omniverse/kit-app-template) environment.

```bash
# Clone into a KAT workspace
cp -r source/extensions/omni.units_api <kat-repo>/source/extensions/

# Build and test
cd <kat-repo>
./repo.sh build
./repo.sh test --ext omni.units_api
```

## Related

- [Units API POC](https://github.com/jensjebens/OpenUSD/tree/jjebens/units-api-poc/extras/units_api) — standalone Python library
- [Units & Scale proposal](https://github.com/jensjebens/OpenUSD-proposals/blob/jjebens/units-and-scale/proposals/units_and_scale/README.md) — OpenUSD proposal
- [MetricsAPI / Revise Layer Metadata (PR #45)](https://github.com/PixarAnimationStudios/OpenUSD-proposals/pull/45) — prim-level unit declarations

## License

Same as OpenUSD. See [LICENSE](LICENSE).
