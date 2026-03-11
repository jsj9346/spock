import time
from functools import wraps
import re
# import psycopg2  # PostgreSQL 의존성 제거 - SQLite 사용
import os
from dotenv import load_dotenv
import functools
import requests
from datetime import datetime, date, timedelta
from typing import Dict, Optional
import logging
import sys
import json
import pytz
import pandas as pd
import psutil

# Import optimized monitor (commented out - module deleted)
# from optimized_data_monitor import get_optimized_monitor

# === 전역 변수 초기화 ===
_conversion_stats = {
    "total_calls": 0,
    "successful_conversions": 0,
    "conversion_failures": 0,
    "datetime_detections": 0
}

def safe_strftime(date_obj, format_str='%Y-%m-%d'):
    """
    안전한 datetime 변환 유틸리티 함수
    
    조건부 처리:
    - pd.Timestamp인 경우: 직접 strftime 사용
    - pd.DatetimeIndex인 경우: 직접 strftime 사용
    - 정수형인 경우: pd.to_datetime()으로 변환 후 strftime
    - None/NaN인 경우: 기본값 반환
    
    Args:
        date_obj: 변환할 날짜 객체 (datetime, pd.Timestamp, int, str 등)
        format_str (str): 날짜 포맷 문자열 (기본값: '%Y-%m-%d')
        
    Returns:
        str: 포맷된 날짜 문자열 또는 기본값
    """
    try:
        # None 또는 NaN 체크
        if date_obj is None or (hasattr(date_obj, 'isna') and date_obj.isna()):
            return "N/A"
        
        # pandas NaT 체크
        if pd.isna(date_obj):
            return "N/A"
        
        # 빈 문자열 체크
        if isinstance(date_obj, str) and date_obj.strip() == "":
            return "N/A"
        
        # 리스트, 튜플, 딕셔너리 등 컨테이너 타입 체크
        if isinstance(date_obj, (list, tuple, dict)):
            return str(date_obj)
        
        # pandas Timestamp 객체인 경우 (우선 처리)
        if isinstance(date_obj, pd.Timestamp):
            return date_obj.strftime(format_str)
        
        # pandas DatetimeIndex 요소인 경우
        if hasattr(date_obj, '__class__') and 'pandas' in str(type(date_obj)):
            try:
                # pandas datetime-like 객체 처리
                return pd.Timestamp(date_obj).strftime(format_str)
            except (TypeError, ValueError):
                pass
            
        # 이미 datetime 객체이거나 strftime 메서드가 있는 경우
        if hasattr(date_obj, 'strftime'):
            return date_obj.strftime(format_str)
            
        # 정수형인 경우 (timestamp)
        if isinstance(date_obj, (int, float)):
            # Unix timestamp로 가정하고 변환 (나노초도 고려)
            if date_obj > 1e15:  # 나노초 timestamp
                dt = pd.to_datetime(date_obj, unit='ns')
            elif date_obj > 1e10:  # 밀리초 timestamp
                dt = pd.to_datetime(date_obj, unit='ms')
            else:  # 초 timestamp
                dt = pd.to_datetime(date_obj, unit='s')
            return dt.strftime(format_str)
            
        # 문자열인 경우
        if isinstance(date_obj, str):
            # 빈 문자열 재확인
            if date_obj.strip() == "":
                return "N/A"
            # 이미 포맷된 문자열이면 그대로 반환
            if len(date_obj) >= 10 and '-' in date_obj:
                return date_obj[:10]  # YYYY-MM-DD 부분만 추출
            # 그렇지 않으면 datetime으로 변환 시도
            dt = pd.to_datetime(date_obj)
            return dt.strftime(format_str)
            
        # 기타 경우: pandas to_datetime으로 변환 시도
        dt = pd.to_datetime(date_obj)
        return dt.strftime(format_str)
        
    except Exception as e:
        # 디버깅을 위한 상세한 로그
        logger.debug(f"safe_strftime 변환 실패 - 입력값: {date_obj} (타입: {type(date_obj)}), 오류: {e}")
        
        # 모든 변환이 실패한 경우 문자열로 변환하여 반환
        try:
            result = str(date_obj)
            if result == "":
                return "N/A"
            return result[:10] if len(result) >= 10 else result
        except (ValueError, TypeError, OverflowError):
            return "Invalid Date"

def retry(max_attempts=3, initial_delay=0.5, backoff=2):
    """
    Decorator to retry a function on exception.
    :param max_attempts: maximum number of attempts (including first)
    :param initial_delay: initial wait time between retries
    :param backoff: multiplier for successive delays
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts:
                        raise
                    time.sleep(delay)
                    delay *= backoff
        return wrapper
    return decorator

def compute_expected_phase(data):
    """
    Stan Weinstein Market Phases 룰을 부분적으로 구현한 간략화 로직.
    :param data: dict with keys 'current_price', 'ma_50', 'ma_200', 'volume_change_7_30', 'r1', 'r2', 'r3', 's1'
    :return: int Phase number (1 to 4)
    """
    cp = float(data.get("current_price", 0))
    ma50 = float(data.get("ma_50", 0))
    ma200 = float(data.get("ma_200", 0))
    vol_chg = float(data.get("volume_change_7_30", 0))
    r1, r2, r3 = map(float, (data.get("r1", 0), data.get("r2", 0), data.get("r3", 0)))
    s1 = float(data.get("s1", 0))

    # Stage 4: 명백한 하락추세 (MA-50 < MA-200 및 가격 < MA-50)
    if ma50 < ma200 and cp < ma50:
        return 4
    # Stage 3: 정점권 (고점 근처 + 거래량 감소)
    if cp >= r3 and vol_chg < 0:
        return 3
    # Stage 2: 상승추세 (MA 배열 + 거래량 증가 + 가격 > MA-50)
    if ma50 > ma200 and vol_chg > 0 and cp > ma50:
        return 2
    # Stage 1: 횡보권 (S1~R1 구간, MA 평탄, 거래량 평이)
    if s1 <= cp <= r1 and abs(ma50 - ma200) < (ma200 * 0.01) and abs(vol_chg) < 0.05:
        return 1
    # 기본적으로 Stage 1으로 반환
    return 1


def validate_and_correct_phase(ticker, reported_phase, data, reason):
    """
    reported_phase: string like "Stage 2"
    :param ticker: str
    :param reported_phase: str
    :param data: dict of analysis data passed to GPT
    :param reason: original reason string from GPT
    :return: (corrected_phase_str, corrected_reason)
    """
    m = re.search(r'\d+', reported_phase or "")
    reported = int(m.group()) if m else None
    expected = compute_expected_phase(data)
    if reported is not None and reported != expected:
        print(f"⚠️ GPT hallucination for {ticker}: reported Stage {reported}, expected Stage {expected}")
        corrected = f"Stage {expected}"
        corrected_reason = f"{reason} | Phase forced to Stage {expected} by rule-based check"
        return corrected, corrected_reason
    return reported_phase, reason

# === 공통 상수 ===
MIN_KRW_ORDER = 10000  # 최소 매수 금액
MIN_KRW_SELL_ORDER = 5000  # 최소 매도 금액
TAKER_FEE_RATE = 0.00139  # 업비트 KRW 마켓 Taker 수수료

# === 환경변수 로딩 ===
def load_env():
    load_dotenv()

# === DB 연결 함수 ===
# PostgreSQL 함수는 SQLite 마이그레이션으로 인해 사용 중단
# def get_db_connection():
#     return psycopg2.connect(
#         host=os.getenv("PG_HOST"),
#         port=os.getenv("PG_PORT"),
#         dbname=os.getenv("PG_DATABASE"),
#         user=os.getenv("PG_USER"),
#         password=os.getenv("PG_PASSWORD")
#     )

# SQLite용 DB 연결 - db_manager_sqlite.py 사용 권장
def get_db_connection():
    """
    레거시 호환성을 위한 더미 함수
    실제로는 db_manager_sqlite.py의 get_db_connection_context() 사용 권장
    """
    import sqlite3
    return sqlite3.connect('./data/spock_local.db')

def setup_logger():
    """
    로깅 설정을 초기화하고 로거를 반환합니다.
    
    Returns:
        logging.Logger: 설정된 로거 객체
    """
    log_dir = "log"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    log_filename = safe_strftime(datetime.now(), "%Y%m%d") + "_spock.log"
    log_file_path = os.path.join(log_dir, log_filename)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 기존 핸들러 삭제
    if logger.hasHandlers():
        logger.handlers.clear()

    # 스트림 핸들러 (터미널 출력)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(stream_handler)

    # 파일 핸들러 (파일 저장)
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)

    return logger

def setup_restricted_logger(logger_name: str = None):
    """
    제한된 로깅 설정을 초기화하고 로거를 반환합니다.
    특정 로그 파일 생성 제한을 적용합니다.

    Args:
        logger_name (str): 로거 이름 (None이면 기본 로거)

    Returns:
        logging.Logger: 설정된 로거 객체
    """
    log_dir = "log"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # 제한된 로그 파일명 (spock.log만 생성)
    log_filename = safe_strftime(datetime.now(), "%Y%m%d") + "_spock.log"
    log_file_path = os.path.join(log_dir, log_filename)

    log_format = "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"

    # 로거 생성
    if logger_name:
        logger = logging.getLogger(logger_name)
    else:
        logger = logging.getLogger()

    logger.setLevel(logging.INFO)

    # 🔧 중복 로깅 방지: propagation 비활성화
    if logger_name:
        logger.propagate = False

    # 기존 핸들러 삭제
    if logger.hasHandlers():
        logger.handlers.clear()

    # 스트림 핸들러 (터미널 출력)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(stream_handler)

    # 파일 핸들러 (spock.log만 사용)
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(log_format))
    logger.addHandler(file_handler)

    return logger

def cleanup_old_log_files(retention_days: int = 7):
    """
    지정된 보관 기간을 초과한 로그 파일들을 삭제합니다.
    
    Args:
        retention_days (int): 로그 파일 보관 기간 (일)
    
    Returns:
        dict: 정리 결과 정보
    """
    try:
        log_dir = "log"
        if not os.path.exists(log_dir):
            return {"status": "success", "message": "로그 디렉토리가 존재하지 않음", "deleted_count": 0}
        
        # 현재 시간 기준으로 보관 기간 계산
        cutoff_date = datetime.now() - timedelta(days=retention_days)
        deleted_count = 0
        error_count = 0
        
        # 로그 디렉토리의 모든 파일 검사
        for filename in os.listdir(log_dir):
            file_path = os.path.join(log_dir, filename)
            
            # 파일인지 확인
            if not os.path.isfile(file_path):
                continue
            
            try:
                # 파일 생성 시간 확인
                file_creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
                
                # 보관 기간을 초과한 파일 삭제
                if file_creation_time < cutoff_date:
                    os.remove(file_path)
                    deleted_count += 1
                    print(f"🗑️ 오래된 로그 파일 삭제: {filename}")
                    
            except Exception as e:
                error_count += 1
                print(f"⚠️ 로그 파일 삭제 중 오류 ({filename}): {e}")
        
        result = {
            "status": "success",
            "deleted_count": deleted_count,
            "error_count": error_count,
            "retention_days": retention_days,
            "cutoff_date": cutoff_date.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        if deleted_count > 0:
            print(f"✅ 로그 파일 정리 완료: {deleted_count}개 파일 삭제")
        else:
            print(f"ℹ️ 삭제할 오래된 로그 파일이 없습니다 (보관기간: {retention_days}일)")
            
        return result
        
    except Exception as e:
        error_result = {
            "status": "error",
            "message": f"로그 파일 정리 중 오류: {str(e)}",
            "deleted_count": 0,
            "error_count": 1
        }
        print(f"❌ 로그 파일 정리 실패: {e}")
        return error_result

def get_log_file_info():
    """
    현재 로그 디렉토리의 파일 정보를 반환합니다.
    
    Returns:
        dict: 로그 파일 정보
    """
    try:
        log_dir = "log"
        if not os.path.exists(log_dir):
            return {"status": "error", "message": "로그 디렉토리가 존재하지 않음"}
        
        log_files = []
        total_size = 0
        
        for filename in os.listdir(log_dir):
            file_path = os.path.join(log_dir, filename)
            
            if os.path.isfile(file_path):
                file_size = os.path.getsize(file_path)
                file_creation_time = datetime.fromtimestamp(os.path.getctime(file_path))
                
                log_files.append({
                    "filename": filename,
                    "size_bytes": file_size,
                    "size_mb": round(file_size / (1024 * 1024), 2),
                    "creation_time": file_creation_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "age_days": (datetime.now() - file_creation_time).days
                })
                
                total_size += file_size
        
        # 파일 크기순으로 정렬
        log_files.sort(key=lambda x: x["size_bytes"], reverse=True)
        
        return {
            "status": "success",
            "total_files": len(log_files),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "files": log_files
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "message": f"로그 파일 정보 조회 중 오류: {str(e)}"
        }

# 로거 초기화
logger = setup_logger()

# === 현재가 안전 조회 ===
def get_current_price_safe(ticker, retries=3, delay=0.3):
    """
    Stock market version - Uses KIS API instead of pyupbit

    Args:
        ticker: Stock ticker code (e.g., '005930' for Samsung Electronics)
        retries: Number of retry attempts
        delay: Delay between retries in seconds

    Returns:
        float: Current price of the stock
    """
    import time
    from modules.market_adapters import KoreaAdapter

    attempt = 0
    adapter = KoreaAdapter()

    while attempt < retries:
        try:
            price_data = adapter.get_current_price(ticker)
            if price_data is None:
                raise ValueError("No data returned")
            if isinstance(price_data, (int, float)):
                return price_data
            if isinstance(price_data, dict):
                if ticker in price_data:
                    return price_data[ticker]
                elif 'trade_price' in price_data:
                    return price_data['trade_price']
                else:
                    first_val = next(iter(price_data.values()), None)
                    if first_val is not None:
                        return first_val
            elif isinstance(price_data, list) and len(price_data) > 0:
                trade_price = price_data[0].get('trade_price')
                if trade_price is not None:
                    return trade_price
            raise ValueError(f"Unexpected data format: {price_data}")
        except Exception as e:
            logging.warning(f"❌ {ticker} 현재가 조회 중 예외 발생: {e}")
            attempt += 1
            time.sleep(delay)
    return None

def retry_on_error(max_retries=3, delay=5):
    """에러 발생 시 재시도하는 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(f"❌ 최대 재시도 횟수 초과: {str(e)}")
                        raise
                    logger.warning(f"⚠️ 재시도 중... ({attempt + 1}/{max_retries})")
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

def handle_api_error(e, context=""):
    """API 관련 에러를 처리하고 로깅합니다."""
    logger.error(f"❌ API 에러 발생 ({context}): {str(e)}")
    if hasattr(e, 'response'):
        logger.error(f"응답 상태: {e.response.status_code}")
        logger.error(f"응답 내용: {e.response.text}")

def handle_db_error(e, context=""):
    """DB 관련 에러를 처리하고 로깅합니다."""
    logger.error(f"❌ DB 에러 발생 ({context}): {str(e)}")

def handle_network_error(e, context=""):
    """네트워크 관련 에러를 처리하고 로깅합니다."""
    logger.error(f"❌ 네트워크 에러 발생 ({context}): {str(e)}")

def load_blacklist():
    """블랙리스트를 로드합니다. (에러 처리 강화)"""
    try:
        blacklist_path = 'blacklist.json'
        
        # 파일 존재 여부 확인
        if not os.path.exists(blacklist_path):
            logger.warning(f"⚠️ 블랙리스트 파일이 존재하지 않습니다: {blacklist_path}")
            # 빈 블랙리스트 파일 생성
            try:
                with open(blacklist_path, 'w', encoding='utf-8') as f:
                    json.dump({}, f, ensure_ascii=False, indent=2)
                logger.info(f"✅ 빈 블랙리스트 파일 생성 완료: {blacklist_path}")
                return {}
            except Exception as create_e:
                logger.error(f"❌ 블랙리스트 파일 생성 실패: {create_e}")
                return {}
        
        # 파일 읽기 권한 확인
        if not os.access(blacklist_path, os.R_OK):
            logger.error(f"❌ 블랙리스트 파일 읽기 권한 없음: {blacklist_path}")
            return {}
        
        # 파일 크기 확인
        file_size = os.path.getsize(blacklist_path)
        if file_size == 0:
            logger.warning(f"⚠️ 블랙리스트 파일이 비어있습니다: {blacklist_path}")
            return {}
        
        # JSON 파일 로드
        with open(blacklist_path, 'r', encoding='utf-8') as f:
            blacklist_data = json.load(f)
        
        # 데이터 타입 검증
        if not isinstance(blacklist_data, dict):
            logger.error(f"❌ 블랙리스트 파일 형식 오류: dict 타입이 아님 (현재: {type(blacklist_data)})")
            return {}
        
        # 블랙리스트 내용 검증
        valid_blacklist = {}
        invalid_entries = []
        
        for ticker, info in blacklist_data.items():
            # 티커 형식 검증
            if not isinstance(ticker, str) or not ticker.startswith('KRW-'):
                invalid_entries.append(f"{ticker}: 잘못된 티커 형식")
                continue
            
            # 정보 구조 검증
            if isinstance(info, dict):
                if 'reason' in info and 'added' in info:
                    valid_blacklist[ticker] = info
                else:
                    # 구조가 불완전한 경우 기본값으로 보완
                    valid_blacklist[ticker] = {
                        'reason': info.get('reason', '사유 없음'),
                        'added': info.get('added', datetime.now().isoformat())
                    }
                    logger.warning(f"⚠️ {ticker} 블랙리스트 정보 불완전, 기본값으로 보완")
            elif isinstance(info, str):
                # 구버전 호환성 (사유만 문자열로 저장된 경우)
                valid_blacklist[ticker] = {
                    'reason': info,
                    'added': datetime.now().isoformat()
                }
                logger.info(f"🔄 {ticker} 블랙리스트 구버전 형식 변환")
            else:
                invalid_entries.append(f"{ticker}: 잘못된 정보 형식")
        
        # 잘못된 항목 로그
        if invalid_entries:
            logger.warning(f"⚠️ 블랙리스트 잘못된 항목 {len(invalid_entries)}개 발견:")
            for entry in invalid_entries[:5]:  # 최대 5개만 표시
                logger.warning(f"   - {entry}")
            if len(invalid_entries) > 5:
                logger.warning(f"   - ... 외 {len(invalid_entries) - 5}개 더")
        
        # 성공 로그
        logger.info(f"✅ 블랙리스트 로드 완료: {len(valid_blacklist)}개 항목 (유효: {len(valid_blacklist)}, 무효: {len(invalid_entries)})")
        
        return valid_blacklist
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ 블랙리스트 JSON 파싱 오류: {e}")
        logger.error(f"   파일 위치: {os.path.abspath('blacklist.json')}")
        
        # 백업 파일 생성 시도
        try:
            backup_path = f"blacklist_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            import shutil
            shutil.copy2('blacklist.json', backup_path)
            logger.info(f"📋 손상된 블랙리스트 파일 백업 완료: {backup_path}")
        except Exception as backup_e:
            logger.error(f"❌ 백업 파일 생성 실패: {backup_e}")
        
        return {}
        
    except PermissionError as e:
        logger.error(f"❌ 블랙리스트 파일 접근 권한 오류: {e}")
        return {}
        
    except Exception as e:
        logger.error(f"❌ 블랙리스트 로드 중 예상치 못한 오류: {e}")
        logger.error(f"   파일 위치: {os.path.abspath('blacklist.json')}")
        
        # 상세 디버깅 정보
        try:
            import traceback
            logger.debug(f"🔍 상세 오류 정보:\n{traceback.format_exc()}")
        except (IOError, json.JSONDecodeError):
            pass
        
        return {}

# === UNUSED: 블랙리스트 관리 함수들 ===
# def add_to_blacklist(ticker: str, reason: str) -> bool:
#     """
#     블랙리스트에 티커를 추가합니다.
#     
#     Args:
#         ticker (str): 추가할 티커
#         reason (str): 추가 사유
#         
#     Returns:
#         bool: 성공 여부
#     """
#     try:
#         blacklist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "blacklist.json")
#         blacklist = load_blacklist()
#         
#         # 현재 UTC 시간
#         now = datetime.now(pytz.UTC)
#         
#         # 티커 추가
#         blacklist[ticker] = {
#             "reason": reason,
#             "added": now.isoformat()
#         }
#         
#         # JSON 파일 저장
#         with open(blacklist_path, 'w', encoding='utf-8') as f:
#             json.dump(blacklist, f, ensure_ascii=False, indent=2)
#             
#         logger.info(f"✅ {ticker} 블랙리스트 추가 완료 (사유: {reason})")
#         return True
#         
#     except Exception as e:
#         logger.error(f"❌ {ticker} 블랙리스트 추가 중 오류 발생: {e}")
#         return False

# def remove_from_blacklist(ticker: str) -> bool:
#     """
#     블랙리스트에서 티커를 제거합니다.
#     
#     Args:
#         ticker (str): 제거할 티커
#         
#     Returns:
#         bool: 성공 여부
#     """
#     try:
#         blacklist_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "blacklist.json")
#         blacklist = load_blacklist()
#         
#         if ticker not in blacklist:
#             logger.warning(f"⚠️ {ticker}는 블랙리스트에 없습니다.")
#             return False
#             
#         # 티커 제거
#         del blacklist[ticker]
#         
#         # JSON 파일 저장
#         with open(blacklist_path, 'w', encoding='utf-8') as f:
#             json.dump(blacklist, f, ensure_ascii=False, indent=2)
#             
#         logger.info(f"✅ {ticker} 블랙리스트 제거 완료")
#         return True
#         
#     except Exception as e:
#         logger.error(f"❌ {ticker} 블랙리스트 제거 중 오류 발생: {e}")
#         return False

# === 테이블 스키마 매핑 정규화 ===
COLUMN_MAPPING = {
    'static_indicators': {
        # 피벗 포인트 매핑
        'resistance_1': 'r1',
        'resistance_2': 'r2', 
        'resistance_3': 'r3',
        'support_1': 's1',
        'support_2': 's2',
        'support_3': 's3',
        
        # 피보나치 매핑 (실제 DB 스키마에 존재하는 컬럼만)
        'fib_382': 'fibo_382',
        'fib_618': 'fibo_618',
        
        # 기타 매핑
        'ma200': 'ma_200',
        'volume_ratio': 'volume_change_7_30'
    },
    'ohlcv': {
        # OHLCV 기본 컬럼 매핑
        'open_price': 'open',
        'high_price': 'high',
        'low_price': 'low',
        'close_price': 'close',
        'trading_volume': 'volume',
        'trade_date': 'date',
        
        # 역호환성을 위한 MACD 매핑
        'macd_hist': 'macd_histogram'
    }
}

def apply_column_mapping(df, table_name):
    """
    DataFrame의 컬럼명을 테이블 스키마에 맞게 매핑합니다.
    
    Args:
        df (pd.DataFrame): 매핑할 DataFrame
        table_name (str): 대상 테이블명
        
    Returns:
        pd.DataFrame: 컬럼명이 매핑된 DataFrame
    """
    if table_name not in COLUMN_MAPPING:
        logger.debug(f"⚠️ {table_name} 테이블에 대한 컬럼 매핑이 정의되지 않음")
        return df
        
    mapping = COLUMN_MAPPING[table_name]
    
    # 실제 존재하는 컬럼만 매핑
    columns_to_rename = {}
    for old_col, new_col in mapping.items():
        if old_col in df.columns:
            columns_to_rename[old_col] = new_col
            
    if columns_to_rename:
        df_mapped = df.rename(columns=columns_to_rename)
        logger.debug(f"✅ {table_name} 테이블 컬럼 매핑 적용: {list(columns_to_rename.keys())} → {list(columns_to_rename.values())}")
        return df_mapped
    else:
        logger.debug(f"ℹ️ {table_name} 테이블에 매핑할 컬럼이 없음")
        return df

def validate_ticker_filtering_system():
    """
    티커 필터링 시스템의 다층 검증을 수행하는 함수
    
    검증 항목:
    1. tickers 테이블의 is_active 컬럼 존재 여부
    2. 블랙리스트 파일 접근 가능성
    3. 두 필터링 방식의 결과 비교
    """
    results = {
        "is_active_available": False,
        "blacklist_available": False,
        "filtering_consistency": False,
        "active_count": 0,
        "blacklist_filtered_count": 0,
        "consistency_rate": 0.0
    }
    
    try:
        # 1. is_active 컬럼 존재 확인
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'tickers' AND column_name = 'is_active'
        """)
        results["is_active_available"] = len(cursor.fetchall()) > 0
        
        # 2. 블랙리스트 접근 확인
        blacklist = load_blacklist()
        results["blacklist_available"] = blacklist is not None
        
        # 3. 두 방식 결과 비교 (is_active 컬럼이 있을 때만)
        if results["is_active_available"]:
            cursor.execute("SELECT ticker FROM tickers WHERE is_active = true")
            active_tickers = {row[0] for row in cursor.fetchall()}
            results["active_count"] = len(active_tickers)
            
            cursor.execute("SELECT ticker FROM tickers")
            all_tickers = {row[0] for row in cursor.fetchall()}
            
            blacklist_filtered = all_tickers - set(blacklist if blacklist else [])
            results["blacklist_filtered_count"] = len(blacklist_filtered)
            
            # 결과 일치도 검사
            overlap = len(active_tickers & blacklist_filtered)
            total = len(active_tickers | blacklist_filtered)
            consistency_rate = overlap / total if total > 0 else 0
            results["consistency_rate"] = consistency_rate
            
            results["filtering_consistency"] = consistency_rate > 0.8
        
        cursor.close()
        conn.close()
        return results
        
    except Exception as e:
        logger.error(f"❌ 티커 필터링 검증 중 오류: {e}")
        return results

def get_safe_ohlcv_columns():
    """
    실제 ohlcv 테이블에 존재하는 컬럼들을 반환하는 안전한 함수
    
    Returns:
        list: 실제 존재하는 ohlcv 테이블 컬럼 목록
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'ohlcv' 
            AND table_schema = 'public'
            ORDER BY ordinal_position
        """)
        
        columns = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        
        logger = setup_logger()
        logger.debug(f"📊 get_safe_ohlcv_columns() 조회 성공: {len(columns)}개 컬럼")
        
        return columns
        
    except Exception as e:
        logger = setup_logger()
        logger.error(f"❌ ohlcv 컬럼 조회 실패: {e}")
        # 기본 컬럼 반환
        return ['ticker', 'date', 'open', 'high', 'low', 'close', 'volume']

def validate_db_schema_and_indicators():
    """
    실제 DB 스키마와 지표 데이터 품질을 검증하는 함수
    
    작업 내용:
    1. .env 파일의 DB 연결 정보 확인
    2. ohlcv 테이블의 실제 컬럼 구조를 조회하여 존재하는 동적 지표 컬럼들만 확인
    3. static_indicators 테이블에 있는 정적 지표 컬럼들 확인
    4. 실제 DB에 존재하는 컬럼만을 대상으로 NULL 값 비율 확인
    5. 검증 결과를 상세히 로깅
    
    Returns:
        dict: 검증 결과 정보
    """
    logger = setup_logger()
    
    try:
        logger.info("🔍 DB 스키마 및 지표 구조 검증 시작")
        
        # 1. DB 연결 정보 확인
        required_env_vars = ['PG_HOST', 'PG_PORT', 'PG_DATABASE', 'PG_USER', 'PG_PASSWORD']
        missing_vars = []
        
        for var in required_env_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                # 비밀번호는 마스킹
                if var == 'PG_PASSWORD':
                    logger.info(f"✅ {var}: {'*' * len(value)}")
                else:
                    logger.info(f"✅ {var}: {value}")
        
        if missing_vars:
            logger.error(f"❌ 필수 환경변수 누락: {missing_vars}")
            return {'status': 'error', 'error': f'Missing environment variables: {missing_vars}'}
        
        # 2. DB 연결
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            # 3. ohlcv 테이블 실제 컬럼 조회
            logger.info("🔍 ohlcv 테이블 컬럼 구조 조회 중...")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'ohlcv' 
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            
            ohlcv_columns_info = cursor.fetchall()
            actual_ohlcv_columns = []
            
            for col_name, data_type, is_nullable in ohlcv_columns_info:
                actual_ohlcv_columns.append(col_name)
                null_status = "NOT NULL" if is_nullable == "NO" else "NULL"
                logger.info(f"   📊 {col_name}: {data_type} ({null_status})")
            
            # 4. static_indicators 테이블 실제 컬럼 조회
            logger.info("🔍 static_indicators 테이블 컬럼 구조 조회 중...")
            cursor.execute("""
                SELECT column_name, data_type, is_nullable 
                FROM information_schema.columns 
                WHERE table_name = 'static_indicators' 
                AND table_schema = 'public'
                ORDER BY ordinal_position
            """)
            
            static_columns_info = cursor.fetchall()
            actual_static_columns = []
            
            for col_name, data_type, is_nullable in static_columns_info:
                actual_static_columns.append(col_name)
                null_status = "NOT NULL" if is_nullable == "NO" else "NULL"
                logger.info(f"   📊 {col_name}: {data_type} ({null_status})")
            
            # 5. 동적 지표 컬럼 중 실제 존재하는 것만 필터링
            expected_dynamic_indicators = [
                'fibo_618', 'fibo_382', 'ht_trendline', 'ma_50', 'ma_200', 
                'bb_upper', 'bb_lower', 'donchian_high', 'donchian_low', 
                'macd_histogram', 'rsi_14', 'volume_20ma', 'stoch_k', 'stoch_d', 'cci'
            ]
            
            existing_dynamic_indicators = [col for col in expected_dynamic_indicators if col in actual_ohlcv_columns]
            missing_dynamic_indicators = [col for col in expected_dynamic_indicators if col not in actual_ohlcv_columns]
            
            logger.info(f"📊 동적 지표 현황:")
            logger.info(f"   • 존재하는 동적 지표: {len(existing_dynamic_indicators)}개")
            for col in existing_dynamic_indicators:
                logger.info(f"     ✅ {col}")
            
            if missing_dynamic_indicators:
                logger.warning(f"   • 누락된 동적 지표: {len(missing_dynamic_indicators)}개")
                for col in missing_dynamic_indicators:
                    logger.warning(f"     ❌ {col}")
            
            # 6. 각 지표의 NULL 비율 확인 (예: 005930 Samsung Electronics 기준)
            logger.info("🔍 동적 지표 NULL 비율 검증 중...")
            null_analysis = {}
            
            for indicator in existing_dynamic_indicators:
                try:
                    cursor.execute(f"""
                        SELECT
                            COUNT(*) as total,
                            COUNT({indicator}) as non_null,
                            COUNT(*) - COUNT({indicator}) as null_count
                        FROM ohlcv_data
                        WHERE ticker = '005930'
                        AND date >= date('now', '-30 days')
                    """)
                    
                    result = cursor.fetchone()
                    if result and result[0] > 0:
                        total, non_null, null_count = result
                        null_ratio = (null_count / total) * 100 if total > 0 else 100
                        
                        null_analysis[indicator] = {
                            'total': total,
                            'non_null': non_null, 
                            'null_count': null_count,
                            'null_ratio': null_ratio
                        }
                        
                        if null_ratio > 80:
                            logger.warning(f"  ⚠️ {indicator}: NULL 비율 {null_ratio:.1f}% ({null_count}/{total})")
                        elif null_ratio > 50:
                            logger.info(f"  🔶 {indicator}: NULL 비율 {null_ratio:.1f}% ({null_count}/{total})")
                        else:
                            logger.info(f"  ✅ {indicator}: NULL 비율 {null_ratio:.1f}% ({null_count}/{total})")
                    else:
                        logger.warning(f"  ⚠️ {indicator}: 데이터 없음")
                        null_analysis[indicator] = {'error': 'no_data'}
                        
                except Exception as e:
                    logger.error(f"  ❌ {indicator} NULL 비율 확인 실패: {e}")
                    null_analysis[indicator] = {'error': str(e)}
            
            # 7. static_indicators 컬럼 검증
            expected_static_indicators = [
                'nvt_relative', 'volume_change_7_30', 'price', 
                'high_60', 'low_60', 'pivot', 's1', 'r1', 'resistance', 
                'support', 'atr', 'adx', 'supertrend_signal'
            ]
            
            existing_static_indicators = [col for col in expected_static_indicators if col in actual_static_columns]
            missing_static_indicators = [col for col in expected_static_indicators if col not in actual_static_columns]
            
            logger.info(f"📊 정적 지표 현황:")
            logger.info(f"   • 존재하는 정적 지표: {len(existing_static_indicators)}개")
            for col in existing_static_indicators:
                logger.info(f"     ✅ {col}")
            
            if missing_static_indicators:
                logger.warning(f"   • 누락된 정적 지표: {len(missing_static_indicators)}개")
                for col in missing_static_indicators:
                    logger.warning(f"     ❌ {col}")
            
            # 8. 검증 결과 요약
            logger.info("📊 DB 스키마 검증 결과 요약:")
            logger.info(f"   • ohlcv 테이블 컬럼 수: {len(actual_ohlcv_columns)}")
            logger.info(f"   • static_indicators 테이블 컬럼 수: {len(actual_static_columns)}")
            logger.info(f"   • 존재하는 동적 지표: {len(existing_dynamic_indicators)}/{len(expected_dynamic_indicators)}")
            logger.info(f"   • 존재하는 정적 지표: {len(existing_static_indicators)}/{len(expected_static_indicators)}")
            
            total_missing = len(missing_dynamic_indicators) + len(missing_static_indicators)
            if total_missing > 0:
                logger.warning(f"   • 총 누락 컬럼 수: {total_missing}")
            
            return {
                'status': 'success',
                'ohlcv_columns': actual_ohlcv_columns,
                'static_columns': actual_static_columns,
                'existing_dynamic_indicators': existing_dynamic_indicators,
                'missing_dynamic_indicators': missing_dynamic_indicators,
                'existing_static_indicators': existing_static_indicators,
                'missing_static_indicators': missing_static_indicators,
                'null_analysis': null_analysis,
                'total_missing_columns': total_missing
            }
            
        finally:
            cursor.close()
            conn.close()
            
    except Exception as e:
        logger.error(f"❌ DB 스키마 검증 중 오류 발생: {e}")
        import traceback
        logger.error(f"상세 오류: {traceback.format_exc()}")
        return {'status': 'error', 'error': str(e)}
    
def safe_float_convert(value, default=0.0, context=""):
    """
    모든 타입의 값을 안전하게 float로 변환합니다. (모니터링 기능 추가)
    
    Args:
        value: 변환할 값
        default (float): 변환 실패 시 기본값
        context (str): 로깅용 컨텍스트
        
    Returns:
        float: 변환된 값 또는 기본값
    """
    global _conversion_stats
    
    # 전역 변수가 초기화되지 않은 경우 초기화
    if '_conversion_stats' not in globals():
        globals()['_conversion_stats'] = {
            "total_calls": 0,
            "successful_conversions": 0,
            "conversion_failures": 0,
            "datetime_detections": 0
        }
    
    _conversion_stats["total_calls"] += 1
    
    if value is None:
        _conversion_stats["successful_conversions"] += 1
        return default
        
    # datetime 계열 객체는 변환하지 않음
    if isinstance(value, (datetime, date)):
        _conversion_stats["datetime_detections"] += 1
        logger.warning(f"⚠️ {context} datetime 객체를 float로 변환 시도: {value} -> {default}")
        return default
        
    # pandas Timestamp도 체크
    if hasattr(value, '__class__') and 'pandas' in str(type(value)):
        _conversion_stats["datetime_detections"] += 1
        logger.warning(f"⚠️ {context} pandas 객체를 float로 변환 시도: {value} -> {default}")
        return default
        
    try:
        result = float(value)
        _conversion_stats["successful_conversions"] += 1
        return result
    except (ValueError, TypeError) as e:
        _conversion_stats["conversion_failures"] += 1
        logger.warning(f"⚠️ {context} float 변환 실패: {value} (타입: {type(value)}) -> {default}")
        return default

def get_conversion_stats():
    """
    safe_float_convert 함수의 변환 통계를 반환합니다.
    
    Returns:
        dict: 변환 통계 정보
    """
    global _conversion_stats
    if '_conversion_stats' not in globals():
        return {
            "total_calls": 0,
            "successful_conversions": 0,
            "conversion_failures": 0,
            "datetime_detections": 0
        }
    return _conversion_stats.copy()

def reset_conversion_stats():
    """
    safe_float_convert 함수의 변환 통계를 리셋합니다.
    """
    global _conversion_stats
    _conversion_stats = {
        "total_calls": 0,
        "successful_conversions": 0,
        "conversion_failures": 0,
        "datetime_detections": 0
    }


def check_market_hours(target_date: Optional[date] = None) -> Dict[str, any]:
    """
    Check Korean stock market hours (KOSPI/KOSDAQ)

    Trading Hours (KST = UTC+9):
    - Pre-market: 08:00-09:00
    - Regular trading: 09:00-15:30
    - After-hours: 15:30-08:00 (next day)
    - Closed: Weekends + Korean holidays

    Args:
        target_date: Date to check (default: today in KST)

    Returns:
        {
            'is_market_open': bool,
            'status': 'market_open' | 'pre_market' | 'after_hours' | 'market_closed',
            'current_time_kst': datetime,
            'market_date': date,
            'next_open': datetime,
            'next_close': datetime
        }
    """
    # KST timezone
    kst = pytz.timezone('Asia/Seoul')

    # Current time in KST
    now_kst = datetime.now(kst)
    current_date = target_date or now_kst.date()
    current_time = now_kst.time()

    # Market hours definition
    pre_market_start = datetime.strptime("08:00", "%H:%M").time()
    market_open = datetime.strptime("09:00", "%H:%M").time()
    market_close = datetime.strptime("15:30", "%H:%M").time()

    # Check if weekend
    is_weekend = current_date.weekday() >= 5  # 5=Saturday, 6=Sunday

    # Check if holiday (load from config if available)
    is_holiday = _check_korean_holiday(current_date)

    # Determine market status
    if is_weekend or is_holiday:
        # Market closed
        status = 'market_closed'
        is_market_open = False

        # Calculate next open time (next business day 09:00)
        next_open_date = _get_next_business_day(current_date)
        next_open = datetime.combine(next_open_date, market_open)
        next_open = kst.localize(next_open)
        next_close = datetime.combine(next_open_date, market_close)
        next_close = kst.localize(next_close)

    elif pre_market_start <= current_time < market_open:
        # Pre-market
        status = 'pre_market'
        is_market_open = False
        next_open = datetime.combine(current_date, market_open)
        next_open = kst.localize(next_open)
        next_close = datetime.combine(current_date, market_close)
        next_close = kst.localize(next_close)

    elif market_open <= current_time < market_close:
        # Regular trading hours
        status = 'market_open'
        is_market_open = True
        next_open = datetime.combine(current_date, market_open)
        next_open = kst.localize(next_open)
        next_close = datetime.combine(current_date, market_close)
        next_close = kst.localize(next_close)

    else:
        # After-hours
        status = 'after_hours'
        is_market_open = False

        # Next open is next business day
        next_open_date = _get_next_business_day(current_date)
        next_open = datetime.combine(next_open_date, market_open)
        next_open = kst.localize(next_open)
        next_close = datetime.combine(next_open_date, market_close)
        next_close = kst.localize(next_close)

    return {
        'is_market_open': is_market_open,
        'status': status,
        'current_time_kst': now_kst,
        'market_date': current_date,
        'next_open': next_open,
        'next_close': next_close,
        'is_weekend': is_weekend,
        'is_holiday': is_holiday
    }


def _check_korean_holiday(check_date: date) -> bool:
    """
    Check if a date is a Korean public holiday

    Args:
        check_date: Date to check

    Returns:
        True if holiday, False otherwise
    """
    # Korean public holidays 2025 (update annually)
    holidays_2025 = [
        date(2025, 1, 1),   # New Year's Day
        date(2025, 1, 28),  # Lunar New Year's Eve
        date(2025, 1, 29),  # Lunar New Year
        date(2025, 1, 30),  # Lunar New Year
        date(2025, 3, 1),   # Independence Movement Day
        date(2025, 5, 5),   # Children's Day
        date(2025, 5, 6),   # Buddha's Birthday
        date(2025, 6, 6),   # Memorial Day
        date(2025, 8, 15),  # Liberation Day
        date(2025, 9, 28),  # Chuseok Eve
        date(2025, 9, 29),  # Chuseok
        date(2025, 9, 30),  # Chuseok
        date(2025, 10, 3),  # National Foundation Day
        date(2025, 10, 9),  # Hangeul Day
        date(2025, 12, 25), # Christmas Day
    ]

    # Try to load from config file if available
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                               'config', 'market_schedule.json')

    if os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                year = check_date.year
                if str(year) in config.get('korean_holidays', {}):
                    holiday_strings = config['korean_holidays'][str(year)]
                    config_holidays = [datetime.strptime(h, '%Y-%m-%d').date()
                                     for h in holiday_strings]
                    return check_date in config_holidays
        except Exception as e:
            # Fallback to hardcoded holidays if config loading fails
            pass

    # Use hardcoded holidays as fallback
    return check_date in holidays_2025


def _get_next_business_day(current_date: date) -> date:
    """
    Get next business day (excluding weekends and holidays)

    Args:
        current_date: Starting date

    Returns:
        Next business day
    """
    next_date = current_date + timedelta(days=1)

    # Loop until we find a business day (max 10 days to prevent infinite loop)
    for _ in range(10):
        # Check if weekend
        if next_date.weekday() < 5:  # Monday=0, Friday=4
            # Check if holiday
            if not _check_korean_holiday(next_date):
                return next_date

        # Not a business day, try next day
        next_date += timedelta(days=1)

    # Fallback: return original next date if loop exhausted
    return current_date + timedelta(days=1)