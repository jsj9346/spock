#!/usr/bin/env python3
"""
Alert Silence Management Script for Quant Platform

Manage alert silences in Alertmanager for maintenance windows or known issues.

Usage:
    # Create silences
    python3 manage_silences.py create --alertname HighBacktestFailureRate --duration 2h
    python3 manage_silences.py create --severity critical --duration 1h --comment "Maintenance"
    python3 manage_silences.py create --category backtest_performance --duration 30m

    # List silences
    python3 manage_silences.py list
    python3 manage_silences.py list --active-only

    # Delete silences
    python3 manage_silences.py delete --id <silence-id>
    python3 manage_silences.py delete --all
"""

import argparse
import requests
import json
import sys
from datetime import datetime, timedelta

# Configuration
ALERTMANAGER_URL = "http://localhost:9093"


class SilenceManager:
    """Manage Alertmanager silences via API"""

    def __init__(self, alertmanager_url):
        self.alertmanager_url = alertmanager_url
        self.api_base = f"{alertmanager_url}/api/v2"

    def parse_duration(self, duration_str):
        """Parse duration string (e.g., '2h', '30m', '1d') to timedelta"""
        if not duration_str:
            return timedelta(hours=1)  # Default 1 hour

        unit = duration_str[-1]
        value = int(duration_str[:-1])

        if unit == 's':
            return timedelta(seconds=value)
        elif unit == 'm':
            return timedelta(minutes=value)
        elif unit == 'h':
            return timedelta(hours=value)
        elif unit == 'd':
            return timedelta(days=value)
        else:
            raise ValueError(f"Invalid duration format: {duration_str}. Use: 30s, 15m, 2h, 1d")

    def create_silence(self, matchers, duration, comment, created_by="admin"):
        """
        Create a new silence in Alertmanager

        Args:
            matchers: List of dicts with 'name', 'value', 'isRegex'
            duration: Duration string (e.g., '2h', '30m')
            comment: Reason for silence
            created_by: User who created the silence
        """
        starts_at = datetime.utcnow()
        ends_at = starts_at + self.parse_duration(duration)

        silence = {
            "matchers": matchers,
            "startsAt": starts_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endsAt": ends_at.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "createdBy": created_by,
            "comment": comment or "Created via manage_silences.py"
        }

        try:
            response = requests.post(
                f"{self.api_base}/silences",
                json=silence,
                headers={"Content-Type": "application/json"},
                timeout=5
            )

            if response.status_code == 200:
                silence_id = response.json()["silenceID"]
                print(f"✅ Silence created successfully")
                print(f"   Silence ID: {silence_id}")
                print(f"   Duration: {duration}")
                print(f"   Ends at: {ends_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"   Matchers:")
                for matcher in matchers:
                    print(f"      - {matcher['name']} = {matcher['value']}")
                return silence_id
            else:
                print(f"❌ Failed to create silence: {response.status_code}")
                print(f"   Response: {response.text}")
                return None

        except Exception as e:
            print(f"❌ Error creating silence: {e}")
            return None

    def list_silences(self, active_only=False):
        """List all silences in Alertmanager"""
        try:
            response = requests.get(f"{self.api_base}/silences", timeout=5)

            if response.status_code != 200:
                print(f"❌ Failed to fetch silences: {response.status_code}")
                return []

            silences = response.json()

            if not silences:
                print("📭 No silences found")
                return []

            # Filter active silences if requested
            if active_only:
                now = datetime.utcnow()
                silences = [
                    s for s in silences
                    if s['status']['state'] == 'active' or
                    (datetime.fromisoformat(s['startsAt'].replace('Z', '+00:00')).replace(tzinfo=None) <= now <=
                     datetime.fromisoformat(s['endsAt'].replace('Z', '+00:00')).replace(tzinfo=None))
                ]

            if not silences:
                print("📭 No active silences found")
                return []

            print(f"📋 Found {len(silences)} silence(s):\n")

            for silence in silences:
                silence_id = silence['id']
                status = silence['status']['state']
                created_by = silence['createdBy']
                comment = silence['comment']
                starts_at = datetime.fromisoformat(silence['startsAt'].replace('Z', '+00:00'))
                ends_at = datetime.fromisoformat(silence['endsAt'].replace('Z', '+00:00'))

                # Status icon
                if status == 'active':
                    icon = '🔕'
                elif status == 'pending':
                    icon = '⏳'
                elif status == 'expired':
                    icon = '⏹️ '
                else:
                    icon = '❓'

                print(f"{icon} Silence ID: {silence_id}")
                print(f"   Status: {status}")
                print(f"   Created by: {created_by}")
                print(f"   Comment: {comment}")
                print(f"   Start: {starts_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                print(f"   End: {ends_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")

                # Calculate remaining time for active silences
                if status == 'active':
                    now = datetime.utcnow().replace(tzinfo=None)
                    remaining = ends_at.replace(tzinfo=None) - now
                    hours = remaining.total_seconds() / 3600
                    print(f"   Remaining: {hours:.1f} hours")

                print(f"   Matchers:")
                for matcher in silence['matchers']:
                    regex_indicator = " (regex)" if matcher['isRegex'] else ""
                    print(f"      - {matcher['name']} = {matcher['value']}{regex_indicator}")

                print()  # Blank line between silences

            return silences

        except Exception as e:
            print(f"❌ Error listing silences: {e}")
            return []

    def delete_silence(self, silence_id):
        """Delete a specific silence by ID"""
        try:
            response = requests.delete(
                f"{self.api_base}/silence/{silence_id}",
                timeout=5
            )

            if response.status_code == 200:
                print(f"✅ Silence {silence_id} deleted successfully")
                return True
            else:
                print(f"❌ Failed to delete silence: {response.status_code}")
                print(f"   Response: {response.text}")
                return False

        except Exception as e:
            print(f"❌ Error deleting silence: {e}")
            return False

    def delete_all_silences(self):
        """Delete all silences (use with caution!)"""
        silences = self.list_silences(active_only=True)

        if not silences:
            print("No active silences to delete")
            return

        print(f"\n⚠️  About to delete {len(silences)} silence(s)")
        confirm = input("Are you sure? (yes/no): ")

        if confirm.lower() != 'yes':
            print("❌ Deletion cancelled")
            return

        success_count = 0
        for silence in silences:
            if self.delete_silence(silence['id']):
                success_count += 1

        print(f"\n✅ Deleted {success_count}/{len(silences)} silence(s)")


def main():
    parser = argparse.ArgumentParser(
        description="Manage Alertmanager silences for Quant Platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create silences
  python3 manage_silences.py create \\
      --alertname HighBacktestFailureRate \\
      --duration 2h \\
      --comment "Investigating issue"

  python3 manage_silences.py create \\
      --severity critical \\
      --duration 1h \\
      --comment "Maintenance window"

  python3 manage_silences.py create \\
      --category backtest_performance \\
      --strategy-name TestStrategy \\
      --duration 30m

  # List silences
  python3 manage_silences.py list
  python3 manage_silences.py list --active-only

  # Delete silences
  python3 manage_silences.py delete --id <silence-id>
  python3 manage_silences.py delete --all
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Create silence
    create_parser = subparsers.add_parser('create', help='Create a new silence')
    create_parser.add_argument('--alertname', type=str, help='Alert name to silence')
    create_parser.add_argument('--severity', type=str, choices=['critical', 'warning', 'info'],
                               help='Severity level to silence')
    create_parser.add_argument('--category', type=str,
                               help='Alert category (e.g., backtest_performance)')
    create_parser.add_argument('--strategy-name', type=str, help='Strategy name to silence')
    create_parser.add_argument('--engine', type=str, help='Engine to silence (e.g., backtrader)')
    create_parser.add_argument('--factor-name', type=str, help='Factor name to silence')
    create_parser.add_argument('--duration', type=str, required=True,
                               help='Silence duration (e.g., 30m, 2h, 1d)')
    create_parser.add_argument('--comment', type=str, help='Reason for silence')
    create_parser.add_argument('--created-by', type=str, default='admin',
                               help='User creating the silence (default: admin)')

    # List silences
    list_parser = subparsers.add_parser('list', help='List all silences')
    list_parser.add_argument('--active-only', action='store_true',
                             help='Show only active silences')

    # Delete silence
    delete_parser = subparsers.add_parser('delete', help='Delete silence(s)')
    delete_parser.add_argument('--id', type=str, help='Silence ID to delete')
    delete_parser.add_argument('--all', action='store_true',
                               help='Delete all active silences (use with caution!)')

    # Global options
    parser.add_argument('--alertmanager-url', type=str, default=ALERTMANAGER_URL,
                        help='Alertmanager URL (default: http://localhost:9093)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Initialize manager
    manager = SilenceManager(args.alertmanager_url)

    print("=" * 60)
    print("Quant Platform Alert Silence Manager")
    print("=" * 60)

    # Execute command
    if args.command == 'create':
        # Build matchers from arguments
        matchers = []

        if args.alertname:
            matchers.append({
                "name": "alertname",
                "value": args.alertname,
                "isRegex": False
            })

        if args.severity:
            matchers.append({
                "name": "severity",
                "value": args.severity,
                "isRegex": False
            })

        if args.category:
            matchers.append({
                "name": "category",
                "value": args.category,
                "isRegex": False
            })

        if args.strategy_name:
            matchers.append({
                "name": "strategy_name",
                "value": args.strategy_name,
                "isRegex": False
            })

        if args.engine:
            matchers.append({
                "name": "engine",
                "value": args.engine,
                "isRegex": False
            })

        if args.factor_name:
            matchers.append({
                "name": "factor_name",
                "value": args.factor_name,
                "isRegex": False
            })

        if not matchers:
            print("❌ Error: At least one matcher is required")
            print("   Use --alertname, --severity, --category, --strategy-name, --engine, or --factor-name")
            sys.exit(1)

        manager.create_silence(
            matchers=matchers,
            duration=args.duration,
            comment=args.comment,
            created_by=args.created_by
        )

    elif args.command == 'list':
        manager.list_silences(active_only=args.active_only)

    elif args.command == 'delete':
        if args.id:
            manager.delete_silence(args.id)
        elif args.all:
            manager.delete_all_silences()
        else:
            print("❌ Error: Specify --id or --all")
            sys.exit(1)

    print("\n" + "=" * 60)
    print("For more information, see:")
    print("   docs/ALERT_NOTIFICATION_SETUP.md")
    print("   Alertmanager UI: http://localhost:9093")


if __name__ == '__main__':
    main()
