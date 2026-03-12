"""
modules.constants — 프로젝트 전역 상수 패키지.

주요 export:
    Region          — str Enum (KR/US/HK/JP/CN/VN)
    VALID_REGIONS   — List[str], argparse choices 등에 사용
    CURRENCY_MAP    — Dict[str, str], 리전 → 통화 코드
"""

from modules.constants.regions import Region, VALID_REGIONS, CURRENCY_MAP

__all__ = [
    'Region',
    'VALID_REGIONS',
    'CURRENCY_MAP',
]
