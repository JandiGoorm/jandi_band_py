from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import re
import math
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from collections import defaultdict, OrderedDict
from threading import Lock
import logging
import os

# 설정 상수들
@dataclass
class TimetableConfig:
    """시간표 파싱 관련 설정"""
    WAIT_TIMEOUT: int = 10
    BASE_TOP_OFFSET: int = 450  # 9시 시작점 픽셀
    PIXEL_PER_30MIN: int = 25   # 30분당 픽셀
    TIME_UNIT_MINUTES: int = 30  # 시간 단위 (분)
    START_HOUR: int = 9         # 시작 시간

    # CSS 선택자
    TABLE_HEAD_CLASS: str = "tablehead"
    TABLE_BODY_CLASS: str = "tablebody"
    SUBJECT_CLASS: str = "subject"

    # 요일 매핑 (한국어 → 영어)
    WEEKDAY_MAPPING: Dict[str, str] = None

    def __post_init__(self):
        if self.WEEKDAY_MAPPING is None:
            self.WEEKDAY_MAPPING = {
                "월": "Mon",
                "화": "Tue",
                "수": "Wed",
                "목": "Thu",
                "금": "Fri",
                "토": "Sat",
                "일": "Sun"
            }

@dataclass
class WebDriverConfig:
    """WebDriver 설정"""
    headless: bool = True
    window_size: str = "1920x1080"
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def get_chromedriver_path(self) -> str:
        """크롬드라이버 경로를 찾아서 반환"""
        paths = ["/usr/bin/chromedriver", "/usr/local/bin/chromedriver"]
        for path in paths:
            if os.path.exists(path):
                return path
        # 둘 다 없으면 기본값 반환 (Docker 환경 우선)
        return "/usr/bin/chromedriver"

class TimetableLoader:
    """시간표 데이터 불러오기 클래스"""

    def __init__(self, config: TimetableConfig = None, driver_config: WebDriverConfig = None):
        self.config = config or TimetableConfig()
        self.driver_config = driver_config or WebDriverConfig()
        self._driver: Optional[webdriver.Chrome] = None
        self._driver_lock = Lock()
        self.logger = logging.getLogger(__name__)

    def _setup_chrome_options(self) -> Options:
        """Chrome 옵션 설정"""
        options = Options()
        options.add_argument("--disable-gpu")
        options.add_argument(f"--window-size={self.driver_config.window_size}")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        if self.driver_config.headless:
            options.add_argument("--headless")

        options.add_argument(f"user-agent={self.driver_config.user_agent}")
        return options

    def _get_driver(self) -> webdriver.Chrome:
        """WebDriver 인스턴스 획득 (싱글톤)"""
        with self._driver_lock:
            if self._driver is None:
                try:
                    service = Service(self.driver_config.get_chromedriver_path())
                    options = self._setup_chrome_options()
                    self._driver = webdriver.Chrome(service=service, options=options)
                    self.logger.info("WebDriver 인스턴스가 생성되었습니다.")
                except Exception as e:
                    self.logger.error(f"WebDriver 생성 실패: {e}")
                    raise
            return self._driver

    def _load_weekdays(self, driver: webdriver.Chrome) -> List[str]:
        """요일 정보 불러오기"""
        try:
            tablehead = WebDriverWait(driver, self.config.WAIT_TIMEOUT).until(
                EC.presence_of_element_located((By.CLASS_NAME, self.config.TABLE_HEAD_CLASS))
            )
            days = [td.text.strip() for td in tablehead.find_elements(By.TAG_NAME, "td") if td.text.strip()]

            if not days:
                raise ValueError("요일 정보를 찾을 수 없습니다")

            return days
        except TimeoutException:
            raise TimeoutException("시간표 헤더를 찾을 수 없습니다")

    def _parse_time_from_style(self, style_str: str) -> Optional[Tuple[int, int]]:
        """스타일 속성에서 시간 정보 파싱"""
        height_match = re.search(r'height:\s*(\d+)px', style_str)
        top_match = re.search(r'top:\s*(\d+)px', style_str)

        if not height_match or not top_match:
            return None

        height = int(height_match.group(1))
        top = int(top_match.group(1))

        return height, top

    def _calculate_time_range(self, height: int, top: int) -> Tuple[str, str]:
        """픽셀 정보를 시간 범위로 변환"""
        # 시작 시간 계산
        start_minutes = ((top - self.config.BASE_TOP_OFFSET) // self.config.PIXEL_PER_30MIN) * self.config.TIME_UNIT_MINUTES
        start_hour = self.config.START_HOUR + (start_minutes // 60)
        start_minute = start_minutes % 60

        # 종료 시간 계산
        duration_minutes = math.ceil((height - 1) / self.config.PIXEL_PER_30MIN) * self.config.TIME_UNIT_MINUTES
        end_total_minutes = start_minutes + duration_minutes
        end_hour = self.config.START_HOUR + (end_total_minutes // 60)
        end_minute = end_total_minutes % 60

        start_time = f"{int(start_hour):02}:{int(start_minute):02}"
        end_time = f"{int(end_hour):02}:{int(end_minute):02}"

        return start_time, end_time

    def _find_subject_day(self, subject_element, weekdays: List[str]) -> str:
        """과목이 속한 요일 찾기"""
        try:
            parent_td = subject_element.find_element(By.XPATH, "./ancestor::td")
            parent_row = parent_td.find_element(By.XPATH, "./ancestor::tr")
            all_tds = parent_row.find_elements(By.TAG_NAME, "td")
            td_index = list(all_tds).index(parent_td)

            return weekdays[td_index] if td_index < len(weekdays) else "알 수 없음"
        except (NoSuchElementException, IndexError):
            return "알 수 없음"

    def _load_subject_data(self, driver: webdriver.Chrome, weekdays: List[str]) -> Dict[str, List[Tuple[str, str]]]:
        """과목 데이터 불러오기"""
        try:
            tablebody = driver.find_element(By.CLASS_NAME, self.config.TABLE_BODY_CLASS)
            subjects = tablebody.find_elements(By.CLASS_NAME, self.config.SUBJECT_CLASS)
        except NoSuchElementException:
            raise ValueError("시간표 본문을 찾을 수 없습니다")

        daily_schedules = defaultdict(list)

        for subject in subjects:
            style = subject.get_attribute("style")
            time_data = self._parse_time_from_style(style)

            if not time_data:
                continue

            height, top = time_data
            start_time, end_time = self._calculate_time_range(height, top)
            day = self._find_subject_day(subject, weekdays)

            daily_schedules[day].append((start_time, end_time))

        return daily_schedules

    def _merge_time_slots(self, time_ranges: List[Tuple[str, str]]) -> List[str]:
        """연속된 시간 슬롯 병합"""
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

    def _build_response(self, success: bool, message: str, data: Dict = None) -> Dict[str, Any]:
        """응답 데이터 구성"""
        if data:
            response = OrderedDict([
                ("success", success),
                ("message", message),
                ("data", data)
            ])
        else:
            response = OrderedDict([
                ("success", success),
                ("message", message)
            ])
        return response

    def load_timetable(self, url: str) -> Dict[str, Any]:
        """메인 시간표 불러오기 메서드"""
        try:
            driver = self._get_driver()
            driver.get(url)

            # 요일 정보 불러오기
            weekdays = self._load_weekdays(driver)

            # 과목 데이터 불러오기
            daily_schedules = self._load_subject_data(driver, weekdays)

            if not daily_schedules:
                return self._build_response(
                    False, "공개되지 않은 시간표입니다."
                )

            # 최종 스케줄 구성
            timetable_data = {}
            for day, time_ranges in daily_schedules.items():
                merged_times = self._merge_time_slots(time_ranges)
                english_day = self.config.WEEKDAY_MAPPING.get(day, day)
                timetable_data[english_day] = merged_times

            return self._build_response(
                True,
                "유저 시간표 불러오기 성공",
                {"timetableData": timetable_data}
            )

        except TimeoutException:
            self.logger.error(f"페이지 로딩 타임아웃: {url}")
            return self._build_response(False, "페이지 로딩 시간이 초과되었습니다.")

        except ValueError as e:
            self.logger.error(f"데이터 파싱 오류: {e}")
            return self._build_response(False, str(e))

        except Exception as e:
            self.logger.error(f"예상치 못한 오류: {e}")
            return self._build_response(False, f"서버 오류: {str(e)}")

    def close_driver(self):
        """WebDriver 종료"""
        with self._driver_lock:
            if self._driver:
                self._driver.quit()
                self._driver = None
                self.logger.info("WebDriver가 종료되었습니다.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_driver()
