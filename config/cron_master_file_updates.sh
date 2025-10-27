#!/bin/bash
# Cron Configuration for Master File Updates
#
# This file contains cron job configurations for automated master file updates.
# DO NOT add this directly to crontab - use it as reference.
#
# To install:
#   1. Make this script executable: chmod +x config/cron_master_file_updates.sh
#   2. Edit your crontab: crontab -e
#   3. Copy the cron entries below (adjust paths and timezone as needed)
#
# Author: Spock Trading System
# Date: 2025-10-15

# =============================================================================
# IMPORTANT: Timezone Configuration
# =============================================================================
#
# These cron times are configured for servers running in KST (Korea Standard Time)
# If your server is in a different timezone, adjust the times accordingly.
#
# KST = UTC+9
# - 6:00 AM KST = 21:00 UTC (previous day)
# - 3:00 AM KST = 18:00 UTC (previous day)
#
# To check your server timezone:
#   timedatectl  # Linux
#   date +%Z     # macOS/Linux
#
# To set timezone to KST (Linux):
#   sudo timedatectl set-timezone Asia/Seoul
#
# To set timezone to KST (macOS):
#   sudo systemsetup -settimezone Asia/Seoul
#
# =============================================================================

# =============================================================================
# Cron Job Entries
# =============================================================================

# -------------------------
# Daily Master File Update
# -------------------------
# Runs every day at 6:00 AM KST
# Updates all regions (US, HK, JP, CN, VN)
# Timing rationale:
#   - After US market close (4:00 PM ET = 5:00 AM KST next day)
#   - Before Asian market open (9:00 AM local times)
#   - Ensures fresh data for next trading day
#
# Syntax: minute hour day month weekday command
# 0 6 * * * /path/to/command

0 6 * * * cd /Users/13ruce/spock && /usr/bin/python3 scripts/update_master_files.py >> logs/cron_master_file_updates.log 2>&1

# -------------------------
# Weekly Full Refresh
# -------------------------
# Runs every Sunday at 3:00 AM KST
# Force refresh + comprehensive validation
# Timing rationale:
#   - Weekend (markets closed)
#   - Before Monday market open
#   - Full validation without time pressure
#
0 3 * * 0 cd /Users/13ruce/spock && /usr/bin/python3 scripts/update_master_files.py --regions US HK JP CN VN >> logs/cron_weekly_updates.log 2>&1

# =============================================================================
# Cron Environment Variables
# =============================================================================
# Add these at the top of your crontab (before the cron entries)
#
# PATH=/usr/local/bin:/usr/bin:/bin
# SHELL=/bin/bash
# MAILTO=""  # Set to your email if you want cron output via email
#
# Note: Cron jobs run with a minimal environment.
# Ensure all paths are absolute and environment variables are loaded from .env
# =============================================================================

# =============================================================================
# Installation Instructions
# =============================================================================
#
# 1. Open crontab editor:
#    crontab -e
#
# 2. Add environment variables (at the top):
#    PATH=/usr/local/bin:/usr/bin:/bin
#    SHELL=/bin/bash
#
# 3. Copy the cron job entries from above (adjust paths if needed)
#
# 4. Save and exit the editor
#
# 5. Verify cron jobs are installed:
#    crontab -l
#
# 6. Check cron is running:
#    # macOS
#    sudo launchctl list | grep cron
#
#    # Linux
#    systemctl status cron
#    # or
#    systemctl status crond
#
# 7. Monitor logs:
#    tail -f logs/cron_master_file_updates.log
#
# =============================================================================

# =============================================================================
# Troubleshooting
# =============================================================================
#
# Issue 1: Cron job not running
# Solution: Check cron service is running and crontab syntax is correct
#
# Issue 2: Script fails with "command not found"
# Solution: Use absolute paths for all commands (/usr/bin/python3)
#
# Issue 3: Environment variables not loaded
# Solution: Source .env in script or use absolute paths
#
# Issue 4: Permission denied
# Solution: Ensure script is executable (chmod +x scripts/update_master_files.py)
#
# Issue 5: No output in logs
# Solution: Check file permissions on log directory and redirect stderr (2>&1)
#
# =============================================================================

# =============================================================================
# Testing Cron Jobs
# =============================================================================
#
# Test cron job manually (simulates cron environment):
#   cd /Users/13ruce/spock && /usr/bin/python3 scripts/update_master_files.py
#
# Test with dry-run:
#   cd /Users/13ruce/spock && /usr/bin/python3 scripts/update_master_files.py --dry-run
#
# Test specific region:
#   cd /Users/13ruce/spock && /usr/bin/python3 scripts/update_master_files.py --regions US
#
# =============================================================================

# =============================================================================
# Alternative: systemd Timer (Linux Production)
# =============================================================================
#
# For production Linux servers, systemd timers are recommended over cron.
# See: docs/MASTER_FILE_DEPLOYMENT_PLAN.md (Phase 2, Step 4)
#
# Benefits:
#   - Better logging integration (journalctl)
#   - Dependency management
#   - Automatic retry on failure
#   - More flexible scheduling
#
# =============================================================================
