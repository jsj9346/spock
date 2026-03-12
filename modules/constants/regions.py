"""
Single Source of Truth for region/market constants.

모든 리전 관련 상수는 이 파일에서 import하여 사용한다.
새 리전 추가 시 이 파일만 수정하면 전체 코드베이스에 반영된다.

Usage:
    from modules.constants.regions import Region, VALID_REGIONS, CURRENCY_MAP
"""

from enum import StrEnum
from typing import Dict, List


class Region(StrEnum):
    """지원하는 시장 리전 코드.

    StrEnum 상속으로 기존 문자열 비교 코드와 완전 호환된다.
        region == 'KR'          → True  (Region.KR == 'KR')
        region in ['KR', 'US']  → True
        f"region={region}"      → "region=KR"
        str(region)             → "KR"
    """
    KR = 'KR'   # 한국 (Korea)
    US = 'US'   # 미국 (United States)
    HK = 'HK'   # 홍콩 (Hong Kong)
    JP = 'JP'   # 일본 (Japan)
    CN = 'CN'   # 중국 (China)
    VN = 'VN'   # 베트남 (Vietnam)


# 유효한 리전 코드 목록 (문자열). argparse choices 등에 직접 사용 가능.
VALID_REGIONS: List[str] = [r.value for r in Region]

# 리전별 기본 통화 코드
CURRENCY_MAP: Dict[str, str] = {
    Region.KR: 'KRW',   # 한국 원
    Region.US: 'USD',   # 미국 달러
    Region.HK: 'HKD',   # 홍콩 달러
    Region.JP: 'JPY',   # 일본 엔
    Region.CN: 'CNY',   # 중국 위안
    Region.VN: 'VND',   # 베트남 동
}
