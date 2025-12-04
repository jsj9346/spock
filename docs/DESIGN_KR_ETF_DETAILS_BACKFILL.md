# KR ETF Details Backfill System Design

## 1. 개요

### 1.1 목표
KR 리전 ETF 1,045개의 `etf_details` 테이블 NULL 필드를 공공 데이터 소스로 채우기

### 1.2 현재 상태
| 필드 | 현재 상태 | 목표 |
|------|----------|------|
| `issuer` | 3/1045 (0.3%) | ~100% |
| `inception_date` | 3/1045 (0.3%) | ~100% |
| `tracking_index` | 모두 'Unknown' | ~100% |
| `listed_shares` | 3/1045 (0.3%) | ~100% |
| `aum` | 3/1045 (0.3%) | ~100% |
| `expense_ratio` | 모두 0.00 | Phase 2 |

### 1.3 데이터 소스
1. **KRX 정보데이터시스템** (data.krx.co.kr) - 공공 데이터 ✅
2. **금융투자협회 전자공시** (dis.kofia.or.kr) - Phase 2

---

## 2. 아키텍처

### 2.1 시스템 구성도

```
┌─────────────────────────────────────────────────────────────────────┐
│                    KR ETF Details Backfill System                    │
└─────────────────────────────────────────────────────────────────────┘

     ┌─────────────────┐              ┌─────────────────┐
     │  KRX Data API   │              │   Kofia API     │
     │  (data.krx.co.kr)│              │ (Phase 2)       │
     └────────┬────────┘              └────────┬────────┘
              │                                │
              │ MDCSTAT04601                   │ expense_ratio
              │ MDCSTAT04301                   │
              │                                │
              ▼                                ▼
     ┌─────────────────────────────────────────────────────┐
     │              KRETFDetailsBackfiller                  │
     │              (Orchestrator)                          │
     ├─────────────────────────────────────────────────────┤
     │  • fetch_from_krx()                                  │
     │  • merge_with_existing()                             │
     │  • batch_update()                                    │
     │  • generate_report()                                 │
     └────────────────────────┬────────────────────────────┘
                              │
                              ▼
     ┌─────────────────────────────────────────────────────┐
     │              PostgresDatabaseManager                 │
     │              (etf_details table)                     │
     └─────────────────────────────────────────────────────┘
```

### 2.2 클래스 다이어그램

```
┌─────────────────────────────────────────────────────────────────────┐
│                          <<interface>>                               │
│                      ETFDetailsDataSource                            │
├─────────────────────────────────────────────────────────────────────┤
│ + fetch_all() → Dict[str, ETFDetailsData]                           │
│ + get_source_name() → str                                           │
└─────────────────────────────────────────────────────────────────────┘
                    △                         △
                    │                         │
        ┌───────────┴───────────┐   ┌────────┴────────┐
        │                       │   │                  │
┌───────┴───────────────┐ ┌─────┴───┴────────────────┐
│   KRXETFDataSource    │ │   KofiaETFDataSource     │
├───────────────────────┤ ├──────────────────────────┤
│ - session: Session    │ │ - session: Session       │
│ - base_url: str       │ │ - base_url: str          │
├───────────────────────┤ ├──────────────────────────┤
│ + fetch_all()         │ │ + fetch_all()            │
│ + _get_etf_list()     │ │ + _scrape_expense()      │
│ + _get_etf_nav()      │ │                          │
│ + _parse_date()       │ │ (Phase 2)                │
└───────────────────────┘ └──────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     KRETFDetailsBackfiller                           │
├─────────────────────────────────────────────────────────────────────┤
│ - db: PostgresDatabaseManager                                        │
│ - sources: List[ETFDetailsDataSource]                                │
│ - stats: BackfillStats                                               │
├─────────────────────────────────────────────────────────────────────┤
│ + run(dry_run: bool = False) → BackfillResult                        │
│ + get_null_field_etfs() → List[str]                                  │
│ + merge_data(existing: Dict, new: Dict) → Dict                       │
│ + batch_update(data: List[Dict]) → int                               │
│ + generate_report() → str                                            │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     @dataclass ETFDetailsData                        │
├─────────────────────────────────────────────────────────────────────┤
│ + ticker: str                                                        │
│ + issuer: Optional[str]                                              │
│ + tracking_index: Optional[str]                                      │
│ + listed_shares: Optional[int]                                       │
│ + inception_date: Optional[date]                                     │
│ + aum: Optional[int]                                                 │
│ + expense_ratio: Optional[float]                                     │
│ + data_source: str                                                   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. KRX API 상세

### 3.1 사용 엔드포인트

| 엔드포인트 | bld 코드 | 제공 데이터 |
|-----------|---------|------------|
| ETF 종목 현황 | `dbms/MDC/STAT/standard/MDCSTAT04601` | issuer, tracking_index, listed_shares, listing_date |
| ETF 시세 | `dbms/MDC/STAT/standard/MDCSTAT04301` | NAV, 순자산총액 (AUM) |

### 3.2 API 호출 구조

```python
# Step 1: OTP 발급
POST http://data.krx.co.kr/comm/fileDn/GenerateOTP/generate.cmd
Headers:
    Referer: http://data.krx.co.kr/
    User-Agent: Mozilla/5.0
Body:
    bld: dbms/MDC/STAT/standard/MDCSTAT04601
    locale: ko_KR
    trdDd: 20251204
    csvxls_isNo: false

# Step 2: 데이터 조회
POST http://data.krx.co.kr/comm/bldAttendant/getJsonData.cmd
Headers:
    Referer: http://data.krx.co.kr/
Body:
    bld: dbms/MDC/STAT/standard/MDCSTAT04601
    locale: ko_KR
    trdDd: 20251204
```

### 3.3 응답 필드 매핑

| KRX 필드 | DB 필드 | 설명 |
|---------|---------|------|
| `COMPANY_NM` | `issuer` | 운용사명 |
| `OBJ_TP_NM` | `tracking_index` | 추종지수 |
| `LIST_SHRS` | `listed_shares` | 상장주식수 |
| `LIST_DD` | `inception_date` | 상장일 |
| `NAV_AMT` | `aum` | 순자산총액 (원) |

---

## 4. 데이터 흐름

### 4.1 실행 흐름

```
┌──────────────────────────────────────────────────────────────────┐
│  1. 시작                                                          │
│     - 명령줄 인자 파싱                                            │
│     - DB 연결 초기화                                              │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  2. NULL 필드 ETF 조회                                            │
│     SELECT ticker FROM etf_details                                │
│     WHERE region = 'KR'                                           │
│       AND (issuer IS NULL OR tracking_index = 'Unknown' ...)      │
│     → 결과: ~1,042개 ETF                                          │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  3. KRX API 호출                                                  │
│     3.1 MDCSTAT04601 → ETF 기본정보 (전체 ETF 한 번에)            │
│     3.2 MDCSTAT04301 → ETF 시세/NAV (전체 ETF 한 번에)            │
│     → 2번의 API 호출로 모든 데이터 수집                           │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  4. 데이터 병합                                                   │
│     - KRX 데이터와 DB ticker 매칭                                 │
│     - NULL 필드만 업데이트 (COALESCE 패턴)                        │
│     - 'Unknown' tracking_index 교체                               │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  5. Batch Update                                                  │
│     UPDATE etf_details SET                                        │
│       issuer = COALESCE(%s, issuer),                              │
│       tracking_index = CASE                                       │
│         WHEN tracking_index = 'Unknown' THEN %s                   │
│         ELSE tracking_index END,                                  │
│       aum = COALESCE(%s, aum),                                    │
│       ...                                                         │
│     WHERE ticker = %s AND region = 'KR'                           │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│  6. 결과 리포트                                                   │
│     - 업데이트 성공/실패 통계                                     │
│     - 필드별 커버리지 변화                                        │
│     - 누락된 ticker 목록                                          │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 에러 처리

| 에러 유형 | 처리 방법 |
|----------|----------|
| KRX API 타임아웃 | 3회 재시도 (exponential backoff) |
| 데이터 파싱 실패 | 해당 ticker 스킵, 로그 기록 |
| DB 업데이트 실패 | 트랜잭션 롤백, 개별 재시도 |
| 날짜 형식 오류 | 다중 형식 파싱 시도 |

---

## 5. 구현 계획

### 5.1 Phase 1: KRX 데이터 (즉시 구현)

| 작업 | 파일 | 설명 |
|------|------|------|
| 1 | `modules/api_clients/krx_data_api.py` | `get_etf_list()` 메서드 확장 (이미 존재, 필드 매핑 확인) |
| 2 | `modules/collection/kr_etf_details_backfiller.py` | 신규 오케스트레이터 클래스 |
| 3 | `scripts/backfill_kr_etf_details.py` | CLI 스크립트 |

### 5.2 Phase 2: 금투협 데이터 (추후 구현)

| 작업 | 파일 | 설명 |
|------|------|------|
| 1 | `modules/api_clients/kofia_api.py` | 신규 API 클라이언트 |
| 2 | `expense_ratio` 수집 로직 | 웹 구조 분석 후 구현 |

---

## 6. CLI 인터페이스

### 6.1 사용법

```bash
# 전체 백필 (기본)
python scripts/backfill_kr_etf_details.py

# Dry-run 모드 (DB 변경 없이 시뮬레이션)
python scripts/backfill_kr_etf_details.py --dry-run

# 특정 ticker만 업데이트
python scripts/backfill_kr_etf_details.py --ticker 069500

# 상태 확인만
python scripts/backfill_kr_etf_details.py --status

# 강제 업데이트 (기존 값도 덮어쓰기)
python scripts/backfill_kr_etf_details.py --force
```

### 6.2 출력 예시

```
================================================================================
  KR ETF Details Backfill Report
================================================================================
  Date: 2024-12-04 15:30:00
  Source: KRX Data API (data.krx.co.kr)
================================================================================

  BEFORE:
    issuer:         3/1045 (0.3%)
    tracking_index: 0/1045 (0.0%) [all 'Unknown']
    listed_shares:  3/1045 (0.3%)
    inception_date: 3/1045 (0.3%)
    aum:            3/1045 (0.3%)

  AFTER:
    issuer:         1042/1045 (99.7%)  ✅ +1039
    tracking_index: 1042/1045 (99.7%)  ✅ +1042
    listed_shares:  1042/1045 (99.7%)  ✅ +1039
    inception_date: 1042/1045 (99.7%)  ✅ +1039
    aum:            1042/1045 (99.7%)  ✅ +1039

  SUMMARY:
    Updated:  1042 ETFs
    Skipped:  3 ETFs (no KRX data)
    Failed:   0 ETFs

================================================================================
```

---

## 7. 테스트 계획

### 7.1 단위 테스트

| 테스트 | 설명 |
|--------|------|
| `test_krx_api_connection` | KRX API 연결 확인 |
| `test_parse_etf_list` | ETF 목록 파싱 |
| `test_parse_date_formats` | 다양한 날짜 형식 파싱 |
| `test_merge_logic` | 데이터 병합 로직 |
| `test_null_coalesce` | NULL 필드 업데이트 로직 |

### 7.2 통합 테스트

| 테스트 | 설명 |
|--------|------|
| `test_dry_run_mode` | Dry-run 모드에서 DB 변경 없음 확인 |
| `test_single_ticker` | 단일 ticker 업데이트 |
| `test_batch_update` | 전체 배치 업데이트 |
| `test_idempotency` | 재실행 시 중복 업데이트 없음 |

---

## 8. 리스크 및 고려사항

### 8.1 기술적 리스크

| 리스크 | 완화 방안 |
|--------|----------|
| KRX API 응답 형식 변경 | 필드 매핑 외부화, 버전 관리 |
| 네트워크 불안정 | 재시도 로직, 타임아웃 설정 |
| 대량 데이터 메모리 | 청크 단위 처리 |

### 8.2 데이터 품질

| 이슈 | 처리 방안 |
|------|----------|
| ticker 불일치 | DB ticker와 KRX ticker 매핑 테이블 |
| 날짜 형식 다양 | 다중 파서 적용 |
| 숫자 형식 (콤마) | 정규화 함수 적용 |

---

## 9. 예상 결과

### 9.1 커버리지 변화

| 필드 | Before | After (Phase 1) | After (Phase 2) |
|------|--------|-----------------|-----------------|
| `issuer` | 0.3% | ~100% | ~100% |
| `tracking_index` | 0% | ~100% | ~100% |
| `listed_shares` | 0.3% | ~100% | ~100% |
| `inception_date` | 0.3% | ~100% | ~100% |
| `aum` | 0.3% | ~100% | ~100% |
| `expense_ratio` | 0% | 0% | ~100% |

### 9.2 실행 시간

- **Phase 1**: ~10초 (2번의 API 호출 + DB 배치 업데이트)
- **Phase 2**: 미정 (금투협 API 분석 필요)

---

## 10. 참고 자료

- [KRX 정보데이터시스템](https://data.krx.co.kr/)
- [금융투자협회 펀드정보](https://fund.kofia.or.kr/)
- [pykrx GitHub](https://github.com/sharebook-kr/pykrx)
- [R을 이용한 퀀트 투자 - 금융 데이터 수집](https://hyunyulhenry.github.io/quant_cookbook/금융-데이터-수집하기-기본.html)

---

**작성일**: 2024-12-04
**작성자**: Claude Code
**상태**: 설계 완료, 구현 대기
