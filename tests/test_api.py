import unittest
import asyncio
from unittest.mock import AsyncMock, patch

import httpx

from app import app, ScrapeBudget


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.loader = AsyncMock()
        app.state.loader = self.loader
        app.state.scrape_budget = ScrapeBudget()
        self.client = httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        )

    async def asyncTearDown(self):
        await self.client.aclose()
        del app.state.loader
        del app.state.scrape_budget

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

    async def test_concurrent_limit_rejects_without_queueing_and_releases_slot(self):
        app.state.scrape_budget = ScrapeBudget(max_concurrent=1)
        entered, release = asyncio.Event(), asyncio.Event()
        async def slow_loader(_):
            entered.set()
            await release.wait()
            return {"success": True, "data": {}}
        self.loader.load_timetable.side_effect = slow_loader
        pending = asyncio.create_task(self.client.get('/timetable', params={'url': 'https://everytime.kr/@a'}))
        try:
            await asyncio.wait_for(entered.wait(), timeout=1)
            response = await self.client.get('/timetable', params={'url': 'https://everytime.kr/@b'})
            self.assertEqual(response.status_code, 429)
            self.assertEqual(response.headers['Retry-After'], '1')
            self.assertEqual((await self.client.get('/health')).status_code, 200)
            self.assertEqual(self.loader.load_timetable.await_count, 1)
        finally:
            release.set()
            self.assertEqual((await pending).status_code, 200)
        self.assertEqual((await self.client.get('/timetable', params={'url': 'https://everytime.kr/@c'})).status_code, 200)

    async def test_rate_window_rejects_and_recovers(self):
        self.loader.load_timetable.return_value = {'success': True, 'data': {}}
        with patch('app.monotonic', return_value=100) as clock:
            app.state.scrape_budget = ScrapeBudget(requests_per_minute=1)
            self.assertEqual((await self.client.get('/timetable', params={'url': 'https://everytime.kr/@a'})).status_code, 200)
            blocked = await self.client.get('/timetable', params={'url': 'https://everytime.kr/@b'})
            self.assertEqual(blocked.status_code, 429)
            self.assertEqual(blocked.headers['Retry-After'], '60')
            clock.return_value = 160
            self.assertEqual((await self.client.get('/timetable', params={'url': 'https://everytime.kr/@c'})).status_code, 200)
        self.assertEqual(self.loader.load_timetable.await_count, 2)

    async def test_failure_hides_exception_and_releases_capacity(self):
        app.state.scrape_budget = ScrapeBudget(max_concurrent=1)
        self.loader.load_timetable.side_effect = [RuntimeError('private connection details'), {'success': True, 'data': {}}]
        response = await self.client.get('/timetable', params={'url': 'https://everytime.kr/@a'})
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {'detail': '서버 오류'})
        self.assertEqual((await self.client.get('/timetable', params={'url': 'https://everytime.kr/@b'})).status_code, 200)
