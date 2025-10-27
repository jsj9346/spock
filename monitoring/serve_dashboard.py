#!/usr/bin/env python3
"""
serve_dashboard.py - Dashboard Server

Purpose:
- Serve monitoring dashboard HTML
- Auto-generate metrics_latest.json symlink
- Provide simple HTTP server for dashboard access
- Support live metrics refresh

Usage:
    python3 monitoring/serve_dashboard.py [--port 8080]

Author: Spock Trading System
Created: 2025-10-16 (Phase 3, Task 3.2.2)
"""

import os
import sys
import json
import argparse
import http.server
import socketserver
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from modules.metrics_collector import MetricsCollector


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP handler for dashboard"""

    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

    def log_message(self, format, *args):
        # Custom logging
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] {format % args}")


def create_latest_symlink():
    """Create or update metrics_latest.json symlink to most recent metrics file"""
    metrics_dir = project_root / 'metrics_reports'

    if not metrics_dir.exists():
        print(f"⚠️  Metrics directory not found: {metrics_dir}")
        return None

    # Find most recent metrics file
    metrics_files = sorted(metrics_dir.glob('metrics_*.json'), reverse=True)

    if not metrics_files:
        print(f"⚠️  No metrics files found in {metrics_dir}")
        return None

    latest_file = metrics_files[0]
    symlink_path = metrics_dir / 'metrics_latest.json'

    # Remove existing symlink if it exists
    if symlink_path.exists() or symlink_path.is_symlink():
        symlink_path.unlink()

    # Create new symlink
    try:
        symlink_path.symlink_to(latest_file.name)
        print(f"✅ Created symlink: {symlink_path} -> {latest_file.name}")
        return symlink_path
    except Exception as e:
        print(f"❌ Failed to create symlink: {e}")
        return None


def generate_fresh_metrics():
    """Generate fresh metrics file"""
    print("📊 Generating fresh metrics...")

    collector = MetricsCollector()
    output_file = collector.save_metrics()

    print(f"✅ Metrics saved: {output_file}")

    # Create/update latest symlink
    create_latest_symlink()

    return output_file


def serve_dashboard(port=8080):
    """Serve monitoring dashboard"""
    # Change to monitoring directory
    os.chdir(project_root / 'monitoring')

    # Generate fresh metrics
    generate_fresh_metrics()

    # Create server
    Handler = DashboardHandler
    with socketserver.TCPServer(("", port), Handler) as httpd:
        print("\n" + "="*70)
        print("Spock Trading System - Monitoring Dashboard Server")
        print("="*70)
        print(f"\n✅ Server running at http://localhost:{port}")
        print(f"📊 Dashboard URL: http://localhost:{port}/dashboard.html")
        print(f"📁 Serving from: {os.getcwd()}")
        print(f"\n💡 Press Ctrl+C to stop the server")
        print("="*70 + "\n")

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n🛑 Shutting down server...")
            httpd.shutdown()


def main():
    parser = argparse.ArgumentParser(description='Spock Monitoring Dashboard Server')
    parser.add_argument('--port', type=int, default=8080,
                       help='Port to serve dashboard (default: 8080)')
    parser.add_argument('--generate-only', action='store_true',
                       help='Only generate metrics, don\'t start server')
    args = parser.parse_args()

    if args.generate_only:
        generate_fresh_metrics()
        print(f"\n✅ Metrics generated. View dashboard by opening:")
        print(f"   file://{project_root}/monitoring/dashboard.html")
    else:
        serve_dashboard(port=args.port)


if __name__ == '__main__':
    main()
