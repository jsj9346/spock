#!/usr/bin/env python3
"""
KIS API Token Cache Inspector

Purpose: Check cached token status and validate caching system
Usage: python3 scripts/check_token_cache.py
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load credentials
load_dotenv(project_root / '.env')

from modules.api_clients.kis_overseas_stock_api import KISOverseasStockAPI


def check_cache_file():
    """Check if token cache file exists and is valid"""
    cache_path = project_root / 'data' / '.kis_token_cache.json'

    print("🔍 KIS API Token Cache Inspector")
    print("=" * 60)
    print()

    print(f"📁 Cache file: {cache_path}")

    if not cache_path.exists():
        print("❌ Cache file does not exist")
        print()
        print("💡 This is expected if:")
        print("   1. This is your first run")
        print("   2. Token cache was manually deleted")
        print()
        return False

    print("✅ Cache file exists")
    print()

    # Check permissions
    stat_info = os.stat(cache_path)
    perms = oct(stat_info.st_mode)[-3:]
    print(f"🔐 File permissions: {perms}")

    if perms != '600':
        print(f"⚠️  Insecure permissions! Should be 600 (owner read/write only)")
    else:
        print("✅ Secure permissions (600)")
    print()

    # Read cache contents
    try:
        with open(cache_path, 'r') as f:
            cache_data = json.load(f)

        print("📄 Cache contents:")
        print(f"   Token length: {len(cache_data.get('access_token', ''))} chars")

        expires_at_str = cache_data.get('expires_at')
        if expires_at_str:
            expires_at = datetime.fromisoformat(expires_at_str)
            now = datetime.now()

            print(f"   Expires at: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")

            if now < expires_at:
                remaining = (expires_at - now).total_seconds()
                hours = remaining / 3600
                print(f"   Status: ✅ VALID ({hours:.1f} hours remaining)")
            else:
                print(f"   Status: ❌ EXPIRED")

        cached_at_str = cache_data.get('cached_at')
        if cached_at_str:
            cached_at = datetime.fromisoformat(cached_at_str)
            print(f"   Cached at: {cached_at.strftime('%Y-%m-%d %H:%M:%S')}")

        print()
        return True

    except Exception as e:
        print(f"❌ Error reading cache: {e}")
        print()
        return False


def test_caching_system():
    """Test KIS API caching system with new monitoring features"""
    print("🧪 Testing Token Caching System")
    print("=" * 60)
    print()

    app_key = os.getenv('KIS_APP_KEY')
    app_secret = os.getenv('KIS_APP_SECRET')

    if not app_key or not app_secret:
        print("❌ KIS credentials not found in .env")
        return False

    print(f"📊 Credentials loaded")
    print(f"   APP_KEY: {app_key[:8]}...{app_key[-4:]}")
    print()

    # Test 1: Initialize API client
    print("Test 1: Initialize API client")
    try:
        api = KISOverseasStockAPI(app_key=app_key, app_secret=app_secret)
        print("✅ API client initialized")

        # Use new get_token_status() method
        status = api.get_token_status()

        print(f"📈 Token Status: {status['status']}")
        print(f"   Valid: {status['valid']}")
        print(f"   Cache exists: {status['cache_exists']}")

        if status['expires_at']:
            print(f"   Expires at: {status['expires_at']}")
            print(f"   Remaining: {status['remaining_hours']:.2f} hours ({status['remaining_seconds']} seconds)")
            print(f"   Buffer: {status['buffer_seconds']}s ({status['buffer_seconds']//60}min)")
            print(f"   Proactive refresh: {status['proactive_refresh_seconds']}s ({status['proactive_refresh_seconds']//60}min)")

        print()

    except Exception as e:
        print(f"❌ Initialization failed: {e}")
        print()
        return False

    # Test 2: Token retrieval (will use cache or request new)
    print("Test 2: Token retrieval")
    try:
        token = api._get_access_token()

        if token:
            print(f"✅ Token retrieved successfully")
            print(f"   Token length: {len(token)} chars")

            # Check updated status
            status = api.get_token_status()
            print(f"   Status after retrieval: {status['status']}")
            print(f"   Remaining time: {status['remaining_hours']:.2f}h")

            # Check if cache file was created/updated
            cache_path = project_root / 'data' / '.kis_token_cache.json'
            if cache_path.exists():
                print(f"✅ Cache file exists: {cache_path}")
            else:
                print(f"⚠️ Cache file not created")
        else:
            print(f"❌ Token retrieval failed")

        print()

    except Exception as e:
        print(f"❌ Token retrieval failed: {e}")
        print()

        # Check if this is a rate limit error
        if "403" in str(e) or "Forbidden" in str(e):
            print("💡 This is likely due to 1-per-day token limit")
            print("   Your cached token should still work for API calls")
            print("   Try again tomorrow for a fresh token")

        print()

    # Test 3: Status monitoring
    print("Test 3: Token status monitoring")
    try:
        status = api.get_token_status()

        print(f"📊 Current Token Status:")
        print(f"   Status: {status['status']}")
        print(f"   Valid: {'✅ Yes' if status['valid'] else '❌ No'}")
        print(f"   Cache file: {'✅ Exists' if status['cache_exists'] else '❌ Missing'}")

        if status['expires_at']:
            print(f"   Expiration: {status['expires_at']}")
            print(f"   Time left: {status['remaining_hours']:.2f}h ({status['remaining_seconds']}s)")

            # Efficiency calculation
            total_lifetime_seconds = 24 * 3600  # 24 hours
            usable_seconds = total_lifetime_seconds - status['buffer_seconds']
            efficiency = (usable_seconds / total_lifetime_seconds) * 100

            print(f"   Token efficiency: {efficiency:.2f}% (buffer: {status['buffer_seconds']//60}min)")

            # Proactive refresh window
            if status['status'] == 'EXPIRING_SOON':
                refresh_window = status['remaining_seconds']
                print(f"   ⚡ Proactive refresh window: {refresh_window}s ({refresh_window//60}min)")
                print(f"   💡 Token will auto-refresh on next API call")

        print()

    except Exception as e:
        print(f"❌ Status monitoring failed: {e}")
        print()

    return True


def main():
    """Main entry point"""

    # Check cache file status
    check_cache_file()

    print()
    print("-" * 60)
    print()

    # Test caching system
    test_caching_system()

    print()
    print("=" * 60)
    print("💡 Token Caching Benefits:")
    print()
    print("✅ Prevents 1-per-day token limit issues")
    print("✅ Persists across program restarts")
    print("✅ Automatic expiration handling (24h lifetime)")
    print("✅ Secure file permissions (600)")
    print("✅ Proactive refresh (30min before expiry)")
    print("✅ File locking (prevents race conditions)")
    print("✅ Automatic error recovery (cache corruption)")
    print("✅ 99.65% token efficiency (5min buffer)")
    print()
    print("🔒 Security:")
    print("   - Token cache stored in data/.kis_token_cache.json")
    print("   - File permissions: 600 (owner read/write only)")
    print("   - Excluded from git (.gitignore)")
    print("   - File locking prevents concurrent access")
    print()
    print("⚡ Performance:")
    print("   - Token efficiency: 99.65% (5min buffer vs 1h)")
    print("   - Proactive refresh: 30min before expiry")
    print("   - Graceful fallback if refresh fails")
    print("   - Unified validation logic")
    print()


if __name__ == '__main__':
    main()
