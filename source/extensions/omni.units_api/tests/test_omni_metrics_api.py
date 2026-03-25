"""Phase 1: Core Validation — MetricsAPI in Kit.

Tests 1.1–1.3: Verify that MetricsAPI and UnitsLens work correctly
inside an Omniverse Kit runtime with real stage composition.
"""

import omni.kit.test
from pxr import Usd, UsdGeom, Gf, Sdf

from omni.units_api._lib import MetricsAPI, UnitsLens


class TestMetricsApiRoundTrip(omni.kit.test.AsyncTestCase):
    """1.1: MetricsAPI round-trip — apply, save, reload, verify."""

    async def setUp(self):
        # Create a fresh in-memory stage via Kit
        self.stage = Usd.Stage.CreateInMemory()
        self.stage.SetMetadata("metersPerUnit", 1.0)
        self.stage.SetMetadata("upAxis", "Z")

    async def test_apply_and_read_back(self):
        """Apply MetricsAPI to a prim, verify it reads back correctly."""
        prim = self.stage.DefinePrim("/World/Bolt", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.001, up_axis="Z", kilograms_per_unit=1.0)

        # Direct read (not inherited)
        metrics = MetricsAPI.get_metrics(prim)
        self.assertAlmostEqual(metrics["metersPerUnit"], 0.001)
        self.assertEqual(metrics["upAxis"], "Z")
        self.assertAlmostEqual(metrics["kilogramsPerUnit"], 1.0)

    async def test_effective_metrics_with_no_annotation(self):
        """Prim without MetricsAPI should fall back to stage metadata."""
        prim = self.stage.DefinePrim("/World/Unannotated", "Xform")
        metrics = MetricsAPI.get_effective_metrics(prim)
        self.assertAlmostEqual(metrics["metersPerUnit"], 1.0)
        self.assertEqual(metrics["upAxis"], "Z")

    async def test_save_and_reload(self):
        """Apply metrics, export to temp file, reload, verify persistence."""
        import tempfile
        import os

        prim = self.stage.DefinePrim("/World/Part", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.01)

        # Save to temp usda
        tmp = tempfile.NamedTemporaryFile(suffix=".usda", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            self.stage.Export(tmp_path)

            # Reload
            reloaded = Usd.Stage.Open(tmp_path)
            reloaded_prim = reloaded.GetPrimAtPath("/World/Part")
            metrics = MetricsAPI.get_metrics(reloaded_prim)
            self.assertAlmostEqual(metrics["metersPerUnit"], 0.01)
        finally:
            os.unlink(tmp_path)


class TestMetricsApiInheritance(omni.kit.test.AsyncTestCase):
    """1.2: MetricsAPI inheritance through references."""

    async def test_ancestor_walk_through_references(self):
        """Reference a mm-scale asset into a meter-scale stage.

        Verify ancestor walk resolves the mm context for prims
        inside the referenced subtree, and meter context above.
        """
        # Create the "mm asset" layer
        mm_layer = Sdf.Layer.CreateAnonymous(".usda")
        mm_stage = Usd.Stage.Open(mm_layer)
        mm_stage.SetMetadata("metersPerUnit", 0.001)
        mm_root = mm_stage.DefinePrim("/Bolt", "Xform")
        MetricsAPI.apply(mm_root, meters_per_unit=0.001)
        shaft = mm_stage.DefinePrim("/Bolt/Shaft", "Xform")
        xf = UsdGeom.Xformable(shaft)
        xf.AddTranslateOp().Set(Gf.Vec3d(10, 0, 0))  # 10 mm

        # Create the meter-scale root stage
        root_layer = Sdf.Layer.CreateAnonymous(".usda")
        root_stage = Usd.Stage.Open(root_layer)
        root_stage.SetMetadata("metersPerUnit", 1.0)
        world = root_stage.DefinePrim("/World", "Xform")
        MetricsAPI.apply(world, meters_per_unit=1.0)

        # Reference mm asset into root stage
        ref_prim = root_stage.DefinePrim("/World/Bolt", "Xform")
        ref_prim.GetReferences().AddReference(
            mm_layer.identifier, "/Bolt"
        )

        # Verify: /World has meter context
        world_metrics = MetricsAPI.get_effective_metrics(world)
        self.assertAlmostEqual(world_metrics["metersPerUnit"], 1.0)

        # Verify: /World/Bolt has mm context (from reference)
        bolt_prim = root_stage.GetPrimAtPath("/World/Bolt")
        bolt_metrics = MetricsAPI.get_effective_metrics(bolt_prim)
        self.assertAlmostEqual(bolt_metrics["metersPerUnit"], 0.001)

        # Verify: /World/Bolt/Shaft inherits mm context
        shaft_prim = root_stage.GetPrimAtPath("/World/Bolt/Shaft")
        shaft_metrics = MetricsAPI.get_effective_metrics(shaft_prim)
        self.assertAlmostEqual(shaft_metrics["metersPerUnit"], 0.001)


class TestUnitsLensInKit(omni.kit.test.AsyncTestCase):
    """1.3: UnitsLens get/set in Kit runtime."""

    async def setUp(self):
        self.stage = Usd.Stage.CreateInMemory()
        self.stage.SetMetadata("metersPerUnit", 0.01)  # cm stage

    async def test_get_translate_converts_to_meters(self):
        """Set translate in cm, read via UnitsLens in meters."""
        prim = self.stage.DefinePrim("/Object", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.01)
        xf = UsdGeom.Xformable(prim)
        xf.AddTranslateOp().Set(Gf.Vec3d(100, 0, 0))  # 100 cm

        result = UnitsLens.get_attr(
            prim.GetAttribute("xformOp:translate"), target_mpu=1.0
        )
        self.assertAlmostEqual(result[0], 1.0, places=6)  # 1 meter
        self.assertAlmostEqual(result[1], 0.0, places=6)
        self.assertAlmostEqual(result[2], 0.0, places=6)

    async def test_set_translate_converts_from_meters(self):
        """Set 5 meters via UnitsLens on a cm prim, verify stored as 500."""
        prim = self.stage.DefinePrim("/Object2", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.01)

        UnitsLens.set_translate(prim, Gf.Vec3d(5, 0, 0), source_mpu=1.0)

        # Read raw value — should be 500 cm
        xf = UsdGeom.Xformable(prim)
        ops = xf.GetOrderedXformOps()
        raw = ops[0].Get()
        self.assertAlmostEqual(raw[0], 500.0, places=4)

    async def test_get_and_set_round_trip(self):
        """Set via UnitsLens in meters, read back via UnitsLens in meters."""
        prim = self.stage.DefinePrim("/Object3", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.01)

        original = Gf.Vec3d(3.7, 1.2, 0.5)
        UnitsLens.set_translate(prim, original, source_mpu=1.0)

        result = UnitsLens.get_translate(prim, target_mpu=1.0)
        self.assertAlmostEqual(result[0], original[0], places=6)
        self.assertAlmostEqual(result[1], original[1], places=6)
        self.assertAlmostEqual(result[2], original[2], places=6)

    async def tearDown(self):
        UnitsLens.clear_cache()
