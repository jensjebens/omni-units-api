"""Phase 3: Physics Attributes — derived quantity conversion.

Tests 3.1–3.5: Verify dimensional exponent handling for physics attributes.
"""

import omni.kit.test
from pxr import Usd, UsdGeom, UsdPhysics, Gf, Sdf

from omni.units_api._lib import MetricsAPI, UnitsLens, MetricsAssembler


class TestDensityConversion(omni.kit.test.AsyncTestCase):
    """3.1: physics:density — L⁻³·M¹ exponent."""

    async def test_density_mm_to_meters(self):
        """Steel density: 7.8e-6 kg/mm³ → 7800 kg/m³."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.001)  # mm

        prim = stage.DefinePrim("/Steel", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.001)

        # Apply physics schemas
        UsdPhysics.CollisionAPI.Apply(prim)
        UsdPhysics.MassAPI.Apply(prim)

        density_attr = prim.CreateAttribute("physics:density", Sdf.ValueTypeNames.Float)
        # Steel: 7800 kg/m³ = 7.8e-6 kg/mm³
        density_attr.Set(7.8e-6)

        result = UnitsLens.get_attr(density_attr, target_mpu=1.0)
        # L⁻³: (0.001/1.0)^-3 = 1e9, M¹: factor 1.0
        # 7.8e-6 * 1e9 = 7800
        self.assertAlmostEqual(result, 7800.0, places=0)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestGravityMagnitude(omni.kit.test.AsyncTestCase):
    """3.2: physics:gravityMagnitude — L¹·T⁻² exponent."""

    async def test_gravity_mm_to_meters(self):
        """9810 mm/s² → 9.81 m/s²."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.001)

        scene = stage.DefinePrim("/PhysicsScene", "PhysicsScene")
        MetricsAPI.apply(scene, meters_per_unit=0.001)

        grav_attr = scene.CreateAttribute("physics:gravityMagnitude", Sdf.ValueTypeNames.Float)
        grav_attr.Set(9810.0)  # mm/s²

        result = UnitsLens.get_attr(grav_attr, target_mpu=1.0)
        # L¹: (0.001/1.0)^1 = 0.001
        # 9810 * 0.001 = 9.81
        self.assertAlmostEqual(result, 9.81, places=2)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestVelocityConversion(omni.kit.test.AsyncTestCase):
    """3.3: physics:velocity — L¹·T⁻¹ exponent."""

    async def test_velocity_cm_to_meters(self):
        """500 cm/s → 5 m/s."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.01)  # cm

        prim = stage.DefinePrim("/RigidBody", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.01)
        UsdPhysics.RigidBodyAPI.Apply(prim)

        vel_attr = prim.CreateAttribute("physics:velocity", Sdf.ValueTypeNames.Vector3f)
        vel_attr.Set(Gf.Vec3f(500, 0, 0))  # 500 cm/s

        result = UnitsLens.get_attr(vel_attr, target_mpu=1.0)
        # L¹: (0.01/1.0)^1 = 0.01
        # 500 * 0.01 = 5.0
        self.assertAlmostEqual(result[0], 5.0, places=4)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestMassPassthrough(omni.kit.test.AsyncTestCase):
    """3.4: physics:mass — M¹ only, no L component."""

    async def test_mass_unchanged_by_mpu(self):
        """10 kg stays 10 kg regardless of metersPerUnit."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.001)  # mm

        prim = stage.DefinePrim("/Object", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.001, kilograms_per_unit=1.0)
        UsdPhysics.MassAPI.Apply(prim)

        mass_attr = prim.CreateAttribute("physics:mass", Sdf.ValueTypeNames.Float)
        mass_attr.Set(10.0)

        # Same kpu source and target → factor = 1.0
        result = UnitsLens.get_attr(mass_attr, target_mpu=1.0, target_kpu=1.0)
        self.assertAlmostEqual(result, 10.0, places=6)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestCrossReferencePhysics(omni.kit.test.AsyncTestCase):
    """3.5: Full stack — assembly correction + UnitsLens for physics."""

    async def test_mm_rigid_body_in_meter_stage(self):
        """mm-scale rigid body with density, velocity, mass referenced into m-scale stage.

        After assembly correction, transforms are correct via xformOp.
        Physics values are correct via UnitsLens.
        """
        # mm asset
        mm_layer = Sdf.Layer.CreateAnonymous(".usda")
        mm_stage = Usd.Stage.Open(mm_layer)
        mm_stage.SetMetadata("metersPerUnit", 0.001)

        body = mm_stage.DefinePrim("/Body", "Xform")
        MetricsAPI.apply(body, meters_per_unit=0.001, kilograms_per_unit=1.0)
        UsdGeom.Xformable(body).AddTranslateOp().Set(Gf.Vec3d(1000, 0, 0))  # 1000 mm = 1 m
        UsdPhysics.RigidBodyAPI.Apply(body)
        UsdPhysics.MassAPI.Apply(body)
        UsdPhysics.CollisionAPI.Apply(body)

        body.CreateAttribute("physics:density", Sdf.ValueTypeNames.Float).Set(7.8e-6)
        body.CreateAttribute("physics:velocity", Sdf.ValueTypeNames.Vector3f).Set(
            Gf.Vec3f(2000, 0, 0)  # 2000 mm/s = 2 m/s
        )
        body.CreateAttribute("physics:mass", Sdf.ValueTypeNames.Float).Set(5.0)

        # m-scale root
        root_layer = Sdf.Layer.CreateAnonymous(".usda")
        root_stage = Usd.Stage.Open(root_layer)
        root_stage.SetMetadata("metersPerUnit", 1.0)
        world = root_stage.DefinePrim("/World", "Xform")
        MetricsAPI.apply(world, meters_per_unit=1.0)
        ref = root_stage.DefinePrim("/World/Body", "Xform")
        ref.GetReferences().AddReference(mm_layer.identifier, "/Body")

        # Assembly correction for transforms
        corrections = MetricsAssembler.correct_stage(root_stage)
        self.assertEqual(len(corrections), 1)

        # Verify world-space transform
        cache = UsdGeom.XformCache()
        body_prim = root_stage.GetPrimAtPath("/World/Body")
        world_pos = cache.GetLocalToWorldTransform(body_prim).ExtractTranslation()
        self.assertAlmostEqual(world_pos[0], 1.0, places=4)  # 1 meter

        # Verify physics via UnitsLens
        density = UnitsLens.get_attr(
            body_prim.GetAttribute("physics:density"), target_mpu=1.0
        )
        self.assertAlmostEqual(density, 7800.0, places=0)

        velocity = UnitsLens.get_attr(
            body_prim.GetAttribute("physics:velocity"), target_mpu=1.0
        )
        self.assertAlmostEqual(velocity[0], 2.0, places=4)

        mass = UnitsLens.get_attr(
            body_prim.GetAttribute("physics:mass"), target_mpu=1.0
        )
        self.assertAlmostEqual(mass, 5.0, places=6)

    async def tearDown(self):
        UnitsLens.clear_cache()
