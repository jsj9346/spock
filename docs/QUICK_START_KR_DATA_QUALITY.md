# Quick Start: KR Market Data Quality Management

**빠른 시작 가이드** - KR 시장 데이터 품질 관리

---

## 📋 한 줄 요약

```bash
# 전체 자동화 워크플로우 (데이터 수집 → 지표 재계산 → 검증)
python3 scripts/kr_data_quality_workflow.py
```

---

## 🚀 빠른 명령어

### 1. 현재 데이터 품질 확인
```bash
python3 scripts/validate_kr_data_quality.py
```
**실행 시간**: 10초
**출력**: 커버리지, NULL 비율, 갭, 이상치 리포트
**종료 코드**: 0 (우수), 1 (심각), 2 (경고)

---

### 2. 250일 데이터 수집 (전체 종목)
```bash
python3 scripts/collect_full_kr_250days.py
```
**실행 시간**: 28분
**대상**: 3,745 종목
**출력**: 종목당 ~249행 (1년 데이터)

---

### 3. 기술적 지표 재계산 (16개 지표)
```bash
python3 scripts/recalculate_technical_indicators.py
```
**실행 시간**: 60초
**지표**: MA, RSI, MACD, BB, ATR, Volume
**출력**: NULL 비율 개선 리포트

---

### 4. 전체 워크플로우 (자동화)
```bash
# 처음 실행 (데이터 수집 + 재계산 + 검증)
python3 scripts/kr_data_quality_workflow.py

# 데이터 수집 건너뛰기 (재계산만)
python3 scripts/kr_data_quality_workflow.py --skip-collection

# 지표 재계산 건너뛰기 (검증만)
python3 scripts/kr_data_quality_workflow.py --skip-recalculation

# 강제 실행 (검증 실패해도)
python3 scripts/kr_data_quality_workflow.py --force
```

---

## 📊 스크립트 비교

| 스크립트 | 목적 | 실행 시간 | 주요 출력 |
|---------|------|---------|----------|
| `validate_kr_data_quality.py` | 품질 검증 | 10초 | 커버리지/NULL 리포트 |
| `collect_full_kr_250days.py` | 데이터 수집 | 28분 | 종목당 249행 수집 |
| `recalculate_technical_indicators.py` | 지표 재계산 | 60초 | NULL 비율 개선 |
| `kr_data_quality_workflow.py` | 전체 자동화 | 29분 | 종합 리포트 |

---

## 🎯 일반적인 시나리오

### 시나리오 1: 처음 실행 (데이터 부족)
```bash
# 1. 현재 상태 확인
python3 scripts/validate_kr_data_quality.py
# 출력 예: "❌ CRITICAL - Average coverage: 139.3 days (target: 250)"

# 2. 전체 워크플로우 실행
python3 scripts/kr_data_quality_workflow.py
# 실행 시간: 약 29분

# 3. 최종 확인
python3 scripts/validate_kr_data_quality.py
# 출력 예: "✅ EXCELLENT - All validations passed"
```

---

### 시나리오 2: 데이터는 충분, 지표만 재계산
```bash
# 1. 현재 상태 확인
python3 scripts/validate_kr_data_quality.py
# 출력 예: "⚠️ ACCEPTABLE - MA200 NULL: 74.25%"

# 2. 지표 재계산만 실행
python3 scripts/recalculate_technical_indicators.py
# 실행 시간: 약 60초

# 3. 최종 확인
python3 scripts/validate_kr_data_quality.py
# 출력 예: "✅ EXCELLENT - MA200 NULL: 0.27%"
```

---

### 시나리오 3: 주기적 품질 확인 (일일/주간)
```bash
# 매일 또는 매주 실행
python3 scripts/validate_kr_data_quality.py

# 문제 발견 시
if [ $? -ne 0 ]; then
    echo "Data quality issue detected!"
    python3 scripts/kr_data_quality_workflow.py --force
fi
```

---

### 시나리오 4: 백그라운드 수집 모니터링
```bash
# 수집 스크립트 백그라운드 실행
nohup python3 scripts/collect_full_kr_250days.py > logs/collection.log 2>&1 &

# 프로세스 ID 확인
ps aux | grep collect_full_kr_250days

# 로그 실시간 모니터링
tail -f logs/full_kr_collection_250days_v2.log

# 진행률 확인
grep "진행률:" logs/full_kr_collection_250days_v2.log | tail -1
```

---

## 🔍 트러블슈팅

### 문제 1: "pandas_ta not available" 경고
```bash
# pandas-ta 설치
pip install pandas-ta

# 재계산 재실행
python3 scripts/recalculate_technical_indicators.py
```

---

### 문제 2: 수집 타임아웃 (1시간 초과)
```bash
# 워크플로우 타임아웃 증가
# kr_data_quality_workflow.py 수정:
# timeout=3600 → timeout=7200 (2시간)

# 또는 수집 스크립트 단독 실행
python3 scripts/collect_full_kr_250days.py
```

---

### 문제 3: 재계산 후에도 NULL 비율 높음
```bash
# 데이터 커버리지 확인
python3 scripts/validate_kr_data_quality.py | grep "Average coverage"

# 커버리지 부족 시 (<250일)
python3 scripts/collect_full_kr_250days.py
python3 scripts/recalculate_technical_indicators.py
```

---

### 문제 4: 데이터베이스 잠금 오류
```bash
# 다른 프로세스 종료
ps aux | grep python3 | grep spock
kill <PID>

# 재계산 재실행
python3 scripts/recalculate_technical_indicators.py
```

---

## 📈 성능 벤치마크

### 하드웨어 사양 기준
- CPU: Apple M1/M2 또는 동급
- RAM: 8GB 이상
- 저장공간: 500MB 여유 (데이터베이스 확장)

### 실행 시간
```
데이터 수집 (3,745 종목):
  - 종목당: 0.45초
  - 총 시간: 28분
  - API 호출: 11,235회

지표 재계산 (3,745 종목):
  - 종목당: 0.016초 (벡터화)
  - 총 시간: 60초
  - DB 업데이트: ~932,605 행

검증:
  - 총 시간: 10초
  - 샘플링: 100개 종목 (갭), 50개 종목 (이상치)
```

---

## 📚 추가 문서

1. **상세 설계 문서**: [docs/TECHNICAL_INDICATOR_RECALCULATION_DESIGN.md](TECHNICAL_INDICATOR_RECALCULATION_DESIGN.md)
2. **자동화 가이드**: [docs/KR_DATA_QUALITY_AUTOMATION.md](KR_DATA_QUALITY_AUTOMATION.md)
3. **페이지네이션 리포트**: [docs/KR_PAGINATION_IMPLEMENTATION_REPORT.md](KR_PAGINATION_IMPLEMENTATION_REPORT.md)

---

## 🎯 최종 목표

```
데이터 커버리지:
  - 목표: 250일 평균
  - 허용: 200일 이상

기술적 지표 완성도:
  - 목표: NULL <1% (EXCELLENT)
  - 허용: NULL <5% (ACCEPTABLE)

최종 상태:
  ✅ LayeredScoringEngine 실행 준비 완료
```

---

## 💡 팁

1. **자동화 스케줄링**:
   ```bash
   # crontab 예제 (매일 오전 6시 실행)
   0 6 * * * cd /path/to/spock && python3 scripts/kr_data_quality_workflow.py --skip-collection
   ```

2. **로그 관리**:
   ```bash
   # 오래된 로그 정리 (30일 이상)
   find logs/ -name "*.log" -mtime +30 -delete
   ```

3. **성능 모니터링**:
   ```bash
   # 실행 시간 측정
   time python3 scripts/recalculate_technical_indicators.py
   ```

4. **데이터베이스 백업**:
   ```bash
   # 재계산 전 백업
   cp data/spock_local.db data/spock_local.db.backup_$(date +%Y%m%d)
   ```

---

**마지막 업데이트**: 2025-10-20
**문의**: GitHub Issues 또는 프로젝트 문서 참조
