"""
EDINET Document List Cache

과거 날짜의 문서 목록을 캐싱하여 재조회 시 API 호출을 100% 절감합니다.

특징:
- JSON 파일 기반 캐시 (간단하고 이식성 높음)
- 과거 날짜: 영구 캐시 (문서 목록 변경 없음)
- 당월 날짜: 1시간 TTL (새 문서 제출 가능)
- 디스크 사용량: ~100MB/년 (일 평균 ~300KB)

Author: Quant Platform Development Team
Date: 2025-11-27
"""

import os
import json
import logging
import hashlib
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class EDINETDocumentCache:
    """
    EDINET 문서 목록 캐시 관리자

    일별 문서 목록을 JSON 파일로 캐싱하여 API 호출을 최소화합니다.

    사용 예시:
        cache = EDINETDocumentCache()

        # 캐시 조회 (없으면 None)
        docs = cache.get(date(2024, 6, 20))

        # 캐시 저장
        cache.set(date(2024, 6, 20), documents)

        # 통계
        stats = cache.get_stats()
        print(f"히트율: {stats['hit_rate']:.1%}")
    """

    DEFAULT_CACHE_DIR = "data/cache/edinet"
    CURRENT_MONTH_TTL_HOURS = 1  # 당월 데이터 TTL

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        enabled: bool = True
    ):
        """
        캐시 초기화

        Args:
            cache_dir: 캐시 디렉토리 경로 (기본: data/cache/edinet)
            enabled: 캐시 활성화 여부
        """
        self.enabled = enabled

        # 캐시 디렉토리 설정
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            # 프로젝트 루트 기준 기본 경로
            project_root = Path(__file__).parent.parent.parent
            self.cache_dir = project_root / self.DEFAULT_CACHE_DIR

        # 디렉토리 생성
        if self.enabled:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"EDINET 캐시 초기화: {self.cache_dir}")

        # 통계
        self._hits = 0
        self._misses = 0

    def _get_cache_path(self, target_date: date) -> Path:
        """날짜에 해당하는 캐시 파일 경로 반환"""
        # 연/월 디렉토리 구조: data/cache/edinet/2024/06/20.json
        year_month_dir = self.cache_dir / str(target_date.year) / f"{target_date.month:02d}"
        return year_month_dir / f"{target_date.day:02d}.json"

    def _is_expired(self, target_date: date, cache_path: Path) -> bool:
        """캐시 만료 여부 확인"""
        today = date.today()
        current_month = date(today.year, today.month, 1)
        target_month = date(target_date.year, target_date.month, 1)

        # 과거 월의 데이터는 영구 캐시
        if target_month < current_month:
            return False

        # 당월 데이터는 TTL 체크
        if not cache_path.exists():
            return True

        # 파일 수정 시간 확인
        mtime = datetime.fromtimestamp(cache_path.stat().st_mtime)
        ttl = timedelta(hours=self.CURRENT_MONTH_TTL_HOURS)

        return datetime.now() - mtime > ttl

    def get(self, target_date: date) -> Optional[List[Dict]]:
        """
        캐시에서 문서 목록 조회

        Args:
            target_date: 대상 날짜

        Returns:
            캐시된 문서 목록 또는 None (캐시 미스)
        """
        if not self.enabled:
            return None

        cache_path = self._get_cache_path(target_date)

        # 파일 존재 및 만료 체크
        if not cache_path.exists() or self._is_expired(target_date, cache_path):
            self._misses += 1
            return None

        try:
            with open(cache_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self._hits += 1
                logger.debug(f"캐시 히트: {target_date}")
                return data.get('documents', [])
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"캐시 읽기 실패 ({target_date}): {e}")
            self._misses += 1
            return None

    def set(self, target_date: date, documents: List[Dict]) -> bool:
        """
        문서 목록을 캐시에 저장

        Args:
            target_date: 대상 날짜
            documents: 문서 목록

        Returns:
            저장 성공 여부
        """
        if not self.enabled:
            return False

        cache_path = self._get_cache_path(target_date)

        try:
            # 디렉토리 생성
            cache_path.parent.mkdir(parents=True, exist_ok=True)

            # 메타데이터와 함께 저장
            data = {
                'date': target_date.isoformat(),
                'cached_at': datetime.now().isoformat(),
                'count': len(documents),
                'documents': documents
            }

            with open(cache_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=None)

            logger.debug(f"캐시 저장: {target_date} ({len(documents)}개 문서)")
            return True

        except IOError as e:
            logger.warning(f"캐시 저장 실패 ({target_date}): {e}")
            return False

    def get_or_fetch(
        self,
        target_date: date,
        fetch_func: callable
    ) -> List[Dict]:
        """
        캐시 조회 또는 API 호출 (캐시 관통 패턴)

        캐시에 있으면 반환, 없으면 fetch_func 호출 후 캐싱.

        Args:
            target_date: 대상 날짜
            fetch_func: API 호출 함수 (lambda: api.get_document_list(date))

        Returns:
            문서 목록
        """
        # 캐시 조회
        cached = self.get(target_date)
        if cached is not None:
            return cached

        # API 호출
        documents = fetch_func()

        # 캐시 저장
        self.set(target_date, documents)

        return documents

    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0

        # 캐시 디스크 사용량 계산
        total_size = 0
        file_count = 0
        if self.cache_dir.exists():
            for f in self.cache_dir.rglob('*.json'):
                total_size += f.stat().st_size
                file_count += 1

        return {
            'hits': self._hits,
            'misses': self._misses,
            'total': total,
            'hit_rate': hit_rate,
            'disk_usage_mb': total_size / (1024 * 1024),
            'file_count': file_count,
            'cache_dir': str(self.cache_dir),
            'enabled': self.enabled
        }

    def clear(self, before_date: Optional[date] = None) -> int:
        """
        캐시 정리

        Args:
            before_date: 이 날짜 이전의 캐시만 삭제 (None이면 전체 삭제)

        Returns:
            삭제된 파일 수
        """
        if not self.cache_dir.exists():
            return 0

        deleted = 0
        for cache_file in self.cache_dir.rglob('*.json'):
            try:
                # 날짜 추출 (경로: year/month/day.json)
                day = int(cache_file.stem)
                month = int(cache_file.parent.name)
                year = int(cache_file.parent.parent.name)
                file_date = date(year, month, day)

                if before_date is None or file_date < before_date:
                    cache_file.unlink()
                    deleted += 1

            except (ValueError, OSError) as e:
                logger.warning(f"캐시 파일 삭제 실패: {cache_file}: {e}")

        logger.info(f"캐시 정리 완료: {deleted}개 파일 삭제")
        return deleted

    def reset_stats(self):
        """통계 초기화"""
        self._hits = 0
        self._misses = 0


# 글로벌 캐시 인스턴스 (싱글톤 패턴)
_global_cache: Optional[EDINETDocumentCache] = None


def get_edinet_cache() -> EDINETDocumentCache:
    """
    글로벌 EDINET 캐시 인스턴스 반환

    Returns:
        EDINETDocumentCache 싱글톤 인스턴스
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = EDINETDocumentCache()
    return _global_cache


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("=" * 60)
    print("EDINET Document Cache 테스트")
    print("=" * 60)

    # 캐시 인스턴스 생성
    cache = EDINETDocumentCache()

    # 테스트 데이터
    test_date = date(2024, 6, 20)
    test_docs = [
        {'docID': 'S100TEST', 'docTypeCode': '120', 'secCode': '72030'},
        {'docID': 'S100TEST2', 'docTypeCode': '120', 'secCode': '99840'},
    ]

    # 캐시 저장
    print(f"\n1. 캐시 저장 테스트 ({test_date})")
    result = cache.set(test_date, test_docs)
    print(f"   저장 결과: {'성공' if result else '실패'}")

    # 캐시 조회
    print(f"\n2. 캐시 조회 테스트 ({test_date})")
    cached = cache.get(test_date)
    print(f"   조회 결과: {len(cached) if cached else 0}개 문서")

    # 캐시 미스 테스트
    print(f"\n3. 캐시 미스 테스트 ({date(2025, 1, 1)})")
    miss = cache.get(date(2025, 1, 1))
    print(f"   조회 결과: {miss}")

    # 통계 출력
    print("\n4. 캐시 통계")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)
