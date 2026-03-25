"""Phase 4: Camera & Light Attributes.

Tests 4.1–4.4: Verify scene-unit vs fixed-unit attribute handling.
"""

import omni.kit.test
from pxr import Usd, UsdGeom, UsdLux, Gf, Sdf

from omni.units_api._lib import MetricsAPI, UnitsLens


class TestFocusDistanceConversion(omni.kit.test.AsyncTestCase):
    """4.1: focusDistance — L¹ scene-unit camera attribute."""

    async def test_focus_distance_cm_to_meters(self):
        """focusDistance = 500 cm → 5 m."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.01)

        cam = stage.DefinePrim("/Camera", "Camera")
        MetricsAPI.apply(cam, meters_per_unit=0.01)
        fd_attr = cam.GetAttribute("focusDistance")
        if not fd_attr.IsValid():
            fd_attr = cam.CreateAttribute("focusDistance", Sdf.ValueTypeNames.Float)
        fd_attr.Set(500.0)  # 500 cm

        result = UnitsLens.get_attr(fd_attr, target_mpu=1.0)
        self.assertAlmostEqual(result, 5.0, places=4)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestClippingRangeConversion(omni.kit.test.AsyncTestCase):
    """4.2: clippingRange — L¹ scene-unit camera attribute."""

    async def test_clipping_range_cm_to_meters(self):
        """clippingRange = (1, 100000) cm → (0.01, 1000) m."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.01)

        cam = stage.DefinePrim("/Camera", "Camera")
        MetricsAPI.apply(cam, meters_per_unit=0.01)
        cr_attr = cam.GetAttribute("clippingRange")
        if not cr_attr.IsValid():
            cr_attr = cam.CreateAttribute("clippingRange", Sdf.ValueTypeNames.Float2)
        cr_attr.Set(Gf.Vec2f(1.0, 100000.0))

        result = UnitsLens.get_attr(cr_attr, target_mpu=1.0)
        self.assertAlmostEqual(result[0], 0.01, places=4)
        self.assertAlmostEqual(result[1], 1000.0, places=1)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestFocalLengthPassthrough(omni.kit.test.AsyncTestCase):
    """4.3: focalLength — fixed mm per schema, should NOT scale."""

    async def test_focal_length_unchanged(self):
        """focalLength = 50 (mm per schema) should stay 50 regardless of mpu."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.01)

        cam = stage.DefinePrim("/Camera", "Camera")
        MetricsAPI.apply(cam, meters_per_unit=0.01)
        fl_attr = cam.GetAttribute("focalLength")
        if not fl_attr.IsValid():
            fl_attr = cam.CreateAttribute("focalLength", Sdf.ValueTypeNames.Float)
        fl_attr.Set(50.0)

        # focalLength is not in the registry → passthrough
        result = UnitsLens.get_attr(fl_attr, target_mpu=1.0)
        self.assertAlmostEqual(result, 50.0, places=6)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestLightSpatialDimensions(omni.kit.test.AsyncTestCase):
    """4.4: Light inputs:width, inputs:height, inputs:radius — L¹."""

    async def test_rect_light_dimensions_cm_to_meters(self):
        """RectLight 200x100 cm → 2x1 m."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.01)

        light = stage.DefinePrim("/RectLight", "RectLight")
        MetricsAPI.apply(light, meters_per_unit=0.01)

        w_attr = light.CreateAttribute("inputs:width", Sdf.ValueTypeNames.Float)
        h_attr = light.CreateAttribute("inputs:height", Sdf.ValueTypeNames.Float)
        w_attr.Set(200.0)
        h_attr.Set(100.0)

        w = UnitsLens.get_attr(w_attr, target_mpu=1.0)
        h = UnitsLens.get_attr(h_attr, target_mpu=1.0)
        self.assertAlmostEqual(w, 2.0, places=4)
        self.assertAlmostEqual(h, 1.0, places=4)

    async def test_sphere_light_radius_mm_to_meters(self):
        """SphereLight radius 50 mm → 0.05 m."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.001)

        light = stage.DefinePrim("/SphereLight", "SphereLight")
        MetricsAPI.apply(light, meters_per_unit=0.001)

        r_attr = light.CreateAttribute("inputs:radius", Sdf.ValueTypeNames.Float)
        r_attr.Set(50.0)

        r = UnitsLens.get_attr(r_attr, target_mpu=1.0)
        self.assertAlmostEqual(r, 0.05, places=6)

    async def tearDown(self):
        UnitsLens.clear_cache()
