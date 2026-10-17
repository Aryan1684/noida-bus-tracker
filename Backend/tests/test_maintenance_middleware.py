import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import main


class MaintenanceMiddlewareTests(unittest.TestCase):
    def run_middleware(self, path, enabled=True):
        request = SimpleNamespace(url=SimpleNamespace(path=path))
        called = []

        async def call_next(_request):
            called.append(True)
            return SimpleNamespace(headers={})

        with patch.object(
            main,
            "get_cached_maintenance_settings",
            return_value={
                "enabled": enabled,
                "message": "Planned maintenance",
                "expires_at": 123456789,
            },
        ):
            response = asyncio.run(
                main.enforce_maintenance_and_disable_caching(request, call_next)
            )
        return response, called

    def test_blocks_analytics_during_maintenance(self):
        response, called = self.run_middleware("/api/analytics/event")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.body and b'"maintenance":true' in response.body, True)
        self.assertEqual(called, [])

    def test_blocks_location_sharing_during_maintenance(self):
        response, called = self.run_middleware("/api/analytics/location")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(called, [])

    def test_allows_public_maintenance_status(self):
        response, called = self.run_middleware("/api/maintenance")
        self.assertEqual(called, [True])

    def test_allows_admin_routes_to_disable_maintenance(self):
        response, called = self.run_middleware("/api/admin/maintenance")
        self.assertEqual(called, [True])

    def test_allows_feedback_during_maintenance(self):
        response, called = self.run_middleware("/api/feedback")
        self.assertEqual(called, [True])

    def test_allows_tracker_api_when_maintenance_is_off(self):
        response, called = self.run_middleware("/api/buses/nearby", enabled=False)
        self.assertEqual(called, [True])


if __name__ == "__main__":
    unittest.main()
