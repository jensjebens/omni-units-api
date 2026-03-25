"""Phase 2: Assembly Correction — MetricsAssembler in Omniverse.

Tests 2.1–2.4: Verify corrective xformOps at reference boundaries.
"""

import omni.kit.test
from pxr import Usd, UsdGeom, Gf, Sdf

from omni.units_api._lib import MetricsAPI, MetricsAssembler, UnitsLens


class TestCorrectiveXformOnReference(omni.kit.test.AsyncTestCase):
    """2.1: Corrective xformOp:scale:metricsCorrection on reference."""

    async def setUp(self):
        # mm-scale asset
        self.mm_layer = Sdf.Layer.CreateAnonymous(".usda")
        mm_stage = Usd.Stage.Open(self.mm_layer)
        mm_stage.SetMetadata("metersPerUnit", 0.001)
        mm_root = mm_stage.DefinePrim("/Bolt", "Xform")
        MetricsAPI.apply(mm_root, meters_per_unit=0.001)
        shaft = mm_stage.DefinePrim("/Bolt/Shaft", "Xform")
        UsdGeom.Xformable(shaft).AddTranslateOp().Set(Gf.Vec3d(10, 0, 0))  # 10 mm

        # meter-scale root stage
        self.root_layer = Sdf.Layer.CreateAnonymous(".usda")
        self.root_stage = Usd.Stage.Open(self.root_layer)
        self.root_stage.SetMetadata("metersPerUnit", 1.0)
        world = self.root_stage.DefinePrim("/World", "Xform")
        MetricsAPI.apply(world, meters_per_unit=1.0)

        ref_prim = self.root_stage.DefinePrim("/World/Bolt", "Xform")
        ref_prim.GetReferences().AddReference(self.mm_layer.identifier, "/Bolt")

    async def test_corrective_scale_applied(self):
        """MetricsAssembler should add xformOp:scale:metricsCorrection."""
        corrections = MetricsAssembler.correct_stage(self.root_stage)
        self.assertEqual(len(corrections), 1)
        self.assertEqual(corrections[0]["prim_path"], "/World/Bolt")
        self.assertAlmostEqual(corrections[0]["scale"], 0.001)  # mm → m

        # Verify the xformOp exists
        bolt = self.root_stage.GetPrimAtPath("/World/Bolt")
        xf = UsdGeom.Xformable(bolt)
        op_names = [op.GetOpName() for op in xf.GetOrderedXformOps()]
        self.assertIn("xformOp:scale:metricsCorrection", op_names)


class TestVisualValidation(omni.kit.test.AsyncTestCase):
    """2.2: After correction, world-space positions are correct."""

    async def test_world_position_after_correction(self):
        """Shaft at 10mm local → should be 0.01m in world space after correction."""
        mm_layer = Sdf.Layer.CreateAnonymous(".usda")
        mm_stage = Usd.Stage.Open(mm_layer)
        mm_stage.SetMetadata("metersPerUnit", 0.001)
        mm_root = mm_stage.DefinePrim("/Bolt", "Xform")
        MetricsAPI.apply(mm_root, meters_per_unit=0.001)
        shaft = mm_stage.DefinePrim("/Bolt/Shaft", "Xform")
        UsdGeom.Xformable(shaft).AddTranslateOp().Set(Gf.Vec3d(10, 0, 0))

        root_layer = Sdf.Layer.CreateAnonymous(".usda")
        root_stage = Usd.Stage.Open(root_layer)
        root_stage.SetMetadata("metersPerUnit", 1.0)
        world = root_stage.DefinePrim("/World", "Xform")
        MetricsAPI.apply(world, meters_per_unit=1.0)
        ref_prim = root_stage.DefinePrim("/World/Bolt", "Xform")
        ref_prim.GetReferences().AddReference(mm_layer.identifier, "/Bolt")

        MetricsAssembler.correct_stage(root_stage)

        # Check world-space position via XformCache
        cache = UsdGeom.XformCache()
        shaft_prim = root_stage.GetPrimAtPath("/World/Bolt/Shaft")
        world_xf = cache.GetLocalToWorldTransform(shaft_prim)
        world_pos = world_xf.ExtractTranslation()

        # 10mm * 0.001 scale = 0.01 meters
        self.assertAlmostEqual(world_pos[0], 0.01, places=6)
        self.assertAlmostEqual(world_pos[1], 0.0, places=6)
        self.assertAlmostEqual(world_pos[2], 0.0, places=6)


class TestAuditWithoutCorrection(omni.kit.test.AsyncTestCase):
    """2.3: audit_stage() detects mismatches without modifying the stage."""

    async def test_audit_is_read_only(self):
        mm_layer = Sdf.Layer.CreateAnonymous(".usda")
        mm_stage = Usd.Stage.Open(mm_layer)
        mm_stage.SetMetadata("metersPerUnit", 0.001)
        mm_root = mm_stage.DefinePrim("/Part", "Xform")
        MetricsAPI.apply(mm_root, meters_per_unit=0.001)

        root_layer = Sdf.Layer.CreateAnonymous(".usda")
        root_stage = Usd.Stage.Open(root_layer)
        root_stage.SetMetadata("metersPerUnit", 1.0)
        world = root_stage.DefinePrim("/World", "Xform")
        MetricsAPI.apply(world, meters_per_unit=1.0)
        ref = root_stage.DefinePrim("/World/Part", "Xform")
        ref.GetReferences().AddReference(mm_layer.identifier, "/Part")

        # Snapshot xformOps before audit
        part = root_stage.GetPrimAtPath("/World/Part")
        ops_before = [op.GetOpName() for op in UsdGeom.Xformable(part).GetOrderedXformOps()]

        mismatches = MetricsAssembler.audit_stage(root_stage)
        self.assertEqual(len(mismatches), 1)
        self.assertAlmostEqual(mismatches[0]["scale"], 0.001)

        # Verify no xformOps were added
        ops_after = [op.GetOpName() for op in UsdGeom.Xformable(part).GetOrderedXformOps()]
        self.assertEqual(ops_before, ops_after)


class TestUpAxisCorrection(omni.kit.test.AsyncTestCase):
    """2.4: Y-up + Z-up asset mix — corrective rotation."""

    async def test_y_to_z_rotation(self):
        """Y-up asset into Z-up stage should get -90° X rotation."""
        y_layer = Sdf.Layer.CreateAnonymous(".usda")
        y_stage = Usd.Stage.Open(y_layer)
        y_stage.SetMetadata("metersPerUnit", 1.0)
        y_stage.SetMetadata("upAxis", "Y")
        y_root = y_stage.DefinePrim("/Asset", "Xform")
        MetricsAPI.apply(y_root, meters_per_unit=1.0, up_axis="Y")

        z_layer = Sdf.Layer.CreateAnonymous(".usda")
        z_stage = Usd.Stage.Open(z_layer)
        z_stage.SetMetadata("metersPerUnit", 1.0)
        z_stage.SetMetadata("upAxis", "Z")
        world = z_stage.DefinePrim("/World", "Xform")
        MetricsAPI.apply(world, meters_per_unit=1.0, up_axis="Z")
        ref = z_stage.DefinePrim("/World/Asset", "Xform")
        ref.GetReferences().AddReference(y_layer.identifier, "/Asset")

        corrections = MetricsAssembler.correct_stage(z_stage)
        self.assertEqual(len(corrections), 1)
        self.assertAlmostEqual(corrections[0]["rotation"], -90.0)

        # Verify rotation xformOp exists
        asset = z_stage.GetPrimAtPath("/World/Asset")
        xf = UsdGeom.Xformable(asset)
        op_names = [op.GetOpName() for op in xf.GetOrderedXformOps()]
        self.assertIn("xformOp:rotateX:metricsCorrection", op_names)
