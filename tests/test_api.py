import unittest
from unittest.mock import AsyncMock

import httpx

from app import app


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.loader = AsyncMock()
        app.state.loader = self.loader
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        del app.state.loader

    async def test_health_does_not_contact_scraper(self):
        response = await self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "healthy")
        self.loader.load_timetable.assert_not_called()

    async def test_rejects_other_domains_before_loading(self):
        for url in ("https://example.com/", "https://everytime.kr.example.com/"):
            with self.subTest(url=url):
                response = await self.client.get("/timetable", params={"url": url})
                self.assertEqual(response.status_code, 400)
        self.loader.load_timetable.assert_not_called()

    async def test_timetable_returns_loader_result_and_failure_status(self):
        for result, status in (
            ({"success": True, "data": {"subjects": []}}, 200),
            ({"success": False, "message": "시간표 없음", "data": {}}, 400),
            ({"success": False, "message": "서버 오류", "data": {}}, 500),
        ):
            with self.subTest(status=status):
                self.loader.load_timetable.return_value = result
                response = await self.client.get(
                    "/timetable", params={"url": "https://everytime.kr/@sample"}
                )
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json(), result)
        self.loader.load_timetable.assert_awaited_with("https://everytime.kr/@sample")
