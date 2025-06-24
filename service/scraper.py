from playwright.async_api import async_playwright, Page, Browser, BrowserContext, Playwright
import re
import math
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import asyncio
import logging
import time
from contextlib import asynccontextmanager


@dataclass
class ContextInfo:
    context: BrowserContext
    is_permanent: bool
    last_used: float
    created_at: float


@dataclass
class ScraperConfig:
    initial_contexts: int = 2
    max_contexts: int = 10
    context_idle_timeout: int = 300

    headless: bool = True
    timeout: int = 15000

    WEEKDAY_MAPPING: Dict[str, str] = None

    def __post_init__(self):
        if self.WEEKDAY_MAPPING is None:
            self.WEEKDAY_MAPPING = {
                "월": "Mon", "화": "Tue", "수": "Wed", "목": "Thu",
                "금": "Fri", "토": "Sat", "일": "Sun"
            }


class BrowserManager:
    def __init__(self, config: ScraperConfig = None):
        self.config = config or ScraperConfig()
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

        self._context_infos: List[ContextInfo] = []
        self._available_contexts: asyncio.Queue = asyncio.Queue()
        self._lock = asyncio.Lock()

        self._cleanup_task: Optional[asyncio.Task] = None
        self._is_started = False

        self.logger = logging.getLogger(__name__)

    async def start_browser(self):
        async with self._lock:
            if self._is_started:
                return

            try:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(
                    headless=self.config.headless
                )

                for i in range(self.config.initial_contexts):
                    context = await self._create_context()
                    context_info = ContextInfo(
                        context=context,
                        is_permanent=True,
                        last_used=time.time(),
                        created_at=time.time()
                    )
                    self._context_infos.append(context_info)
                    await self._available_contexts.put(context_info)

                self._cleanup_task = asyncio.create_task(self._background_cleanup())

                self._is_started = True
                self.logger.info(f"Playwright 브라우저가 {self.config.initial_contexts}개의 영구 컨텍스트로 시작되었습니다")

            except Exception as e:
                self.logger.error(f"브라우저 시작 실패: {e}")
                await self._cleanup()
                raise

    async def close_browser(self):
        async with self._lock:
            if not self._is_started:
                return

            if self._cleanup_task:
                self._cleanup_task.cancel()
                try:
                    await self._cleanup_task
                except asyncio.CancelledError:
                    pass
                self._cleanup_task = None

            await self._cleanup()
            self._is_started = False
            self.logger.info("Playwright 브라우저가 중지되었습니다")

    async def _acquire_context(self) -> ContextInfo:
        # 1. 즉시 사용 가능한 컨텍스트 확인
        try:
            return self._available_contexts.get_nowait()
        except asyncio.QueueEmpty:
            pass

        # 2. 새 컨텍스트 생성 가능한지 확인
        if len(self._context_infos) < self.config.max_contexts:
            self.logger.info("컨텍스트 풀이 비어있음, 새 컨텍스트 즉시 생성")
            context = await self._create_context()
            context_info = ContextInfo(
                context=context,
                is_permanent=False,
                last_used=time.time(),
                created_at=time.time()
            )
            async with self._lock:
                self._context_infos.append(context_info)
            self.logger.info(f"새로운 임시 컨텍스트 생성됨. 풀 크기: {len(self._context_infos)}")
            return context_info

        # 3. 최대치 도달 시 대기
        self.logger.warning("최대 컨텍스트 수에 도달, 대기 중...")
        return await asyncio.wait_for(
            self._available_contexts.get(),
            timeout=2.0
        )

    async def _return_context(self, context_info: Optional[ContextInfo]):
        if context_info and context_info in self._context_infos:
            try:
                await self._available_contexts.put(context_info)
            except Exception as e:
                self.logger.warning(f"컨텍스트 풀 반환 중 오류: {e}")

    async def _close_page_safely(self, page: Optional[Page]):
        if page:
            try:
                await page.close()
            except Exception as e:
                self.logger.warning(f"페이지 종료 중 오류: {e}")

    @asynccontextmanager
    async def get_page(self):
        if not self._is_started:
            raise RuntimeError("Browser is not started. Call start_browser() first.")

        context_info = None
        page = None

        try:
            context_info = await self._acquire_context()

            if context_info is None or context_info.context is None:
                raise RuntimeError("브라우저 컨텍스트를 가져올 수 없습니다")

            context_info.last_used = time.time()
            page = await context_info.context.new_page()
            page.set_default_timeout(self.config.timeout)

            yield page

        except Exception as e:
            self.logger.error(f"get_page 중 오류: {e}")
            raise
        finally:
            await self._close_page_safely(page)
            await self._return_context(context_info)

    async def _create_context(self) -> BrowserContext:
        if not self._browser:
            raise RuntimeError("Browser is not started")

        context = await self._browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )

        try:
            # 파싱하는 데에 있어 불필요한 리소스는 차단
            blocked_patterns = [
                "**/*.{png,jpg,jpeg,gif,svg,ico,webp}",  # 이미지
                "**/*.{woff,woff2,ttf,otf,eot}",  # 폰트
                "**/analytics/**",  # 분석 도구
                "**/ads/**",  # 광고
                "**/tracking/**"  # 트래킹
            ]

            for pattern in blocked_patterns:
                await context.route(pattern, lambda route: route.abort())

        except Exception as e:
            self.logger.warning(f"리소스 차단 설정 실패: {e}")

        return context

    async def _background_cleanup(self):
        while True:
            try:
                await asyncio.sleep(60)
                await self._cleanup_idle_contexts()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"백그라운드 정리 중 오류: {e}")

    async def _cleanup_idle_contexts(self):
        async with self._lock:
            current_time = time.time()
            contexts_to_remove = []

            for context_info in self._context_infos:
                if context_info.is_permanent:
                    continue

                idle_time = current_time - context_info.last_used
                if idle_time > self.config.context_idle_timeout:
                    contexts_to_remove.append(context_info)

            for context_info in contexts_to_remove:
                try:
                    await context_info.context.close()
                    self._context_infos.remove(context_info)
                    self.logger.info(f"유휴 컨텍스트 제거됨. 풀 크기: {len(self._context_infos)}")
                except Exception as e:
                    self.logger.warning(f"유휴 컨텍스트 제거 중 오류: {e}")

            await self._clean_available_queue()

    async def _clean_available_queue(self):
        temp_queue = []

        while not self._available_contexts.empty():
            try:
                context_info = self._available_contexts.get_nowait()
                if context_info in self._context_infos:
                    temp_queue.append(context_info)
            except asyncio.QueueEmpty:
                break

        for context_info in temp_queue:
            await self._available_contexts.put(context_info)

    async def _cleanup(self):
        # 모든 컨텍스트 정리
        for context_info in self._context_infos:
            try:
                await context_info.context.close()
            except Exception as e:
                self.logger.warning(f"컨텍스트 종료 중 오류: {e}")

        self._context_infos.clear()

        # 큐 비우기
        while not self._available_contexts.empty():
            try:
                self._available_contexts.get_nowait()
            except asyncio.QueueEmpty:
                break

        # 브라우저 및 playwright 정리
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                self.logger.warning(f"브라우저 종료 중 오류: {e}")
            finally:
                self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                self.logger.warning(f"Playwright 중지 중 오류: {e}")
            finally:
                self._playwright = None


class TimetableLoader:
    """시간표 파싱 로직을 담당하는 클래스"""

    TABLE_HEAD_CLASS = ".tablehead"
    TABLE_BODY_CLASS = ".tablebody"
    SUBJECT_CLASS = ".subject"
    SUBJECT_CENTER_RATIO = 0.5

    def __init__(self, config: ScraperConfig = None):
        self.config = config or ScraperConfig()
        self.time_calc = TimeCalculator()
        self.response_builder = ResponseBuilder()
        self.logger = logging.getLogger(__name__)

    async def load_timetable(self, url: str, page: Page) -> Dict[str, Any]:
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=self.config.timeout)
            await page.wait_for_function(
                f"document.querySelector('{self.TABLE_HEAD_CLASS} td') && "
                f"document.querySelector('{self.TABLE_HEAD_CLASS} td').textContent.trim() !== '' && "
                f"document.querySelector('{self.TABLE_BODY_CLASS}')",
                timeout=10000
            )
            weekdays = await self._load_weekdays(page)
            daily_schedules = await self._load_subject_data(page, weekdays)

            if not daily_schedules:
                return self.response_builder.build_response(
                    False, "공개되지 않은 시간표입니다."
                )

            # 최종 스케줄 구성
            available_times = {}
            for day, time_ranges in daily_schedules.items():
                merged_times = self.time_calc.merge_time_slots(time_ranges)
                english_day = self.config.WEEKDAY_MAPPING.get(day, day)
                available_times[english_day] = merged_times

            timetable_data = self.time_calc.calculate_unavailable_times(available_times)

            return self.response_builder.build_response(
                True,
                "유저 시간표 불러오기 성공",
                {"timetableData": timetable_data}
            )

        except TimeoutError:
            self.logger.error(f"페이지 로딩 타임아웃: {url}")
            return self.response_builder.build_response(False, "페이지 로딩 시간이 초과되었습니다.")

        except ValueError as e:
            self.logger.error(f"데이터 파싱 오류: {e}")
            return self.response_builder.build_response(False, str(e))

        except Exception as e:
            self.logger.error(f"예상치 못한 오류: {e}")
            return self.response_builder.build_response(False, f"서버 오류: {str(e)}")

    async def _load_weekdays(self, page: Page) -> List[str]:
        try:
            td_elements = page.locator(f"{self.TABLE_HEAD_CLASS} td")
            days = []

            for i in range(await td_elements.count()):
                text_content = await td_elements.nth(i).text_content()
                text = text_content.strip() if text_content else ""
                if text:
                    days.append(text)

            if not days:
                raise ValueError("요일 정보를 찾을 수 없습니다")

            return days

        except Exception as e:
            if "Timeout" in str(e):
                raise TimeoutError("시간표 헤더를 찾을 수 없습니다")
            raise

    async def _load_subject_data(
        self, page: Page, weekdays: List[str]
    ) -> Dict[str, List[Tuple[str, str]]]:
        try:
            subjects = page.locator(f"{self.TABLE_BODY_CLASS} {self.SUBJECT_CLASS}")

            subject_count = await subjects.count()
            if subject_count == 0:
                self.logger.warning("과목 요소를 찾을 수 없지만, 빈 시간표일 수 있습니다.")
                return defaultdict(list)

        except Exception:
            raise ValueError("시간표 본문을 찾을 수 없습니다")

        daily_schedules = defaultdict(list)

        for i in range(await subjects.count()):
            subject = subjects.nth(i)
            style = await subject.get_attribute("style")
            time_data = self._parse_time_from_style(style)

            if not time_data:
                continue

            height, top = time_data
            start_time, end_time = self.time_calc.calculate_time_range(height, top)
            day = await self._find_subject_day(subject, weekdays, page)

            daily_schedules[day].append((start_time, end_time))

        return daily_schedules

    def _parse_time_from_style(self, style_str: Optional[str]) -> Optional[Tuple[int, int]]:
        if not style_str:
            return None

        height_match = re.search(r'height:\s*(\d+)px', style_str)
        top_match = re.search(r'top:\s*(\d+)px', style_str)

        if not height_match or not top_match:
            return None

        height = int(height_match.group(1))
        top = int(top_match.group(1))

        return height, top

    async def _find_subject_day(self, subject_element, weekdays: List[str], page: Page) -> str:
        try:
            subject_rect = await subject_element.bounding_box()
            if not subject_rect:
                return "알 수 없음"

            tablehead = page.locator(self.TABLE_HEAD_CLASS).first
            td_elements = tablehead.locator('td')

            subject_x = (
                    subject_rect['x'] +
                    subject_rect['width'] * self.SUBJECT_CENTER_RATIO
            )

            for i in range(await td_elements.count()):
                td_rect = await td_elements.nth(i).bounding_box()
                if td_rect and td_rect['x'] <= subject_x <= td_rect['x'] + td_rect['width']:
                    return weekdays[i] if i < len(weekdays) else "알 수 없음"

            return "알 수 없음"

        except Exception as e:
            self.logger.debug(f"요일 찾기 실패: {e}")
            return "알 수 없음"


class TimeCalculator:
    TIME_UNIT_MINUTES = 30
    START_HOUR = 9
    BASE_TOP_OFFSET = 540
    PIXEL_PER_30MIN = 30
    HEIGHT_ADJUSTMENT = 1

    def pixels_to_time(self, pixels: int) -> str:
        offset_pixels = pixels - self.BASE_TOP_OFFSET
        time_slots = offset_pixels // self.PIXEL_PER_30MIN
        minutes = time_slots * self.TIME_UNIT_MINUTES

        hour = self.START_HOUR + (minutes // 60)
        minute = minutes % 60
        return f"{hour:02d}:{minute:02d}"

    def calculate_time_range(self, height: int, top: int) -> Tuple[str, str]:
        """높이와 위치로부터 시작-종료 시간 계산"""
        start_time = self.pixels_to_time(top)

        adjusted_height = height - self.HEIGHT_ADJUSTMENT
        time_slots = math.ceil(adjusted_height / self.PIXEL_PER_30MIN)
        duration_minutes = time_slots * self.TIME_UNIT_MINUTES

        offset_pixels = top - self.BASE_TOP_OFFSET
        start_time_slots = offset_pixels // self.PIXEL_PER_30MIN
        start_minutes = start_time_slots * self.TIME_UNIT_MINUTES

        end_total_minutes = start_minutes + duration_minutes
        end_hour = self.START_HOUR + (end_total_minutes // 60)
        end_minute = end_total_minutes % 60

        end_time = f"{end_hour:02d}:{end_minute:02d}"
        return start_time, end_time

    def merge_time_slots(self, time_ranges: List[Tuple[str, str]]) -> List[str]:
        """시간 범위들을 병합하여 30분 단위 슬롯으로 변환"""
        if not time_ranges:
            return []

        time_ranges.sort()
        merged_slots = set()

        for start_str, end_str in time_ranges:
            start_h, start_m = map(int, start_str.split(":"))
            end_h, end_m = map(int, end_str.split(":"))

            current_h, current_m = start_h, start_m
            while (current_h, current_m) < (end_h, end_m):
                merged_slots.add(f"{current_h:02}:{current_m:02}")
                current_m += self.TIME_UNIT_MINUTES
                if current_m >= 60:
                    current_h += 1
                    current_m = 0

        return sorted(merged_slots)

    def generate_full_time_slots(self) -> List[str]:
        """전체 시간 집합 생성: 7시~23시30분 (30분 단위)"""
        full_slots = []
        start_hour, end_hour = 7, 24

        current_hour = start_hour
        current_minute = 0

        while current_hour < end_hour:
            full_slots.append(f"{current_hour:02d}:{current_minute:02d}")
            current_minute += self.TIME_UNIT_MINUTES

            if current_minute >= 60:
                current_hour += 1
                current_minute = 0

        return full_slots

    def calculate_unavailable_times(self, available_times: Dict[str, List[str]]) -> Dict[str, List[str]]:
        """전체 시간 집합에서 사용 가능한 시간을 제외한 여집합 계산"""
        full_time_slots = set(self.generate_full_time_slots())
        unavailable_times = {}

        all_weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        for day in all_weekdays:
            available_set = set(available_times.get(day, []))
            unavailable_set = full_time_slots - available_set
            unavailable_times[day] = sorted(unavailable_set)

        return unavailable_times


class ResponseBuilder:
    @staticmethod
    def build_response(success: bool, message: str, data: Dict = None) -> Dict[str, Any]:
        response = {"success": success, "message": message}
        if data:
            response["data"] = data
        return response


# 전역 브라우저 매니저 관리
_browser_manager: Optional[BrowserManager] = None
_manager_lock: Optional[asyncio.Lock] = None


async def get_browser_manager(config: ScraperConfig = None) -> BrowserManager:
    global _browser_manager, _manager_lock

    if _manager_lock is None:
        _manager_lock = asyncio.Lock()

    async with _manager_lock:
        if _browser_manager is None:
            _browser_manager = BrowserManager(config)
        return _browser_manager


async def cleanup_browser_manager():
    global _browser_manager, _manager_lock

    if _manager_lock is None:
        _manager_lock = asyncio.Lock()

    async with _manager_lock:
        if _browser_manager:
            await _browser_manager.close_browser()
            _browser_manager = None
