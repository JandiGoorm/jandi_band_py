from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
import re
import math
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
from threading import Lock
import logging
import os

@dataclass
class ScraperConfig:
    # 시간표 파싱 관련
    WAIT_TIMEOUT: int = 10000  # Playwright는 밀리초 단위
    TIME_UNIT_MINUTES: int = 30  # 시간 단위 (분)
    START_HOUR: int = 9         # 시작 시각
    BASE_TOP_OFFSET: int = 540  # 9시 시작점 픽셀
    PIXEL_PER_30MIN: int = 30   # 30분당 픽셀
    HEIGHT_ADJUSTMENT: int = 1  # 높이 계산시 보정값
    SUBJECT_CENTER_RATIO: float = 0.5  # subject 중앙점 계산 비율

    # CSS 선택자
    TABLE_HEAD_CLASS: str = ".tablehead"
    TABLE_BODY_CLASS: str = ".tablebody"
    SUBJECT_CLASS: str = ".subject"

    # Playwright 설정
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    timeout: int = 30000  # 30초

    # 요일 매핑 (한국어 → 영어)
    WEEKDAY_MAPPING: Dict[str, str] = None

    def __post_init__(self):
        if self.WEEKDAY_MAPPING is None:
            self.WEEKDAY_MAPPING = {
                "월": "Mon", "화": "Tue", "수": "Wed", "목": "Thu",
                "금": "Fri", "토": "Sat", "일": "Sun"
            }


class TimetableLoader:
    """ 1. 초기화 및 Public 인터페이스 """

    def __init__(self, config: ScraperConfig = None):
        self.config = config or ScraperConfig()
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        self._playwright = None
        self._browser_lock = Lock()
        self.logger = logging.getLogger(__name__)

    def load_timetable(self, url: str) -> Dict[str, Any]:
        try:
            page = self._get_page()
            page.goto(url)
            weekdays = self._load_weekdays(page)
            daily_schedules = self._load_subject_data(page, weekdays)

            if not daily_schedules:
                return self._build_response(
                    False, "공개되지 않은 시간표입니다."
                )

            available_times = {}
            for day, time_ranges in daily_schedules.items():
                merged_times = self._merge_time_slots(time_ranges)
                english_day = self.config.WEEKDAY_MAPPING.get(day, day)
                available_times[english_day] = merged_times

            # 전체 시간 집합에서 사용 가능한 시간을 제외한 여집합 계산
            timetable_data = self._calculate_unavailable_times(available_times)

            return self._build_response(
                True,
                "유저 시간표 불러오기 성공",
                {"timetableData": timetable_data}
            )

        except TimeoutError:
            self.logger.error(f"페이지 로딩 타임아웃: {url}")
            return self._build_response(False, "페이지 로딩 시간이 초과되었습니다.")

        except ValueError as e:
            self.logger.error(f"데이터 파싱 오류: {e}")
            return self._build_response(False, str(e))

        except Exception as e:
            self.logger.error(f"예상치 못한 오류: {e}")
            return self._build_response(False, f"서버 오류: {str(e)}")

    """ 2. 브라우저 관리 (생명주기) """

    def _get_page(self) -> Page:
        with self._browser_lock:
            if self._page is None:
                try:
                    self._playwright = sync_playwright().start()
                    self._browser = self._playwright.chromium.launch(
                        headless=self.config.headless
                    )
                    self._context = self._browser.new_context(
                        viewport={
                            'width': self.config.viewport_width,
                            'height': self.config.viewport_height
                        },
                        user_agent=self.config.user_agent
                    )

                    # 이미지와 폰트 차단 (CSS는 레이아웃 계산에 필요)
                    blocked_patterns = "**/*.{png,jpg,jpeg,gif,svg,woff,woff2,ttf}"
                    self._context.route(blocked_patterns, lambda route: route.abort())

                    self._page = self._context.new_page()
                    self._page.set_default_timeout(self.config.timeout)

                    self.logger.info("Playwright 인스턴스가 생성되었습니다.")

                except Exception as e:
                    self.logger.error(f"Playwright 생성 실패: {e}")
                    raise

            return self._page

    def close_browser(self):
        with self._browser_lock:
            if self._page:
                self._page.close()
                self._page = None
            if self._context:
                self._context.close()
                self._context = None
            if self._browser:
                self._browser.close()
                self._browser = None
            if self._playwright:
                self._playwright.stop()
                self._playwright = None
            self.logger.info("Playwright 브라우저가 종료되었습니다.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_browser()

    """ 3. 데이터 추출 (상위 레벨) """

    def _load_weekdays(self, page: Page) -> List[str]:
        try:
            page.wait_for_selector(
                self.config.TABLE_HEAD_CLASS,
                timeout=self.config.WAIT_TIMEOUT
            )
            td_elements = page.locator(f"{self.config.TABLE_HEAD_CLASS} td")
            days = []

            for i in range(td_elements.count()):
                text = td_elements.nth(i).text_content().strip()
                if text:
                    days.append(text)

            if not days:
                raise ValueError("요일 정보를 찾을 수 없습니다")

            return days

        except Exception as e:
            if "Timeout" in str(e):
                raise TimeoutError("시간표 헤더를 찾을 수 없습니다")
            raise

    def _load_subject_data(
        self, page: Page, weekdays: List[str]
    ) -> Dict[str, List[Tuple[str, str]]]:
        try:
            page.wait_for_selector(
                self.config.TABLE_BODY_CLASS,
                timeout=self.config.WAIT_TIMEOUT
            )
            subjects = page.locator(
                f"{self.config.TABLE_BODY_CLASS} {self.config.SUBJECT_CLASS}"
            )

            if subjects.count() == 0:
                raise ValueError("과목 요소를 찾을 수 없습니다")

        except Exception:
            raise ValueError("시간표 본문을 찾을 수 없습니다")

        daily_schedules = defaultdict(list)

        for i in range(subjects.count()):
            subject = subjects.nth(i)
            style = subject.get_attribute("style")
            time_data = self._parse_time_from_style(style)

            if not time_data:
                continue

            height, top = time_data
            start_time, end_time = self._calculate_time_range(height, top)
            day = self._find_subject_day(subject, weekdays, page)

            daily_schedules[day].append((start_time, end_time))

        return daily_schedules

    """ 4. 파싱 및 계산 (하위 레벨 헬퍼) """
    def _parse_time_from_style(self, style_str: str) -> Optional[Tuple[int, int]]:
        if not style_str:
            return None
            
        height_match = re.search(r'height:\s*(\d+)px', style_str)
        top_match = re.search(r'top:\s*(\d+)px', style_str)

        if not height_match or not top_match:
            return None

        height = int(height_match.group(1))
        top = int(top_match.group(1))

        return height, top

    def _pixels_to_time(self, pixels: int) -> str:
        offset_pixels = pixels - self.config.BASE_TOP_OFFSET
        time_slots = offset_pixels // self.config.PIXEL_PER_30MIN
        minutes = time_slots * self.config.TIME_UNIT_MINUTES

        hour = self.config.START_HOUR + (minutes // 60)
        minute = minutes % 60
        return f"{hour:02d}:{minute:02d}"

    def _calculate_duration_minutes(self, height: int) -> int:
        adjusted_height = height - self.config.HEIGHT_ADJUSTMENT
        time_slots = math.ceil(adjusted_height / self.config.PIXEL_PER_30MIN)
        return time_slots * self.config.TIME_UNIT_MINUTES

    def _calculate_time_range(self, height: int, top: int) -> Tuple[str, str]:
        start_time = self._pixels_to_time(top)
        duration_minutes = self._calculate_duration_minutes(height)

        offset_pixels = top - self.config.BASE_TOP_OFFSET
        time_slots = offset_pixels // self.config.PIXEL_PER_30MIN
        start_minutes = time_slots * self.config.TIME_UNIT_MINUTES

        end_total_minutes = start_minutes + duration_minutes
        end_hour = self.config.START_HOUR + (end_total_minutes // 60)
        end_minute = end_total_minutes % 60

        end_time = f"{end_hour:02d}:{end_minute:02d}"
        return start_time, end_time

    def _find_subject_day(self, subject_element, weekdays: List[str], page: Page) -> str:
        try:
            subject_rect = subject_element.bounding_box()
            if not subject_rect:
                return "알 수 없음"

            tablehead = page.locator(self.config.TABLE_HEAD_CLASS).first
            td_elements = tablehead.locator('td')

            subject_x = (
                subject_rect['x'] +
                subject_rect['width'] * self.config.SUBJECT_CENTER_RATIO
            )

            for i in range(td_elements.count()):
                td_rect = td_elements.nth(i).bounding_box()
                if (td_rect and
                    td_rect['x'] <= subject_x <= td_rect['x'] + td_rect['width']):
                    return weekdays[i] if i < len(weekdays) else "알 수 없음"

            return "알 수 없음"

        except Exception as e:
            self.logger.debug(f"요일 찾기 실패: {e}")
            return "알 수 없음"

    """ 5. 데이터 처리 (유틸리티) """
    def _merge_time_slots(self, time_ranges: List[Tuple[str, str]]) -> List[str]:
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
                current_m += self.config.TIME_UNIT_MINUTES
                if current_m >= 60:
                    current_h += 1
                    current_m = 0

        return sorted(merged_slots)

    def _generate_full_time_slots(self) -> List[str]:
        full_slots = []

        # 7시부터 23시30분까지 (실질적으로 24시 마감)
        start_hour = 7
        end_hour = 24

        current_hour = start_hour
        current_minute = 0

        while current_hour < end_hour:
            full_slots.append(f"{current_hour:02d}:{current_minute:02d}")
            current_minute += self.config.TIME_UNIT_MINUTES

            if current_minute >= 60:
                current_hour += 1
                current_minute = 0

        return full_slots

    def _calculate_unavailable_times(self, available_times: Dict[str, List[str]]) -> Dict[str, List[str]]:
        full_time_slots = set(self._generate_full_time_slots())
        unavailable_times = {}

        # 모든 요일에 대해 처리 (월~일)
        all_weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        for day in all_weekdays:
            available_set = set(available_times.get(day, []))
            unavailable_set = full_time_slots - available_set
            unavailable_times[day] = sorted(unavailable_set)

        return unavailable_times

    def _build_response(self, success: bool, message: str, data: Dict = None) -> Dict[str, Any]:
        response = {"success": success, "message": message}
        if data:
            response["data"] = data
        return response
