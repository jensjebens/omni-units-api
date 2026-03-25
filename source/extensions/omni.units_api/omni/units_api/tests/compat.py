"""Compatibility shim: allow tests to run with either omni.kit.test or pytest.

When running inside Kit, omni.kit.test.AsyncTestCase is used natively.
When running standalone with pytest, we provide a minimal drop-in that
wraps async test methods into sync calls.
"""

try:
    import omni.kit.test
    AsyncTestCase = omni.kit.test.AsyncTestCase
except ImportError:
    import unittest
    import asyncio

    class AsyncTestCase(unittest.TestCase):
        """Minimal shim: runs async setUp/test/tearDown methods synchronously."""

        def _run_async(self, coro):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

        def setUp(self):
            # Check if subclass has async setUp
            setup = getattr(super(), 'setUp', None)
            if setup:
                setup()

        def tearDown(self):
            teardown = getattr(super(), 'tearDown', None)
            if teardown:
                teardown()

        @classmethod
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__(**kwargs)
            # Wrap async test methods
            for name in list(vars(cls)):
                method = getattr(cls, name)
                if asyncio.iscoroutinefunction(method):
                    if name == 'setUp':
                        cls._async_setUp = method
                        def sync_setUp(self, _m=method):
                            self._run_async(_m(self))
                        cls.setUp = sync_setUp
                    elif name == 'tearDown':
                        cls._async_tearDown = method
                        def sync_tearDown(self, _m=method):
                            self._run_async(_m(self))
                        cls.tearDown = sync_tearDown
                    elif name.startswith('test'):
                        def make_sync(m):
                            def sync_test(self):
                                self._run_async(m(self))
                            sync_test.__name__ = m.__name__
                            sync_test.__qualname__ = m.__qualname__
                            return sync_test
                        setattr(cls, name, make_sync(method))
