import omni.ext
import carb


class UnitsApiExtension(omni.ext.IExt):
    """Units API Extension — unit-aware USD attribute access for Omniverse.

    Provides:
    - Units Inspector window (Window > Units Inspector)
    - Unit-aware property widget (auto-registers for unit-bearing attributes)
    """

    def __init__(self):
        super().__init__()
        self._inspector = None
        self._menu_entry = None

    def on_startup(self, ext_id):
        carb.log_info("[omni.units_api] Extension startup")
        self._register_menu()

    def on_shutdown(self):
        carb.log_info("[omni.units_api] Extension shutdown")
        if self._inspector:
            self._inspector.destroy()
            self._inspector = None
        self._menu_entry = None

    def _register_menu(self):
        """Register Window > Units Inspector menu entry."""
        try:
            import omni.kit.ui
            editor_menu = omni.kit.ui.get_editor_menu()
            if editor_menu:
                self._menu_entry = editor_menu.add_item(
                    "Window/Units Inspector",
                    self._on_menu_click,
                    toggle=True,
                    value=False,
                )
        except (ImportError, AttributeError):
            # No menu system available (headless mode) — skip
            pass

    def _on_menu_click(self, *args):
        """Toggle the Units Inspector window."""
        if self._inspector is None:
            from .units_inspector import UnitsInspectorWindow
            self._inspector = UnitsInspectorWindow()
        else:
            self._inspector.destroy()
            self._inspector = None
