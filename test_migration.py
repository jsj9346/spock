#!/usr/bin/env python3
"""
M5 Mac 마이그레이션 검증 스크립트
"""

import sys
import os

# 환경 확인
print("=" * 60)
print(" M5 Mac 마이그레이션 검증")
print("=" * 60)
print()

# 1. Python 버전 확인
print(f"✅ Python 버전: {sys.version}")
print()

# 2. 주요 패키지 import 테스트
print("패키지 import 테스트:")
try:
    import pandas as pd
    print(f"  ✅ pandas {pd.__version__}")
except Exception as e:
    print(f"  ❌ pandas: {e}")

try:
    import numpy as np
    print(f"  ✅ numpy {np.__version__}")
except Exception as e:
    print(f"  ❌ numpy: {e}")

try:
    import psycopg2
    print(f"  ✅ psycopg2 {psycopg2.__version__}")
except Exception as e:
    print(f"  ❌ psycopg2: {e}")

try:
    import scipy
    print(f"  ✅ scipy {scipy.__version__}")
except Exception as e:
    print(f"  ❌ scipy: {e}")

try:
    import sklearn
    print(f"  ✅ scikit-learn {sklearn.__version__}")
except Exception as e:
    print(f"  ❌ scikit-learn: {e}")

print()

# 3. 데이터베이스 연결 테스트
print("데이터베이스 연결 테스트:")
try:
    conn = psycopg2.connect(
        host='localhost',
        database='quant_platform',
        user='13ruce'
    )
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ohlcv_data")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    print(f"  ✅ PostgreSQL 연결 성공")
    print(f"  ✅ OHLCV 데이터: {count:,} 행")
except Exception as e:
    print(f"  ❌ PostgreSQL 연결 실패: {e}")

print()

# 4. 모듈 import 테스트
print("프로젝트 모듈 import 테스트:")
try:
    from modules.db_manager_postgres import PostgresDatabaseManager
    print("  ✅ PostgresDatabaseManager")
except Exception as e:
    print(f"  ❌ PostgresDatabaseManager: {e}")

try:
    from modules.backtesting.data_providers.base_data_provider import BaseDataProvider
    print("  ✅ BaseDataProvider")
except Exception as e:
    print(f"  ❌ BaseDataProvider: {e}")

print()
print("=" * 60)
print(" 마이그레이션 검증 완료")
print("=" * 60)
