#!/usr/bin/env python3
"""
test_value_factors.py - Unit Tests for Value Factors (Phase 2)

Tests:
1. PERatioFactor calculation with mock database
2. PBRatioFactor calculation
3. EVToEBITDAFactor calculation
4. DividendYieldFactor calculation
5. Database integration and error handling
6. Sanity checks and validation

Usage:
    python3 tests/test_value_factors.py
    pytest tests/test_value_factors.py -v
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import unittest
import sqlite3
import tempfile
from datetime import datetime

from modules.factors import (
    PERatioFactor,
    PBRatioFactor,
    EVToEBITDAFactor,
    DividendYieldFactor
)


class TestValueFactorsWithMockDB(unittest.TestCase):
    """Test Value factors with mock database"""

    @classmethod
    def setUpClass(cls):
        """Create temporary database with mock fundamental data"""
        cls.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        cls.db_path = cls.temp_db.name

        # Create schema and insert mock data
        conn = sqlite3.connect(cls.db_path)
        cursor = conn.cursor()

        # Create tickers table
        cursor.execute("""
            CREATE TABLE tickers (
                ticker TEXT PRIMARY KEY,
                name TEXT,
                region TEXT
            )
        """)

        # Create ticker_fundamentals table
        cursor.execute("""
            CREATE TABLE ticker_fundamentals (
                id INTEGER PRIMARY KEY,
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                period_type TEXT NOT NULL,
                fiscal_year INTEGER,
                per REAL,
                pbr REAL,
                ev_ebitda REAL,
                dividend_yield REAL,
                market_cap BIGINT,
                FOREIGN KEY (ticker) REFERENCES tickers(ticker)
            )
        """)

        # Insert mock tickers
        cursor.execute("INSERT INTO tickers VALUES ('005930', 'Samsung Electronics', 'KR')")
        cursor.execute("INSERT INTO tickers VALUES ('035720', 'Kakao', 'KR')")
        cursor.execute("INSERT INTO tickers VALUES ('AAPL', 'Apple Inc', 'US')")

        # Insert mock fundamental data
        # Samsung - Low P/E (value stock)
        cursor.execute("""
            INSERT INTO ticker_fundamentals (ticker, date, period_type, fiscal_year, per, pbr, ev_ebitda, dividend_yield, market_cap)
            VALUES ('005930', '2024-12-31', 'ANNUAL', 2024, 12.5, 1.2, 8.5, 2.5, 500000000000000)
        """)

        # Kakao - High P/E (growth stock)
        cursor.execute("""
            INSERT INTO ticker_fundamentals (ticker, date, period_type, fiscal_year, per, pbr, ev_ebitda, dividend_yield, market_cap)
            VALUES ('035720', '2024-12-31', 'ANNUAL', 2024, 35.0, 3.5, 18.0, 0.8, 50000000000000)
        """)

        # Apple - Moderate P/E (quality growth)
        cursor.execute("""
            INSERT INTO ticker_fundamentals (ticker, date, period_type, fiscal_year, per, pbr, ev_ebitda, dividend_yield, market_cap)
            VALUES ('AAPL', '2024-12-31', 'ANNUAL', 2024, 25.0, 45.0, 22.0, 0.5, 3000000000000000)
        """)

        conn.commit()
        conn.close()

    @classmethod
    def tearDownClass(cls):
        """Clean up temporary database"""
        os.unlink(cls.db_path)

    def test_pe_ratio_factor_samsung(self):
        """Test P/E factor with Samsung (low P/E)"""
        factor = PERatioFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='005930')

        self.assertIsNotNone(result)
        self.assertEqual(result.ticker, '005930')
        self.assertEqual(result.factor_name, 'PE_Ratio')

        # P/E = 12.5, so factor_value = -12.5
        self.assertAlmostEqual(result.raw_value, -12.5, places=1)

        # Check metadata
        self.assertEqual(result.metadata['pe_ratio'], 12.5)
        self.assertEqual(result.metadata['fiscal_year'], 2024)
        self.assertEqual(result.metadata['interpretation'], 'fair_value')

        # Confidence should be high
        self.assertGreater(result.confidence, 0.8)

    def test_pe_ratio_factor_kakao(self):
        """Test P/E factor with Kakao (high P/E)"""
        factor = PERatioFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='035720')

        self.assertIsNotNone(result)
        # P/E = 35.0, so factor_value = -35.0 (lower score for expensive stock)
        self.assertAlmostEqual(result.raw_value, -35.0, places=1)
        self.assertEqual(result.metadata['interpretation'], 'overvalued')

    def test_pb_ratio_factor_samsung(self):
        """Test P/B factor with Samsung (low P/B)"""
        factor = PBRatioFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='005930')

        self.assertIsNotNone(result)
        # P/B = 1.2, factor_value = -1.2
        self.assertAlmostEqual(result.raw_value, -1.2, places=1)
        self.assertEqual(result.metadata['pb_ratio'], 1.2)
        self.assertEqual(result.metadata['interpretation'], 'fair_value')

    def test_pb_ratio_factor_apple(self):
        """Test P/B factor with Apple (very high P/B)"""
        factor = PBRatioFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='AAPL')

        self.assertIsNotNone(result)
        # P/B = 45.0 (expensive growth stock)
        self.assertAlmostEqual(result.raw_value, -45.0, places=1)
        self.assertEqual(result.metadata['interpretation'], 'expensive')

    def test_ev_ebitda_factor_samsung(self):
        """Test EV/EBITDA factor with Samsung"""
        factor = EVToEBITDAFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='005930')

        self.assertIsNotNone(result)
        # EV/EBITDA = 8.5, factor_value = -8.5
        self.assertAlmostEqual(result.raw_value, -8.5, places=1)
        self.assertEqual(result.metadata['ev_ebitda'], 8.5)
        self.assertEqual(result.metadata['interpretation'], 'undervalued')

    def test_ev_ebitda_factor_kakao(self):
        """Test EV/EBITDA factor with Kakao"""
        factor = EVToEBITDAFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='035720')

        self.assertIsNotNone(result)
        # EV/EBITDA = 18.0, factor_value = -18.0
        self.assertAlmostEqual(result.raw_value, -18.0, places=1)
        self.assertEqual(result.metadata['interpretation'], 'growth_premium')

    def test_dividend_yield_factor_samsung(self):
        """Test Dividend Yield factor with Samsung (moderate yield)"""
        factor = DividendYieldFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='005930')

        self.assertIsNotNone(result)
        # Dividend yield = 2.5%, factor_value = 2.5 (NOT negated)
        self.assertAlmostEqual(result.raw_value, 2.5, places=1)
        self.assertEqual(result.metadata['dividend_yield'], 2.5)
        self.assertEqual(result.metadata['interpretation'], 'moderate_yield')

    def test_dividend_yield_factor_kakao(self):
        """Test Dividend Yield factor with Kakao (low yield)"""
        factor = DividendYieldFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='035720')

        self.assertIsNotNone(result)
        # Dividend yield = 0.8% (low yield growth stock)
        self.assertAlmostEqual(result.raw_value, 0.8, places=1)
        self.assertEqual(result.metadata['interpretation'], 'low_yield')

    def test_missing_ticker(self):
        """Test handling of missing ticker"""
        factor = PERatioFactor(db_path=self.db_path)
        result = factor.calculate(None, ticker='INVALID')

        self.assertIsNone(result)

    def test_all_value_factors_consistency(self):
        """Test that all value factors return consistent results for same ticker"""
        ticker = '005930'

        pe_factor = PERatioFactor(db_path=self.db_path)
        pb_factor = PBRatioFactor(db_path=self.db_path)
        ev_factor = EVToEBITDAFactor(db_path=self.db_path)
        div_factor = DividendYieldFactor(db_path=self.db_path)

        pe_result = pe_factor.calculate(None, ticker)
        pb_result = pb_factor.calculate(None, ticker)
        ev_result = ev_factor.calculate(None, ticker)
        div_result = div_factor.calculate(None, ticker)

        # All should succeed
        self.assertIsNotNone(pe_result)
        self.assertIsNotNone(pb_result)
        self.assertIsNotNone(ev_result)
        self.assertIsNotNone(div_result)

        # All should have same ticker and fiscal_year
        self.assertEqual(pe_result.metadata['fiscal_year'], 2024)
        self.assertEqual(pb_result.metadata['fiscal_year'], 2024)
        self.assertEqual(ev_result.metadata['fiscal_year'], 2024)
        self.assertEqual(div_result.metadata['fiscal_year'], 2024)

    def test_value_factor_ranking(self):
        """Test that value factors rank stocks correctly"""
        pe_factor = PERatioFactor(db_path=self.db_path)

        samsung_result = pe_factor.calculate(None, '005930')  # P/E = 12.5
        kakao_result = pe_factor.calculate(None, '035720')    # P/E = 35.0

        # Samsung (lower P/E) should have HIGHER factor value (less negative)
        # Because factor_value = -P/E, so -12.5 > -35.0
        self.assertGreater(samsung_result.raw_value, kakao_result.raw_value)


class TestValueFactorInterpretation(unittest.TestCase):
    """Test interpretation logic for value factors"""

    def test_pe_interpretation_ranges(self):
        """Test P/E ratio interpretation ranges"""
        factor = PERatioFactor(db_path="dummy.db")

        self.assertEqual(factor._interpret_pe(8.0), "undervalued")
        self.assertEqual(factor._interpret_pe(15.0), "fair_value")
        self.assertEqual(factor._interpret_pe(25.0), "growth_premium")
        self.assertEqual(factor._interpret_pe(40.0), "overvalued")

    def test_pb_interpretation_ranges(self):
        """Test P/B ratio interpretation ranges"""
        factor = PBRatioFactor(db_path="dummy.db")

        self.assertEqual(factor._interpret_pb(0.8), "deep_value")
        self.assertEqual(factor._interpret_pb(2.0), "fair_value")
        self.assertEqual(factor._interpret_pb(4.0), "growth_premium")
        self.assertEqual(factor._interpret_pb(10.0), "expensive")

    def test_ev_ebitda_interpretation_ranges(self):
        """Test EV/EBITDA interpretation ranges"""
        factor = EVToEBITDAFactor(db_path="dummy.db")

        self.assertEqual(factor._interpret_ev_ebitda(8.0), "undervalued")
        self.assertEqual(factor._interpret_ev_ebitda(12.0), "fair_value")
        self.assertEqual(factor._interpret_ev_ebitda(17.0), "growth_premium")
        self.assertEqual(factor._interpret_ev_ebitda(25.0), "expensive")

    def test_dividend_yield_interpretation_ranges(self):
        """Test dividend yield interpretation ranges"""
        factor = DividendYieldFactor(db_path="dummy.db")

        self.assertEqual(factor._interpret_dividend_yield(5.0), "high_yield")
        self.assertEqual(factor._interpret_dividend_yield(3.0), "moderate_yield")
        self.assertEqual(factor._interpret_dividend_yield(1.0), "low_yield")
        self.assertEqual(factor._interpret_dividend_yield(0.0), "no_dividend")


def run_tests():
    """Run all tests"""
    unittest.main(verbosity=2)


if __name__ == '__main__':
    run_tests()
