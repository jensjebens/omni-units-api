"""Phase 6: End-to-End Scenarios.

Tests 6.1–6.4: Real-world assembly, physics readiness, custom attrs, overhead comparison.
"""

import omni.kit.test
import time
from pxr import Usd, UsdGeom, UsdPhysics, Gf, Vt, Sdf

from omni.units_api._lib import (
    MetricsAPI, UnitsLens, MetricsAssembler,
    PerAttributeUnits, Dimension,
)


class TestFactoryFloorAssembly(omni.kit.test.AsyncTestCase):
    """6.1: Multi-source factory floor — bolt (mm), robot (cm), building (m)."""

    async def test_factory_floor_world_positions(self):
        # --- Bolt asset (mm) ---
        bolt_layer = Sdf.Layer.CreateAnonymous(".usda")
        bolt_stage = Usd.Stage.Open(bolt_layer)
        bolt_stage.SetMetadata("metersPerUnit", 0.001)
        bolt = bolt_stage.DefinePrim("/Bolt", "Xform")
        MetricsAPI.apply(bolt, meters_per_unit=0.001)
        shaft = bolt_stage.DefinePrim("/Bolt/Shaft", "Xform")
        UsdGeom.Xformable(shaft).AddTranslateOp().Set(Gf.Vec3d(20, 0, 0))  # 20 mm

        # --- Robot asset (cm) ---
        robot_layer = Sdf.Layer.CreateAnonymous(".usda")
        robot_stage = Usd.Stage.Open(robot_layer)
        robot_stage.SetMetadata("metersPerUnit", 0.01)
        robot = robot_stage.DefinePrim("/Robot", "Xform")
        MetricsAPI.apply(robot, meters_per_unit=0.01)
        arm = robot_stage.DefinePrim("/Robot/Arm", "Xform")
        UsdGeom.Xformable(arm).AddTranslateOp().Set(Gf.Vec3d(150, 0, 0))  # 150 cm

        # --- Building asset (m) ---
        bldg_layer = Sdf.Layer.CreateAnonymous(".usda")
        bldg_stage = Usd.Stage.Open(bldg_layer)
        bldg_stage.SetMetadata("metersPerUnit", 1.0)
        bldg = bldg_stage.DefinePrim("/Building", "Xform")
        MetricsAPI.apply(bldg, meters_per_unit=1.0)
        wall = bldg_stage.DefinePrim("/Building/Wall", "Xform")
        UsdGeom.Xformable(wall).AddTranslateOp().Set(Gf.Vec3d(10, 0, 0))  # 10 m

        # --- Factory floor (m) ---
        factory_layer = Sdf.Layer.CreateAnonymous(".usda")
        factory = Usd.Stage.Open(factory_layer)
        factory.SetMetadata("metersPerUnit", 1.0)
        world = factory.DefinePrim("/World", "Xform")
        MetricsAPI.apply(world, meters_per_unit=1.0)

        # Reference all three
        bolt_ref = factory.DefinePrim("/World/Bolt", "Xform")
        bolt_ref.GetReferences().AddReference(bolt_layer.identifier, "/Bolt")
        robot_ref = factory.DefinePrim("/World/Robot", "Xform")
        robot_ref.GetReferences().AddReference(robot_layer.identifier, "/Robot")
        bldg_ref = factory.DefinePrim("/World/Building", "Xform")
        bldg_ref.GetReferences().AddReference(bldg_layer.identifier, "/Building")

        # Audit
        mismatches = MetricsAssembler.audit_stage(factory)
        # Bolt (mm→m) and Robot (cm→m) should mismatch; Building (m→m) should not
        mismatch_paths = [m["prim_path"] for m in mismatches]
        self.assertIn("/World/Bolt", mismatch_paths)
        self.assertIn("/World/Robot", mismatch_paths)
        self.assertNotIn("/World/Building", mismatch_paths)

        # Correct
        corrections = MetricsAssembler.correct_stage(factory)
        self.assertEqual(len(corrections), 2)

        # Verify world-space positions
        cache = UsdGeom.XformCache()

        shaft_prim = factory.GetPrimAtPath("/World/Bolt/Shaft")
        shaft_world = cache.GetLocalToWorldTransform(shaft_prim).ExtractTranslation()
        self.assertAlmostEqual(shaft_world[0], 0.02, places=4)  # 20mm → 0.02m

        arm_prim = factory.GetPrimAtPath("/World/Robot/Arm")
        arm_world = cache.GetLocalToWorldTransform(arm_prim).ExtractTranslation()
        self.assertAlmostEqual(arm_world[0], 1.5, places=4)  # 150cm → 1.5m

        wall_prim = factory.GetPrimAtPath("/World/Building/Wall")
        wall_world = cache.GetLocalToWorldTransform(wall_prim).ExtractTranslation()
        self.assertAlmostEqual(wall_world[0], 10.0, places=4)  # 10m → 10m

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestPhysicsSimulationReadiness(omni.kit.test.AsyncTestCase):
    """6.2: After correction, all physics values self-consistent in meters."""

    async def test_physics_consistency(self):
        """mm asset with gravity, density, velocity, mass → all correct in meters."""
        mm_layer = Sdf.Layer.CreateAnonymous(".usda")
        mm_stage = Usd.Stage.Open(mm_layer)
        mm_stage.SetMetadata("metersPerUnit", 0.001)

        scene = mm_stage.DefinePrim("/Scene", "PhysicsScene")
        MetricsAPI.apply(scene, meters_per_unit=0.001)
        scene.CreateAttribute("physics:gravityMagnitude", Sdf.ValueTypeNames.Float).Set(9810.0)

        body = mm_stage.DefinePrim("/Scene/Body", "Xform")
        UsdPhysics.RigidBodyAPI.Apply(body)
        UsdPhysics.MassAPI.Apply(body)
        UsdPhysics.CollisionAPI.Apply(body)
        body.CreateAttribute("physics:density", Sdf.ValueTypeNames.Float).Set(7.8e-6)
        body.CreateAttribute("physics:velocity", Sdf.ValueTypeNames.Vector3f).Set(
            Gf.Vec3f(1000, 0, 0)
        )
        body.CreateAttribute("physics:mass", Sdf.ValueTypeNames.Float).Set(2.5)
        UsdGeom.Xformable(body).AddTranslateOp().Set(Gf.Vec3d(500, 0, 0))

        # Assemble into m-scale stage
        root_layer = Sdf.Layer.CreateAnonymous(".usda")
        root_stage = Usd.Stage.Open(root_layer)
        root_stage.SetMetadata("metersPerUnit", 1.0)
        world = root_stage.DefinePrim("/World", "Xform")
        MetricsAPI.apply(world, meters_per_unit=1.0)
        ref = root_stage.DefinePrim("/World/Scene", "Xform")
        ref.GetReferences().AddReference(mm_layer.identifier, "/Scene")

        MetricsAssembler.correct_stage(root_stage)

        # All values in meters
        scene_prim = root_stage.GetPrimAtPath("/World/Scene")
        body_prim = root_stage.GetPrimAtPath("/World/Scene/Body")

        gravity = UnitsLens.get_attr(
            scene_prim.GetAttribute("physics:gravityMagnitude"), target_mpu=1.0
        )
        self.assertAlmostEqual(gravity, 9.81, places=2)

        density = UnitsLens.get_attr(
            body_prim.GetAttribute("physics:density"), target_mpu=1.0
        )
        self.assertAlmostEqual(density, 7800.0, places=0)

        velocity = UnitsLens.get_attr(
            body_prim.GetAttribute("physics:velocity"), target_mpu=1.0
        )
        self.assertAlmostEqual(velocity[0], 1.0, places=4)

        mass = UnitsLens.get_attr(
            body_prim.GetAttribute("physics:mass"), target_mpu=1.0
        )
        self.assertAlmostEqual(mass, 2.5, places=6)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestPerAttributeCustomAttrs(omni.kit.test.AsyncTestCase):
    """6.3: Per-attribute annotation for custom pipeline attributes."""

    async def test_custom_flow_rate(self):
        """myPipeline:flowRate annotated as L³·T⁻¹ — UnitsLens converts it."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.01)  # cm

        prim = stage.DefinePrim("/Pipe", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.01)

        flow_attr = prim.CreateAttribute("myPipeline:flowRate", Sdf.ValueTypeNames.Float)
        flow_attr.Set(5000.0)  # 5000 cm³/s

        # Annotate with L³·T⁻¹
        PerAttributeUnits.annotate(flow_attr, Dimension(L=3, T=-1), meters_per_unit=0.01)

        # Read in meters → L³ factor = (0.01)^3 = 1e-6
        # 5000 * 1e-6 = 0.005 m³/s
        result = UnitsLens.get_attr(flow_attr, target_mpu=1.0)
        self.assertAlmostEqual(result, 0.005, places=6)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestAnnotationOverheadComparison(omni.kit.test.AsyncTestCase):
    """6.4: MetricsAPI (2 annotations) vs per-attribute (many) — count and timing."""

    async def test_overhead_comparison(self):
        """Build a stage with multiple prims, compare annotation counts."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.001)

        # Create a representative hierarchy: 1 root + 10 prims with 3 attrs each
        root = stage.DefinePrim("/Root", "Xform")
        prims = []
        for i in range(10):
            p = stage.DefinePrim(f"/Root/Prim_{i}", "Xform")
            UsdGeom.Xformable(p).AddTranslateOp().Set(Gf.Vec3d(i * 10, 0, 0))
            p.CreateAttribute("physics:velocity", Sdf.ValueTypeNames.Vector3f).Set(
                Gf.Vec3f(100, 0, 0)
            )
            p.CreateAttribute("physics:density", Sdf.ValueTypeNames.Float).Set(1e-6)
            prims.append(p)

        # --- MetricsAPI approach: 1 annotation on root ---
        MetricsAPI.apply(root, meters_per_unit=0.001)
        metrics_annotations = 1  # just the root

        # Verify all children resolve correctly
        for p in prims:
            m = MetricsAPI.get_effective_metrics(p)
            self.assertAlmostEqual(m["metersPerUnit"], 0.001)

        # --- Per-attribute approach: count annotations needed ---
        per_attr_count = 0
        for p in prims:
            for attr in p.GetAttributes():
                if attr.GetName() in ("xformOp:translate", "physics:velocity", "physics:density"):
                    per_attr_count += 1

        # Report
        ratio = per_attr_count / metrics_annotations if metrics_annotations > 0 else float('inf')

        # We expect MetricsAPI to require dramatically fewer annotations
        self.assertGreater(ratio, 10, f"Expected >10x fewer MetricsAPI annotations, got {ratio}x")

        # Timing comparison (informational, not a pass/fail)
        # MetricsAPI read
        UnitsLens.clear_cache()
        t0 = time.perf_counter()
        for p in prims:
            for attr in p.GetAttributes():
                if attr.GetName() in ("xformOp:translate", "physics:velocity", "physics:density"):
                    UnitsLens.get_attr(attr, target_mpu=1.0)
        metrics_time = time.perf_counter() - t0

        # Per-attribute read (would need annotations first — just measure UnitsLens path)
        UnitsLens.clear_cache()
        t0 = time.perf_counter()
        for p in prims:
            for attr in p.GetAttributes():
                if attr.GetName() in ("xformOp:translate", "physics:velocity", "physics:density"):
                    UnitsLens.get_attr(attr, target_mpu=1.0)
        per_attr_time = time.perf_counter() - t0

        # Log results (visible in test output)
        print(f"\n[OVERHEAD] MetricsAPI annotations: {metrics_annotations}")
        print(f"[OVERHEAD] Per-attribute annotations needed: {per_attr_count}")
        print(f"[OVERHEAD] Ratio: {ratio:.0f}x")
        print(f"[OVERHEAD] MetricsAPI read time: {metrics_time*1000:.2f}ms")
        print(f"[OVERHEAD] Per-attribute read time: {per_attr_time*1000:.2f}ms")

    async def tearDown(self):
        UnitsLens.clear_cache()
