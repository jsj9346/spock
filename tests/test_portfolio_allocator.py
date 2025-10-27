#!/usr/bin/env python3
"""
Portfolio Allocator Unit Tests
===============================
Comprehensive test suite for PortfolioAllocator module.

Test Coverage:
- Template loading and validation
- Error handling for invalid templates
- Configuration access methods
- Template listing functionality
- Edge cases and boundary conditions

Author: Spock Development Team
Date: 2025-10-15
"""

import unittest
import tempfile
import shutil
import yaml
from pathlib import Path
from unittest.mock import Mock, MagicMock

# Add parent directory to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from modules.portfolio_allocator import (
    PortfolioAllocator,
    PortfolioAllocatorError,
    TemplateValidationError,
    TemplateNotFoundError,
    load_template,
    list_templates
)


class TestPortfolioAllocator(unittest.TestCase):
    """Test suite for PortfolioAllocator class"""

    @classmethod
    def setUpClass(cls):
        """Setup test environment once"""
        cls.test_dir = Path(tempfile.mkdtemp())
        cls.config_dir = cls.test_dir / 'config'
        cls.config_dir.mkdir()
        cls.config_file = cls.config_dir / 'portfolio_templates.yaml'

        # Create valid test configuration
        cls.valid_config = {
            'templates': {
                'test_balanced': {
                    'name': 'Test Balanced',
                    'name_kr': '테스트 균형형',
                    'risk_level': 'moderate',
                    'description': 'Test template for balanced portfolio',
                    'allocation': {
                        'bonds_etf': 20.0,
                        'commodities_etf': 20.0,
                        'dividend_stocks': 20.0,
                        'individual_stocks': 30.0,
                        'cash': 10.0
                    },
                    'rebalancing': {
                        'method': 'hybrid',
                        'drift_threshold_percent': 7.0,
                        'periodic_interval_days': 60,
                        'min_rebalance_interval_days': 30,
                        'max_trade_size_percent': 15.0
                    },
                    'limits': {
                        'max_single_position_percent': 15.0,
                        'max_sector_exposure_percent': 40.0,
                        'min_cash_reserve_percent': 10.0,
                        'max_concurrent_positions': 10
                    },
                    'asset_classes': {}
                },
                'test_invalid_sum': {
                    'name': 'Test Invalid Sum',
                    'risk_level': 'moderate',
                    'allocation': {
                        'bonds_etf': 20.0,
                        'commodities_etf': 20.0,
                        'dividend_stocks': 20.0,
                        'individual_stocks': 30.0,
                        'cash': 20.0  # Sum = 110%
                    },
                    'rebalancing': {
                        'method': 'threshold',
                        'drift_threshold_percent': 5.0
                    },
                    'limits': {
                        'max_single_position_percent': 15.0,
                        'max_sector_exposure_percent': 40.0,
                        'min_cash_reserve_percent': 10.0,
                        'max_concurrent_positions': 10
                    }
                }
            }
        }

        # Write config file
        with open(cls.config_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(cls.valid_config, f)

    @classmethod
    def tearDownClass(cls):
        """Cleanup test environment"""
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)

    def setUp(self):
        """Setup for each test"""
        # Mock database manager
        self.mock_db = MagicMock()

    # ====================================================================
    # Test 1: Template Loading Success
    # ====================================================================

    def test_01_load_valid_template(self):
        """Test loading a valid template successfully"""
        print("\n" + "=" * 70)
        print("[Test 1] Load Valid Template")
        print("=" * 70)

        allocator = PortfolioAllocator(
            'test_balanced',
            self.mock_db,
            config_dir=str(self.config_dir)
        )

        print(f"\n✓ Template loaded: {allocator.template_name}")
        print(f"✓ Risk level: {allocator.template_config['risk_level']}")

        # Verify template loaded correctly
        self.assertEqual(allocator.template_name, 'test_balanced')
        self.assertEqual(allocator.template_config['risk_level'], 'moderate')
        self.assertEqual(allocator.template_config['template_name'], 'test_balanced')

        # Verify allocation
        allocation = allocator.get_allocation_targets()
        self.assertEqual(allocation['bonds_etf'], 20.0)
        self.assertEqual(allocation['individual_stocks'], 30.0)

        print("\n✅ Test 1 PASSED: Valid template loaded successfully")

    # ====================================================================
    # Test 2: Template Not Found
    # ====================================================================

    def test_02_template_not_found(self):
        """Test error handling for non-existent template"""
        print("\n" + "=" * 70)
        print("[Test 2] Template Not Found Error")
        print("=" * 70)

        with self.assertRaises(TemplateNotFoundError) as context:
            PortfolioAllocator(
                'nonexistent_template',
                self.mock_db,
                config_dir=str(self.config_dir)
            )

        error_msg = str(context.exception)
        print(f"\n✓ Correctly raised TemplateNotFoundError")
        print(f"✓ Error message: {error_msg}")

        self.assertIn('not found', error_msg.lower())
        self.assertIn('nonexistent_template', error_msg)

        print("\n✅ Test 2 PASSED: Template not found error handled correctly")

    # ====================================================================
    # Test 3: Invalid Allocation Sum
    # ====================================================================

    def test_03_invalid_allocation_sum(self):
        """Test validation failure for allocation sum != 100%"""
        print("\n" + "=" * 70)
        print("[Test 3] Invalid Allocation Sum")
        print("=" * 70)

        with self.assertRaises(TemplateValidationError) as context:
            PortfolioAllocator(
                'test_invalid_sum',
                self.mock_db,
                config_dir=str(self.config_dir)
            )

        error_msg = str(context.exception)
        print(f"\n✓ Correctly raised TemplateValidationError")
        print(f"✓ Error message: {error_msg}")

        self.assertIn('100', error_msg)
        self.assertIn('sum', error_msg.lower())

        print("\n✅ Test 3 PASSED: Invalid allocation sum rejected")

    # ====================================================================
    # Test 4: Missing Required Fields
    # ====================================================================

    def test_04_missing_required_fields(self):
        """Test validation failure for missing required fields"""
        print("\n" + "=" * 70)
        print("[Test 4] Missing Required Fields")
        print("=" * 70)

        # Create config with missing 'rebalancing' section
        invalid_config = {
            'templates': {
                'test_missing_fields': {
                    'name': 'Test Missing',
                    'risk_level': 'moderate',
                    'allocation': {
                        'bonds_etf': 25.0,
                        'commodities_etf': 25.0,
                        'dividend_stocks': 25.0,
                        'individual_stocks': 15.0,
                        'cash': 10.0
                    },
                    # Missing 'rebalancing' section
                    'limits': {
                        'max_single_position_percent': 15.0,
                        'max_sector_exposure_percent': 40.0,
                        'min_cash_reserve_percent': 10.0,
                        'max_concurrent_positions': 10
                    }
                }
            }
        }

        # Write invalid config to a new config directory
        temp_dir = self.test_dir / 'test_missing_fields_config'
        temp_dir.mkdir(exist_ok=True)
        temp_config = temp_dir / 'portfolio_templates.yaml'
        with open(temp_config, 'w', encoding='utf-8') as f:
            yaml.safe_dump(invalid_config, f)

        with self.assertRaises(TemplateValidationError) as context:
            PortfolioAllocator(
                'test_missing_fields',
                self.mock_db,
                config_dir=str(temp_dir)
            )

        error_msg = str(context.exception)
        print(f"\n✓ Correctly raised TemplateValidationError")
        print(f"✓ Error message: {error_msg}")

        self.assertIn('missing', error_msg.lower())

        print("\n✅ Test 4 PASSED: Missing required fields detected")

    # ====================================================================
    # Test 5: List Available Templates
    # ====================================================================

    def test_05_list_available_templates(self):
        """Test listing all available templates"""
        print("\n" + "=" * 70)
        print("[Test 5] List Available Templates")
        print("=" * 70)

        allocator = PortfolioAllocator(
            'test_balanced',
            self.mock_db,
            config_dir=str(self.config_dir)
        )

        templates = allocator.list_available_templates()

        print(f"\n✓ Found {len(templates)} templates:")
        for template in templates:
            print(f"  - {template}")

        self.assertEqual(len(templates), 2)
        self.assertIn('test_balanced', templates)
        self.assertIn('test_invalid_sum', templates)

        print("\n✅ Test 5 PASSED: Template listing works correctly")

    # ====================================================================
    # Test 6: Get Configuration Methods
    # ====================================================================

    def test_06_get_configuration_methods(self):
        """Test configuration access methods"""
        print("\n" + "=" * 70)
        print("[Test 6] Configuration Access Methods")
        print("=" * 70)

        allocator = PortfolioAllocator(
            'test_balanced',
            self.mock_db,
            config_dir=str(self.config_dir)
        )

        # Test get_allocation_targets
        allocation = allocator.get_allocation_targets()
        print("\n✓ Allocation targets retrieved:")
        for asset_class, percentage in allocation.items():
            print(f"  {asset_class}: {percentage}%")

        self.assertEqual(len(allocation), 5)
        self.assertEqual(sum(allocation.values()), 100.0)

        # Test get_rebalancing_config
        rebalancing = allocator.get_rebalancing_config()
        print("\n✓ Rebalancing config retrieved:")
        print(f"  Method: {rebalancing['method']}")
        print(f"  Drift threshold: {rebalancing['drift_threshold_percent']}%")

        self.assertEqual(rebalancing['method'], 'hybrid')
        self.assertEqual(rebalancing['drift_threshold_percent'], 7.0)

        # Test get_position_limits
        limits = allocator.get_position_limits()
        print("\n✓ Position limits retrieved:")
        for key, value in limits.items():
            print(f"  {key}: {value}")

        self.assertEqual(limits['max_single_position_percent'], 15.0)
        self.assertEqual(limits['max_concurrent_positions'], 10)

        print("\n✅ Test 6 PASSED: All configuration access methods working")

    # ====================================================================
    # Test 7: Invalid Risk Level
    # ====================================================================

    def test_07_invalid_risk_level(self):
        """Test validation failure for invalid risk level"""
        print("\n" + "=" * 70)
        print("[Test 7] Invalid Risk Level")
        print("=" * 70)

        invalid_config = {
            'templates': {
                'test_invalid_risk': {
                    'name': 'Test Invalid Risk',
                    'risk_level': 'super_aggressive',  # Invalid
                    'allocation': {
                        'bonds_etf': 20.0,
                        'commodities_etf': 20.0,
                        'dividend_stocks': 20.0,
                        'individual_stocks': 30.0,
                        'cash': 10.0
                    },
                    'rebalancing': {
                        'method': 'threshold',
                        'drift_threshold_percent': 5.0
                    },
                    'limits': {
                        'max_single_position_percent': 15.0,
                        'max_sector_exposure_percent': 40.0,
                        'min_cash_reserve_percent': 10.0,
                        'max_concurrent_positions': 10
                    }
                }
            }
        }

        temp_dir = self.test_dir / 'test_invalid_risk_config'
        temp_dir.mkdir(exist_ok=True)
        temp_config = temp_dir / 'portfolio_templates.yaml'
        with open(temp_config, 'w', encoding='utf-8') as f:
            yaml.safe_dump(invalid_config, f)

        with self.assertRaises(TemplateValidationError) as context:
            PortfolioAllocator(
                'test_invalid_risk',
                self.mock_db,
                config_dir=str(temp_dir)
            )

        error_msg = str(context.exception)
        print(f"\n✓ Correctly raised TemplateValidationError")
        print(f"✓ Error message: {error_msg}")

        self.assertIn('risk_level', error_msg.lower())

        print("\n✅ Test 7 PASSED: Invalid risk level rejected")

    # ====================================================================
    # Test 8: Module-Level Functions
    # ====================================================================

    def test_08_module_level_functions(self):
        """Test module-level convenience functions"""
        print("\n" + "=" * 70)
        print("[Test 8] Module-Level Functions")
        print("=" * 70)

        # Test list_templates
        templates = list_templates(config_dir=str(self.config_dir))
        print(f"\n✓ list_templates() found {len(templates)} templates")
        self.assertGreaterEqual(len(templates), 2)

        # Test load_template
        allocator = load_template(
            'test_balanced',
            self.mock_db,
            config_dir=str(self.config_dir)
        )
        print(f"✓ load_template() created allocator: {allocator}")

        self.assertIsInstance(allocator, PortfolioAllocator)
        self.assertEqual(allocator.template_name, 'test_balanced')

        print("\n✅ Test 8 PASSED: Module-level functions working correctly")

    # ====================================================================
    # Test 9: String Representations
    # ====================================================================

    def test_09_string_representations(self):
        """Test __str__ and __repr__ methods"""
        print("\n" + "=" * 70)
        print("[Test 9] String Representations")
        print("=" * 70)

        allocator = PortfolioAllocator(
            'test_balanced',
            self.mock_db,
            config_dir=str(self.config_dir)
        )

        # Test __repr__
        repr_str = repr(allocator)
        print(f"\n✓ repr(): {repr_str}")
        self.assertIn('PortfolioAllocator', repr_str)
        self.assertIn('test_balanced', repr_str)
        self.assertIn('moderate', repr_str)

        # Test __str__
        str_str = str(allocator)
        print(f"✓ str(): {str_str}")
        self.assertIn('Test Balanced', str_str)
        self.assertIn('20.0%', str_str)

        print("\n✅ Test 9 PASSED: String representations correct")

    # ====================================================================
    # Test 10: Current Allocation Calculation (Empty Portfolio)
    # ====================================================================

    def test_10_current_allocation_empty(self):
        """Test current allocation calculation with no holdings"""
        print("\n" + "=" * 70)
        print("[Test 10] Current Allocation - Empty Portfolio")
        print("=" * 70)

        # Mock database to return empty results
        self.mock_db.execute_query = Mock(return_value=[])

        allocator = PortfolioAllocator(
            'test_balanced',
            self.mock_db,
            config_dir=str(self.config_dir)
        )

        allocation = allocator.get_current_allocation()

        print("\n✓ Empty portfolio allocation:")
        for asset_class, percentage in allocation.items():
            print(f"  {asset_class}: {percentage}%")

        # All should be 0.0
        for asset_class in allocator.ASSET_CLASSES:
            self.assertEqual(allocation[asset_class], 0.0)

        print("\n✅ Test 10 PASSED: Empty portfolio returns zero allocation")

    # ====================================================================
    # Test 11: Current Allocation with Mock Holdings
    # ====================================================================

    def test_11_current_allocation_with_holdings(self):
        """Test current allocation calculation with mock holdings"""
        print("\n" + "=" * 70)
        print("[Test 11] Current Allocation - With Holdings")
        print("=" * 70)

        # Mock database to return sample holdings
        # Total: 10M KRW portfolio
        mock_holdings = [
            ('bonds_etf', 2_000_000),        # 20%
            ('commodities_etf', 1_500_000),  # 15%
            ('dividend_stocks', 2_500_000),  # 25%
            ('individual_stocks', 3_000_000), # 30%
            ('cash', 1_000_000)              # 10%
        ]
        self.mock_db.execute_query = Mock(return_value=mock_holdings)

        allocator = PortfolioAllocator(
            'test_balanced',
            self.mock_db,
            config_dir=str(self.config_dir)
        )

        allocation = allocator.get_current_allocation(use_cache=False)

        print("\n✓ Portfolio allocation (10M KRW total):")
        total = 0.0
        for asset_class, percentage in allocation.items():
            print(f"  {asset_class}: {percentage:.1f}%")
            total += percentage

        # Check percentages
        self.assertAlmostEqual(allocation['bonds_etf'], 20.0, places=1)
        self.assertAlmostEqual(allocation['commodities_etf'], 15.0, places=1)
        self.assertAlmostEqual(allocation['dividend_stocks'], 25.0, places=1)
        self.assertAlmostEqual(allocation['individual_stocks'], 30.0, places=1)
        self.assertAlmostEqual(allocation['cash'], 10.0, places=1)

        # Total should be 100%
        self.assertAlmostEqual(total, 100.0, places=1)

        print(f"\n✓ Total allocation: {total:.1f}%")
        print("\n✅ Test 11 PASSED: Allocation calculated correctly")

    # ====================================================================
    # Test 12: Drift Calculation
    # ====================================================================

    def test_12_drift_calculation(self):
        """Test drift calculation between current and target"""
        print("\n" + "=" * 70)
        print("[Test 12] Drift Calculation")
        print("=" * 70)

        # Mock holdings: bonds overweight, individual stocks underweight
        mock_holdings = [
            ('bonds_etf', 3_000_000),        # 30% (target: 20%, drift: +10%)
            ('commodities_etf', 2_000_000),  # 20% (target: 20%, drift: 0%)
            ('dividend_stocks', 2_000_000),  # 20% (target: 20%, drift: 0%)
            ('individual_stocks', 2_000_000), # 20% (target: 30%, drift: -10%)
            ('cash', 1_000_000)              # 10% (target: 10%, drift: 0%)
        ]
        self.mock_db.execute_query = Mock(return_value=mock_holdings)

        allocator = PortfolioAllocator(
            'test_balanced',
            self.mock_db,
            config_dir=str(self.config_dir)
        )

        drift = allocator.calculate_drift()

        print("\n✓ Drift calculation:")
        for asset_class, drift_pct in drift.items():
            print(f"  {asset_class}: {drift_pct:+.1f}%")

        # Check drift values
        self.assertAlmostEqual(drift['bonds_etf'], 10.0, places=1)
        self.assertAlmostEqual(drift['commodities_etf'], 0.0, places=1)
        self.assertAlmostEqual(drift['dividend_stocks'], 0.0, places=1)
        self.assertAlmostEqual(drift['individual_stocks'], -10.0, places=1)
        self.assertAlmostEqual(drift['cash'], 0.0, places=1)

        print("\n✅ Test 12 PASSED: Drift calculated correctly")

    # ====================================================================
    # Test 13: Max Drift Detection
    # ====================================================================

    def test_13_max_drift_detection(self):
        """Test finding asset class with maximum drift"""
        print("\n" + "=" * 70)
        print("[Test 13] Maximum Drift Detection")
        print("=" * 70)

        # Mock holdings with significant drift
        mock_holdings = [
            ('bonds_etf', 1_500_000),        # 15% (target: 20%, drift: -5%)
            ('commodities_etf', 2_000_000),  # 20% (target: 20%, drift: 0%)
            ('dividend_stocks', 1_000_000),  # 10% (target: 20%, drift: -10%)
            ('individual_stocks', 4_500_000), # 45% (target: 30%, drift: +15%)  MAX
            ('cash', 1_000_000)              # 10% (target: 10%, drift: 0%)
        ]
        self.mock_db.execute_query = Mock(return_value=mock_holdings)

        allocator = PortfolioAllocator(
            'test_balanced',
            self.mock_db,
            config_dir=str(self.config_dir)
        )

        max_asset, max_drift = allocator.get_max_drift()

        print(f"\n✓ Maximum drift: {max_asset} = {max_drift:+.1f}%")

        self.assertEqual(max_asset, 'individual_stocks')
        self.assertAlmostEqual(max_drift, 15.0, places=1)

        print("\n✅ Test 13 PASSED: Maximum drift detected correctly")

    # ====================================================================
    # Test 14: Rebalancing Check - Threshold Method
    # ====================================================================

    def test_14_rebalancing_threshold_method(self):
        """Test threshold-based rebalancing trigger"""
        print("\n" + "=" * 70)
        print("[Test 14] Rebalancing Check - Threshold Method")
        print("=" * 70)

        # Create threshold-method template config
        threshold_config = self.valid_config.copy()
        threshold_config['templates']['test_threshold'] = {
            'name': 'Test Threshold',
            'risk_level': 'moderate',
            'allocation': {
                'bonds_etf': 20.0,
                'commodities_etf': 20.0,
                'dividend_stocks': 20.0,
                'individual_stocks': 30.0,
                'cash': 10.0
            },
            'rebalancing': {
                'method': 'threshold',
                'drift_threshold_percent': 5.0  # 5% threshold
            },
            'limits': {
                'max_single_position_percent': 15.0,
                'max_sector_exposure_percent': 40.0,
                'min_cash_reserve_percent': 10.0,
                'max_concurrent_positions': 10
            },
            'asset_classes': {}
        }

        temp_config_file = self.test_dir / 'threshold_config' / 'portfolio_templates.yaml'
        temp_config_file.parent.mkdir(exist_ok=True)
        with open(temp_config_file, 'w', encoding='utf-8') as f:
            yaml.safe_dump(threshold_config, f)

        # Test 1: Drift below threshold - no rebalancing
        print("\n[Test 14.1] Drift below threshold (3%)")
        mock_holdings_low = [
            ('bonds_etf', 2_300_000),        # 23% (drift: +3%)
            ('commodities_etf', 2_000_000),  # 20%
            ('dividend_stocks', 2_000_000),  # 20%
            ('individual_stocks', 2_700_000), # 27% (drift: -3%)
            ('cash', 1_000_000)              # 10%
        ]
        self.mock_db.execute_query = Mock(return_value=mock_holdings_low)

        allocator = PortfolioAllocator(
            'test_threshold',
            self.mock_db,
            config_dir=str(temp_config_file.parent)
        )

        needed, reason = allocator.check_rebalancing_needed()
        print(f"  Needed: {needed}")
        print(f"  Reason: {reason}")
        self.assertFalse(needed)

        # Test 2: Drift above threshold - rebalancing needed
        print("\n[Test 14.2] Drift above threshold (8%)")
        mock_holdings_high = [
            ('bonds_etf', 2_800_000),        # 28% (drift: +8%)
            ('commodities_etf', 2_000_000),  # 20%
            ('dividend_stocks', 2_000_000),  # 20%
            ('individual_stocks', 2_200_000), # 22% (drift: -8%)
            ('cash', 1_000_000)              # 10%
        ]
        self.mock_db.execute_query = Mock(return_value=mock_holdings_high)

        allocator2 = PortfolioAllocator(
            'test_threshold',
            self.mock_db,
            config_dir=str(temp_config_file.parent)
        )

        needed, reason = allocator2.check_rebalancing_needed()
        print(f"  Needed: {needed}")
        print(f"  Reason: {reason}")
        self.assertTrue(needed)
        self.assertIn('threshold', reason.lower())

        print("\n✅ Test 14 PASSED: Threshold rebalancing works correctly")

    # ====================================================================
    # Test 15: Cache Functionality
    # ====================================================================

    def test_15_allocation_cache(self):
        """Test allocation caching mechanism"""
        print("\n" + "=" * 70)
        print("[Test 15] Allocation Cache")
        print("=" * 70)

        mock_holdings = [
            ('bonds_etf', 2_000_000),
            ('commodities_etf', 2_000_000),
            ('dividend_stocks', 2_000_000),
            ('individual_stocks', 3_000_000),
            ('cash', 1_000_000)
        ]
        self.mock_db.execute_query = Mock(return_value=mock_holdings)

        allocator = PortfolioAllocator(
            'test_balanced',
            self.mock_db,
            config_dir=str(self.config_dir)
        )

        # First call - should query database
        allocation1 = allocator.get_current_allocation(use_cache=False)
        call_count_1 = self.mock_db.execute_query.call_count

        # Second call with cache - should NOT query database
        allocation2 = allocator.get_current_allocation(use_cache=True)
        call_count_2 = self.mock_db.execute_query.call_count

        print(f"\n✓ First call (no cache): {call_count_1} DB queries")
        print(f"✓ Second call (with cache): {call_count_2 - call_count_1} DB queries")

        self.assertEqual(call_count_2, call_count_1, "Cache should prevent second DB query")
        self.assertEqual(allocation1, allocation2, "Cached result should match")

        # Invalidate cache
        allocator.invalidate_cache()
        allocation3 = allocator.get_current_allocation(use_cache=True)
        call_count_3 = self.mock_db.execute_query.call_count

        print(f"✓ After cache invalidation: {call_count_3 - call_count_2} DB queries")
        self.assertGreater(call_count_3, call_count_2, "Cache invalidation should trigger new query")

        print("\n✅ Test 15 PASSED: Cache functionality works correctly")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
