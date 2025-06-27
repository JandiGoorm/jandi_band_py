import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Any
from urllib.parse import urlparse

import httpx
from lxml import etree

logger = logging.getLogger(__name__)

START_HOUR = 7
END_HOUR = 24
DAY_MAPPING = {
    "0": "Mon", "1": "Tue", "2": "Wed", "3": "Thu",
    "4": "Fri", "5": "Sat", "6": "Sun"
}
ALL_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MINUTES_PER_OFFSET = 5
TIME_UNIT_MINUTES = 30
TIMEOUT = 30
MAX_RETRIES = 3


class TimetableLoader:
    BASE_URL = "https://api.everytime.kr"
    TIMETABLE_ENDPOINT = "/find/timetable/table/friend"

    _full_time_slots = None
    _instance = None
    _client = None

    def __new__(cls):
        """싱글톤 패턴 구현 - Lambda 컨테이너 재사용 시 동일한 인스턴스 사용"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def _initialize_full_time_slots(cls) -> set[str]:
        full_slots = []
        current_hour = START_HOUR
        current_minute = 0

        while current_hour < END_HOUR:
            full_slots.append(f"{current_hour:02d}:{current_minute:02d}")
            current_minute += TIME_UNIT_MINUTES
            if current_minute >= 60:
                current_hour += 1
                current_minute = 0
        return set(full_slots)

    @classmethod
    def get_full_time_slots(cls) -> set[str]:
        if cls._full_time_slots is None:
            cls._full_time_slots = cls._initialize_full_time_slots()
        return cls._full_time_slots

    def __init__(self):
        # 싱글톤이므로 중복 초기화 방지
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        logger.info("TimetableLoader 인스턴스 초기화")

    @property
    def client(self) -> httpx.AsyncClient:
        """지연 초기화된 HTTP 클라이언트"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=TIMEOUT)
            logger.info("HTTP 클라이언트 생성")
        return self._client

    async def close(self):
        """리소스 정리 - 로컬 환경에서만 필요"""
        if self._client and not self._client.is_closed:
            try:
                await self._client.aclose()
                logger.info("HTTP 클라이언트 정리 완료")
            except Exception as e:
                logger.error(f"HTTP 클라이언트 정리 중 오류: {e}")
            finally:
                self._client = None

    async def load_timetable(self, url: str) -> Dict[str, Any]:
        """(메인) 시간표 불러오기 함수"""
        try:
            # 입력받은 URL에서 identifier 추출
            identifier = self._extract_identifier_from_url(url)
            if not identifier:
                return self._build_response(
                    False, "유효하지 않은 URL입니다. identifier를 찾을 수 없습니다."
                )

            # 에브리타임 API를 호출해서 XML 시간표 데이터 가져오기
            xml_data = await self._get_timetable_data(identifier)
            if not xml_data:
                return self._build_response(
                    False, "시간표 데이터를 가져올 수 없습니다."
                )

            # XML 시간표 데이터를 파싱하여 시간표 정보 추출
            available_times = self._parse_timetable_xml(xml_data)
            if not available_times:
                return self._build_response(
                    False, "공개되지 않은 시간표입니다."
                )

            # 전체 시간 슬롯에서 사용 가능한 시간을 제외한 여집합 계산
            timetable_data = self._calc_unavailable_times(available_times)

            return self._build_response(
                True,
                "유저 시간표 불러오기 성공",
                {"timetableData": timetable_data}
            )

        except Exception as e:
            logger.error(f"시간표 로딩 중 예상치 못한 오류: {e}")
            return self._build_response(False, f"서버 오류: {str(e)}")

    def _extract_identifier_from_url(self, url: str) -> Optional[str]:
        try:
            parsed_url = urlparse(url)

            if 'everytime.kr' not in parsed_url.netloc:
                logger.warning(f"에브리타임 도메인이 아닙니다: {parsed_url.netloc}")
                return None

            path_parts = parsed_url.path.strip('/').split('/')
            if len(path_parts) >= 1 and path_parts[0].startswith('@') and len(path_parts[0]) > 1:
                return path_parts[0][1:]  # @ 제거하고 identifier 추출

            logger.warning(f"올바른 에브리타임 시간표 URL 형식이 아닙니다: {url}")
            return None

        except Exception as e:
            logger.error(f"URL에서 identifier 추출 실패: {e}")
            return None

    async def _get_timetable_data(self, identifier: str) -> Optional[str]:
        headers = {
            'accept': '*/*',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'user-agent': (
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/137.0.0.0 Safari/537.36'
            )
        }

        data = {
            'identifier': identifier,
            'friendInfo': 'true'
        }

        for attempt in range(MAX_RETRIES):
            try:
                # 동시성에 안전한 클라이언트 인스턴스 httpx.AsyncClient를 재사용함
                response = await self.client.post(
                    f"{self.BASE_URL}{self.TIMETABLE_ENDPOINT}",
                    headers=headers,
                    data=data
                )

                if response.status_code == 200:
                    return response.text
                else:
                    logger.warning(
                        f"API 호출 실패 (시도 {attempt + 1}): {response.status_code}"
                    )

            except httpx.TimeoutException:
                logger.warning(f"API 호출 타임아웃 (시도 {attempt + 1})")
            except Exception as e:
                logger.error(f"API 호출 중 오류 (시도 {attempt + 1}): {e}")

            if attempt < MAX_RETRIES - 1:
                await asyncio.sleep(1)

        return None

    def _parse_timetable_xml(self, xml_data: str) -> Dict[str, List[str]]:
        try:
            root = etree.fromstring(xml_data.encode('utf-8'))
            subjects = root.xpath('//table/subject')
            if not subjects:
                logger.warning("시간표에서 subject 요소를 찾을 수 없습니다")
                return {}

            schedules = defaultdict(set)  # 요일별 시간 슬롯 수집 (30분 단위)

            for subject in subjects:
                time_blocks = subject.xpath('.//time/data')  # 각각의 타임블록 찾기

                for timeblock in time_blocks:
                    day = timeblock.get('day')
                    if day not in DAY_MAPPING:
                        continue

                    start_time_minutes = int(timeblock.get('starttime', 0)) * MINUTES_PER_OFFSET
                    end_time_minutes = int(timeblock.get('endtime', 0)) * MINUTES_PER_OFFSET

                    # 분을 30분 단위로 내림 (에타 시간표가 30분 단위가 아니어서 꼬이는 것 대비)
                    hours = start_time_minutes // 60
                    mins = start_time_minutes % 60
                    current_minutes = hours * 60 if mins < 30 else hours * 60 + 30

                    temp_slots = []
                    while current_minutes < end_time_minutes:
                        slot_hours = current_minutes // 60
                        slot_minutes = current_minutes % 60
                        temp_slots.append(f"{slot_hours:02d}:{slot_minutes:02d}")
                        current_minutes += TIME_UNIT_MINUTES

                    schedules[DAY_MAPPING[day]].update(temp_slots)

            return {day: sorted(time_slots) for day, time_slots in schedules.items()}

        except etree.XMLSyntaxError as e:
            logger.error(f"XML 파싱 중 구문 오류: {e}")
            return {}
        except Exception as e:
            logger.error(f"XML 파싱 중 오류: {e}")
            return {}

    def _calc_unavailable_times(self, available_times: Dict[str, List[str]]) -> Dict[str, List[str]]:
        unavailable_times = {}
        full_time_slots = self.get_full_time_slots()

        for day in ALL_WEEKDAYS:
            available_set = set(available_times.get(day, []))
            unavailable_set = full_time_slots - available_set
            unavailable_times[day] = sorted(unavailable_set)

        return unavailable_times

    def _build_response(self, success: bool, message: str, data: Dict = None) -> Dict[str, Any]:
        response = {"success": success, "message": message}
        if data:
            response["data"] = data
        return response
