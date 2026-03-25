import omni.ext
import carb


class UnitsApiExtension(omni.ext.IExt):
    """Units API Extension — unit-aware USD attribute access for Omniverse."""

    def on_startup(self, ext_id):
        carb.log_info("[omni.units_api] Extension startup")

    def on_shutdown(self):
        carb.log_info("[omni.units_api] Extension shutdown")
