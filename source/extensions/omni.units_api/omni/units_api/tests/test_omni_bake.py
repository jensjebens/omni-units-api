"""Phase 7: bake_to_units — convert all attribute values to target units via overs.

Tests that bake_to_units creates an override layer with converted values,
leaving the original data untouched underneath.
"""

import omni.kit.test
from pxr import Usd, UsdGeom, UsdPhysics, Gf, Sdf

from omni.units_api._lib import MetricsAPI, MetricsAssembler, UnitsLens


class TestBakeToUnitsBasic(omni.kit.test.AsyncTestCase):
    """bake_to_units converts a mm stage to meters."""

    async def test_bake_mm_to_meters(self):
        """Create a mm stage with translate + density, bake to meters."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.001)

        prim = stage.DefinePrim("/Bolt", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.001, kilograms_per_unit=1.0)

        # Translate: 10 mm
        xf = UsdGeom.Xformable(prim)
        xf.AddTranslateOp().Set(Gf.Vec3d(10, 0, 0))

        # Density: 7.8e-6 kg/mm³ (= 7800 kg/m³)
        UsdPhysics.MassAPI.Apply(prim)
        UsdPhysics.CollisionAPI.Apply(prim)
        density_attr = prim.CreateAttribute("physics:density", Sdf.ValueTypeNames.Float)
        density_attr.Set(7.8e-6)

        # Bake to meters
        result = MetricsAssembler.bake_to_units(stage, target_mpu=1.0)

        self.assertGreater(result["attrs_converted"], 0)
        self.assertIsNotNone(result["layer"])

        # Now read values — they should be in meters without UnitsLens
        bolt = stage.GetPrimAtPath("/Bolt")
        translate = bolt.GetAttribute("xformOp:translate").Get()
        self.assertAlmostEqual(translate[0], 0.01, places=6)  # 10mm → 0.01m

        density = bolt.GetAttribute("physics:density").Get()
        self.assertAlmostEqual(density, 7800.0, places=0)  # 7.8e-6 kg/mm³ → 7800 kg/m³

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestBakePreservesOriginal(omni.kit.test.AsyncTestCase):
    """bake_to_units is non-destructive — original layer unchanged."""

    async def test_original_layer_untouched(self):
        # Create stage with explicit root layer
        root_layer = Sdf.Layer.CreateAnonymous(".usda")
        stage = Usd.Stage.Open(root_layer)
        stage.SetMetadata("metersPerUnit", 0.01)  # cm

        prim = stage.DefinePrim("/Object", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.01)
        xf = UsdGeom.Xformable(prim)
        xf.AddTranslateOp().Set(Gf.Vec3d(500, 0, 0))  # 500 cm

        # Snapshot original layer content
        original_usda = root_layer.ExportToString()

        # Bake
        result = MetricsAssembler.bake_to_units(stage, target_mpu=1.0)

        # Original layer should be unchanged
        self.assertEqual(root_layer.ExportToString(), original_usda)

        # But composed value should be in meters
        translate = stage.GetPrimAtPath("/Object").GetAttribute("xformOp:translate").Get()
        self.assertAlmostEqual(translate[0], 5.0, places=4)  # 500cm → 5m

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestBakeTimeSamples(omni.kit.test.AsyncTestCase):
    """bake_to_units converts animated attributes."""

    async def test_animated_translate_baked(self):
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.01)  # cm

        prim = stage.DefinePrim("/Mover", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.01)
        xf = UsdGeom.Xformable(prim)
        op = xf.AddTranslateOp()
        for frame in range(1, 25):
            op.Set(Gf.Vec3d(frame * 100, 0, 0), frame)  # 100-2400 cm

        result = MetricsAssembler.bake_to_units(stage, target_mpu=1.0)

        self.assertGreater(result["time_samples_converted"], 0)

        # Check frame 1: 100 cm → 1 m
        attr = stage.GetPrimAtPath("/Mover").GetAttribute("xformOp:translate")
        val = attr.Get(1)
        self.assertAlmostEqual(val[0], 1.0, places=4)

        # Check frame 24: 2400 cm → 24 m
        val = attr.Get(24)
        self.assertAlmostEqual(val[0], 24.0, places=4)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestBakePhysicsConsistency(omni.kit.test.AsyncTestCase):
    """After baking, all physics values are self-consistent in target units."""

    async def test_full_physics_bake(self):
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.001)  # mm

        scene = stage.DefinePrim("/Scene", "Xform")
        MetricsAPI.apply(scene, meters_per_unit=0.001)

        scene.CreateAttribute("physics:gravityMagnitude", Sdf.ValueTypeNames.Float).Set(9810.0)

        body = stage.DefinePrim("/Scene/Body", "Xform")
        UsdPhysics.RigidBodyAPI.Apply(body)
        UsdPhysics.MassAPI.Apply(body)
        UsdPhysics.CollisionAPI.Apply(body)
        body.CreateAttribute("physics:density", Sdf.ValueTypeNames.Float).Set(7.8e-6)
        body.CreateAttribute("physics:velocity", Sdf.ValueTypeNames.Vector3f).Set(
            Gf.Vec3f(1000, 0, 0)  # 1000 mm/s
        )
        body.CreateAttribute("physics:mass", Sdf.ValueTypeNames.Float).Set(2.5)
        UsdGeom.Xformable(body).AddTranslateOp().Set(Gf.Vec3d(500, 0, 0))  # 500 mm

        MetricsAssembler.bake_to_units(stage, target_mpu=1.0)

        # All values should now be in meters — no UnitsLens needed
        scene_prim = stage.GetPrimAtPath("/Scene")
        body_prim = stage.GetPrimAtPath("/Scene/Body")

        gravity = scene_prim.GetAttribute("physics:gravityMagnitude").Get()
        self.assertAlmostEqual(gravity, 9.81, places=2)

        density = body_prim.GetAttribute("physics:density").Get()
        self.assertAlmostEqual(density, 7800.0, places=0)

        velocity = body_prim.GetAttribute("physics:velocity").Get()
        self.assertAlmostEqual(velocity[0], 1.0, places=4)  # 1000mm/s → 1m/s

        mass = body_prim.GetAttribute("physics:mass").Get()
        self.assertAlmostEqual(mass, 2.5, places=6)  # mass unchanged (same kpu)

        translate = body_prim.GetAttribute("xformOp:translate").Get()
        self.assertAlmostEqual(translate[0], 0.5, places=4)  # 500mm → 0.5m

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestBakeSkipsUnitless(omni.kit.test.AsyncTestCase):
    """bake_to_units doesn't touch unitless or unknown attributes."""

    async def test_unitless_preserved(self):
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.001)

        prim = stage.DefinePrim("/Thing", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.001)

        # Unitless attribute (visibility is a token, doubleSided is bool)
        prim.CreateAttribute("customUnknown:foo", Sdf.ValueTypeNames.Float).Set(42.0)

        MetricsAssembler.bake_to_units(stage, target_mpu=1.0)

        # Unknown attribute should be untouched
        val = stage.GetPrimAtPath("/Thing").GetAttribute("customUnknown:foo").Get()
        self.assertAlmostEqual(val, 42.0, places=6)

    async def tearDown(self):
        UnitsLens.clear_cache()
