#!/usr/bin/env python3
"""
Test CLI Login via API

This script tests the end-to-end CLI → API integration for authentication.
"""

import sys
from pathlib import Path
from unittest.mock import patch
import io

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from cli.commands.auth import login, status, logout


def test_login():
    """Test login command with mocked input."""
    print("\n" + "="*70)
    print("TEST 1: Login via API (cloud mode)")
    print("="*70 + "\n")

    # Mock getpass and input
    with patch('cli.commands.auth.input', return_value='admin'):
        with patch('cli.commands.auth.getpass.getpass', return_value='password123'):
            try:
                login()
                print("\n✅ Login test PASSED\n")
                return True
            except Exception as e:
                print(f"\n❌ Login test FAILED: {e}\n")
                return False


def test_status():
    """Test status command."""
    print("\n" + "="*70)
    print("TEST 2: Authentication Status Check")
    print("="*70 + "\n")

    try:
        status()
        print("\n✅ Status test PASSED\n")
        return True
    except Exception as e:
        print(f"\n❌ Status test FAILED: {e}\n")
        return False


def test_logout():
    """Test logout command."""
    print("\n" + "="*70)
    print("TEST 3: Logout via API")
    print("="*70 + "\n")

    try:
        logout()
        print("\n✅ Logout test PASSED\n")
        return True
    except Exception as e:
        print(f"\n❌ Logout test FAILED: {e}\n")
        return False


def test_status_after_logout():
    """Test status after logout."""
    print("\n" + "="*70)
    print("TEST 4: Verify Logout (should show 'Not authenticated')")
    print("="*70 + "\n")

    try:
        status()
        print("\n✅ Post-logout status test PASSED\n")
        return True
    except Exception as e:
        print(f"\n❌ Post-logout status test FAILED: {e}\n")
        return False


if __name__ == '__main__':
    print("\n" + "🚀 " + "="*66)
    print("  CLI ↔ API Integration Test Suite")
    print("="*68 + " 🚀\n")

    results = []

    # Run tests sequentially
    results.append(("Login", test_login()))
    results.append(("Status Check", test_status()))
    results.append(("Logout", test_logout()))
    results.append(("Post-Logout Status", test_status_after_logout()))

    # Summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status_icon = "✅" if result else "❌"
        print(f"{status_icon} {test_name}: {'PASSED' if result else 'FAILED'}")

    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*70 + "\n")

    # Exit code
    sys.exit(0 if passed == total else 1)
