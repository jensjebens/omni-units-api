"""Phase 5: PointInstancer & Animation.

Tests 5.1–5.4: Bulk array conversion, time samples, and spline handling.
"""

import omni.kit.test
from pxr import Usd, UsdGeom, Gf, Vt, Sdf

from omni.units_api._lib import MetricsAPI, UnitsLens


class TestPointInstancerPositions(omni.kit.test.AsyncTestCase):
    """5.1: PointInstancer positions — bulk array in cm → meters."""

    async def test_1000_instances_positions(self):
        """1000 instance positions at (100,0,0) cm → (1,0,0) m."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.01)

        pi = stage.DefinePrim("/Instancer", "PointInstancer")
        MetricsAPI.apply(pi, meters_per_unit=0.01)

        count = 1000
        positions = Vt.Vec3fArray([Gf.Vec3f(100, 0, 0)] * count)
        pos_attr = pi.GetAttribute("positions")
        if not pos_attr.IsValid():
            pos_attr = pi.CreateAttribute("positions", Sdf.ValueTypeNames.Point3fArray)
        pos_attr.Set(positions)

        result = UnitsLens.get_attr(pos_attr, target_mpu=1.0)
        self.assertEqual(len(result), count)
        self.assertAlmostEqual(result[0][0], 1.0, places=4)
        self.assertAlmostEqual(result[0][1], 0.0, places=4)
        self.assertAlmostEqual(result[-1][0], 1.0, places=4)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestPointInstancerVelocities(omni.kit.test.AsyncTestCase):
    """5.2: PointInstancer velocities — L¹·T⁻¹ on arrays."""

    async def test_velocities_cm_to_meters(self):
        """velocities (500,0,0) cm/s → (5,0,0) m/s."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.01)

        pi = stage.DefinePrim("/Instancer", "PointInstancer")
        MetricsAPI.apply(pi, meters_per_unit=0.01)

        vel_attr = pi.CreateAttribute("velocities", Sdf.ValueTypeNames.Vector3fArray)
        vel_attr.Set(Vt.Vec3fArray([Gf.Vec3f(500, 0, 0)] * 100))

        result = UnitsLens.get_attr(vel_attr, target_mpu=1.0)
        self.assertAlmostEqual(result[0][0], 5.0, places=4)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestTimeSampledTranslation(omni.kit.test.AsyncTestCase):
    """5.3: Animated translate — bulk get_time_samples() with conversion."""

    async def test_animated_translate_cm_to_meters(self):
        """240 frames of translate in cm, read as meters."""
        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.01)

        prim = stage.DefinePrim("/Mover", "Xform")
        MetricsAPI.apply(prim, meters_per_unit=0.01)
        xf = UsdGeom.Xformable(prim)
        translate_op = xf.AddTranslateOp()

        # Animate: frame 1–240, linear motion 0→2400 cm along X
        for frame in range(1, 241):
            translate_op.Set(Gf.Vec3d(frame * 10, 0, 0), frame)

        attr = prim.GetAttribute("xformOp:translate")
        samples = UnitsLens.get_time_samples(attr, target_mpu=1.0)

        self.assertEqual(len(samples), 240)
        # Frame 1: 10 cm → 0.1 m
        self.assertAlmostEqual(samples[0][1][0], 0.1, places=4)
        # Frame 240: 2400 cm → 24 m
        self.assertAlmostEqual(samples[-1][1][0], 24.0, places=4)

    async def tearDown(self):
        UnitsLens.clear_cache()


class TestBezierSplineConversion(omni.kit.test.AsyncTestCase):
    """5.4: Bezier spline — values AND tangent slopes scale, widths preserved."""

    async def test_spline_focus_distance(self):
        """Animated focusDistance with spline in cm → meters.

        Note: Ts.Spline support requires OpenUSD 26.x with spline API.
        This test may be skipped on older builds.
        """
        try:
            from pxr import Ts
        except ImportError:
            self.skipTest("Ts module not available — spline test requires OpenUSD 26.x")

        stage = Usd.Stage.CreateInMemory()
        stage.SetMetadata("metersPerUnit", 0.01)

        cam = stage.DefinePrim("/Camera", "Camera")
        MetricsAPI.apply(cam, meters_per_unit=0.01)

        # Use double-typed attribute so spline knots (which default to double) match
        fd_attr = cam.CreateAttribute("testFocusDistance", Sdf.ValueTypeNames.Double)

        # Create a bezier spline: 100cm at frame 1, 500cm at frame 24
        spline = Ts.Spline()
        k1 = Ts.Knot()
        k1.SetTime(1.0)
        k1.SetValue(100.0)  # 100 cm
        k1.SetPostTanSlope(20.0)  # dValue/dTime in cm/frame
        k1.SetPostTanWidth(5.0)   # frames (time unit)
        k1.SetPreTanSlope(0.0)
        k1.SetPreTanWidth(0.0)
        k1.SetNextInterpolation(Ts.InterpValueBlock)
        spline.SetKnot(k1)

        k2 = Ts.Knot()
        k2.SetTime(24.0)
        k2.SetValue(500.0)  # 500 cm
        k2.SetPreTanSlope(15.0)
        k2.SetPreTanWidth(5.0)
        k2.SetPostTanSlope(0.0)
        k2.SetPostTanWidth(0.0)
        k2.SetNextInterpolation(Ts.InterpValueBlock)
        spline.SetKnot(k2)

        fd_attr.SetSpline(spline)

        # Register testFocusDistance as L1 (same as focusDistance) for this test
        from omni.units_api._lib.dimensions import DIMENSION_REGISTRY, Dimension
        DIMENSION_REGISTRY["testFocusDistance"] = Dimension(L=1)

        try:
            converted = UnitsLens.get_spline(fd_attr, target_mpu=1.0)
            self.assertIsNotNone(converted)

            knots = list(converted.GetKnots().keys())
            self.assertEqual(len(knots), 2)

            # Values scaled: 100cm → 1m, 500cm → 5m
            k1_conv = converted.GetKnot(1.0)
            k2_conv = converted.GetKnot(24.0)
            self.assertAlmostEqual(k1_conv.GetValue(), 1.0, places=4)
            self.assertAlmostEqual(k2_conv.GetValue(), 5.0, places=4)

            # Slopes scaled: 20 cm/frame → 0.2 m/frame
            self.assertAlmostEqual(k1_conv.GetPostTanSlope(), 0.2, places=4)

            # Widths preserved (time units, not spatial)
            self.assertAlmostEqual(k1_conv.GetPostTanWidth(), 5.0, places=4)
        finally:
            del DIMENSION_REGISTRY["testFocusDistance"]

    async def tearDown(self):
        UnitsLens.clear_cache()
