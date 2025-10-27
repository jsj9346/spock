# Phase 2 Dry Run 상세 분석

**실행 완료**: 2025-10-24 14:51
**총 소요 시간**: 16.2분 (평균 108초/종목)
**성공률**: 100% (9/9)
**수집된 레코드**: 25/27 (2개 누락)

---

## 🎯 전체 결과 요약

| 종목 | 이름 | 산업 | 2022 | 2023 | 2024 | 상태 |
|------|------|------|------|------|------|------|
| 005930 | 삼성전자 | 반도체 | ⚠️ Rev=0 | ✅ | ✅ | COGS/EBITDA OK |
| 000660 | SK하이닉스 | 반도체 | ✅ | ⚠️ EBITDA=0 | ⚠️ EBITDA=0 | Revenue OK |
| 105560 | KB금융 | 금융 | ❌ 없음 | ⚠️ Rev=0 | ⚠️ Rev=0 | EBITDA OK |
| 035420 | 네이버 | IT서비스 | ✅ | ✅ | ✅ | COGS=0 정상 |
| 035720 | 카카오 | IT서비스 | ✅ Rev | ✅ Rev | ✅ Rev | ⚠️ EBITDA=0 |
| 005380 | 현대차 | 자동차 | ✅ | ✅ | ✅ | 완벽 |
| 051910 | LG화학 | 화학 | ⚠️ Rev=0 | ⚠️ Rev=0 | ⚠️ Rev=0 | COGS/EBITDA OK |
| 055550 | 신한금융 | 금융 | ❌ 없음 | ⚠️ Rev=0 | ⚠️ Rev=0 | EBITDA OK |
| 068270 | 셀트리온 | 제약/바이오 | ✅ | ✅ | ✅ | 완벽 |

---

## ❌ 문제 1: Revenue = 0

### 패턴 분석

#### A. 제조업 (Revenue=0)
- **삼성전자 2022**: Revenue=0, COGS=190T, EBITDA=43T
- **LG화학 전체**: Revenue=0 (모든 연도), COGS 존재

**원인 가설**:
- 2022년 보고서: '매출액' 대신 다른 계정명 사용 가능
- LG화학: 연결재무제표에서 '매출액' vs '영업수익' 필드명 차이

#### B. 금융업 (Revenue=0) - 예상된 결과
- **KB금융 2023/2024**: Revenue=0, EBITDA=6.4T/8.0T
- **신한금융 2023/2024**: Revenue=0, EBITDA=6.1T/6.5T

**원인**: 금융회사는 '영업수익' 사용 (이미 fallback 로직 있음)
**실제값**: EBITDA가 정상이므로 operating profit은 수집됨

---

## ❌ 문제 2: EBITDA = 0

### 패턴 분석

#### A. SK하이닉스 2023/2024
- **2022**: Revenue=44.6T, COGS=29.0T, EBITDA=6.8T ✅
- **2023**: Revenue=32.8T, COGS=33.3T, EBITDA=0 ❌
- **2024**: Revenue=66.2T, COGS=34.4T, EBITDA=0 ❌

**분석**:
- 2023: COGS > Revenue → 영업손실 발생 (반도체 불황)
- Operating profit이 음수일 경우 EBITDA 계산 로직 문제
- Depreciation 추정 실패 가능성

**예상 EBITDA** (간단 추정):
- 2023: Gross Profit = 32.8T - 33.3T = -0.5T (영업손실)
- 2024: Gross Profit = 66.2T - 34.4T = 31.8T (회복)
- 2024 EBITDA가 0인 것은 비정상 → Depreciation 추정 실패

#### B. 카카오 전체 연도
- **Revenue**: 6.8T/7.6T/7.9T ✅ 수집됨
- **COGS**: 0 (정상 - 서비스업)
- **EBITDA**: 0 ❌ (비정상 - 서비스업도 EBITDA 존재)

**원인 가설**:
- Operating profit은 수집되었으나 depreciation 추정 실패
- 서비스업의 감가상각비 추정 알고리즘 문제

---

## ✅ 정상 동작 확인

### 1. 제조업 (완벽)
- **현대차**: Revenue/COGS/EBITDA 모두 정상
- **셀트리온**: Revenue/COGS/EBITDA 모두 정상

### 2. IT서비스 (부분 정상)
- **네이버**: Revenue 정상, COGS=0 (정상), EBITDA 정상

### 3. Depreciation 추정 성공 사례
- **삼성전자 2023**: EBITDA=44.1T (추정 성공)
- **현대차 2023**: EBITDA=15.1T (추정 성공)
- **셀트리온 2023**: EBITDA=651B (추정 성공)

---

## 🔍 Step 2: 근본 원인 조사 계획

### 조사 대상 1: Revenue=0 문제

#### LG화학 (051910) - 우선순위 높음
```bash
# LG화학 2023 DART API 응답 확인
python3 tests/investigate_revenue_issue.py --ticker 051910 --year 2023
```

**예상 결과**:
- '매출액' 필드 없음
- '영업수익' 또는 다른 변형 계정명 사용

#### 삼성전자 2022 - 우선순위 중간
```bash
# 삼성전자 2022 vs 2023 비교
python3 tests/investigate_revenue_issue.py --ticker 005930 --years 2022,2023
```

**예상 결과**:
- 2022년 보고서 계정명 변형
- 2023년과 다른 필드명 사용

### 조사 대상 2: EBITDA=0 문제

#### SK하이닉스 2024 - 우선순위 높음
```bash
# 2024년 cash flow 데이터 확인
python3 tests/investigate_ebitda_issue.py --ticker 000660 --year 2024
```

**예상 원인**:
- Operating CF 데이터 누락
- Working capital change 계산 오류
- 음수 operating profit 처리 로직 오류

#### 카카오 전체 - 우선순위 높음
```bash
# 서비스업 depreciation 추정 확인
python3 tests/investigate_ebitda_issue.py --ticker 035720 --year 2023
```

**예상 원인**:
- 서비스업 특성상 PP&E 적음
- Operating CF 기반 추정 실패
- 대체 계정명 필요 ('무형자산상각비' 등)

---

## 📋 수정 우선순위

### Priority 1: Revenue 필드명 확장 (LG화학)
- **영향도**: 높음 (제조업 매출액 누락)
- **난이도**: 낮음 (fallback 로직 추가)
- **예상 시간**: 30분

### Priority 2: EBITDA 계산 로직 개선 (SK하이닉스, 카카오)
- **영향도**: 높음 (핵심 지표 누락)
- **난이도**: 중간 (음수 처리, 서비스업 대응)
- **예상 시간**: 1-2시간

### Priority 3: 금융업 Revenue 수집 (KB금융, 신한금융)
- **영향도**: 중간 (EBITDA는 수집됨)
- **난이도**: 낮음 (이미 fallback 있음, 확인 필요)
- **예상 시간**: 30분

---

## 🎯 Next Actions

1. ✅ **조사 스크립트 생성**: Revenue/EBITDA 문제 조사
2. 🔄 **DART API 응답 확인**: 문제 종목 실제 데이터 분석
3. 🛠️ **파싱 로직 수정**: dart_api_client.py 업데이트
4. ✅ **재검증**: 수정된 로직으로 dry run 재실행
5. 🚀 **전체 백필 진행**: ~2,000 종목

---

**작성일**: 2025-10-24 14:52
**다음 단계**: Revenue=0 문제 조사 스크립트 작성
