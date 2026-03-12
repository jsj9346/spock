"""
modules/log_config.py — 프로젝트 전역 로깅 설정 유틸리티

사용법:
    from modules.log_config import setup_file_logging

    setup_file_logging("log/my_script_20260312.log")

기본값:
    rotation  = 100 MB  (파일이 100MB 초과 시 자동 회전)
    retention = 30 days (30일 이상 된 파일 자동 삭제)
    compression = gz    (회전된 파일 gzip 압축)
"""

import os
import sys
from typing import Optional

from loguru import logger


# 기본 rotation/retention 정책
_DEFAULT_ROTATION = "100 MB"
_DEFAULT_RETENTION = "30 days"
_DEFAULT_COMPRESSION = "gz"
_DEFAULT_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{line} | {message}"
)


def setup_file_logging(
    log_path: str,
    level: str = "INFO",
    rotation: str = _DEFAULT_ROTATION,
    retention: str = _DEFAULT_RETENTION,
    compression: str = _DEFAULT_COMPRESSION,
    fmt: Optional[str] = None,
) -> None:
    """
    loguru 파일 싱크를 rotation/retention 정책과 함께 추가한다.

    Args:
        log_path:   로그 파일 경로 (디렉토리가 없으면 자동 생성)
        level:      최소 로그 레벨 (기본 INFO)
        rotation:   파일 회전 기준 (기본 "100 MB")
        retention:  파일 보존 기간 (기본 "30 days")
        compression: 회전 파일 압축 포맷 (기본 "gz")
        fmt:        로그 포맷 문자열 (기본값 사용 권장)
    """
    os.makedirs(os.path.dirname(log_path) if os.path.dirname(log_path) else ".", exist_ok=True)

    logger.add(
        log_path,
        level=level,
        format=fmt or _DEFAULT_FORMAT,
        rotation=rotation,
        retention=retention,
        compression=compression,
        encoding="utf-8",
        enqueue=True,   # 멀티스레드 안전 (비동기 큐 방식)
    )
