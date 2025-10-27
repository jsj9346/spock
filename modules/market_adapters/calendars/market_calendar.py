"""
Market Calendar

Handles trading hours, market holidays, and trading day calculations for each region.

Author: Spock Trading System
"""

import logging
from datetime import datetime, time, timedelta
from typing import Optional, Dict, List, Tuple
import os
import yaml

logger = logging.getLogger(__name__)


class MarketCalendar:
    """
    Market calendar manager for global stock markets

    Handles:
    - Trading hours (local timezone)
    - Market holidays
    - Trading day calculations
    - Market status checks
    """

    # Trading hours configuration (local timezone)
    TRADING_HOURS = {
        'KR': {
            'open': time(9, 0),
            'close': time(15, 30),
            'timezone': 'Asia/Seoul',
            'name': 'Korea Exchange'
        },
        'US': {
            'open': time(9, 30),
            'close': time(16, 0),
            'timezone': 'America/New_York',
            'name': 'US Stock Exchanges'
        },
        'CN': {
            'open': time(9, 30),
            'close': time(15, 0),
            'timezone': 'Asia/Shanghai',
            'name': 'Chinese Stock Exchanges',
            'lunch_break': (time(11, 30), time(13, 0))  # 11:30-13:00 lunch break
        },
        'HK': {
            'open': time(9, 30),
            'close': time(16, 0),
            'timezone': 'Asia/Hong_Kong',
            'name': 'Hong Kong Stock Exchange',
            'lunch_break': (time(12, 0), time(13, 0))  # 12:00-13:00 lunch break
        },
        'JP': {
            'open': time(9, 0),
            'close': time(15, 0),
            'timezone': 'Asia/Tokyo',
            'name': 'Tokyo Stock Exchange',
            'lunch_break': (time(11, 30), time(12, 30))  # 11:30-12:30 lunch break
        },
        'VN': {
            'open': time(9, 0),
            'close': time(14, 45),
            'timezone': 'Asia/Ho_Chi_Minh',
            'name': 'Vietnamese Stock Exchanges'
        }
    }

    # Weekend days (0=Monday, 6=Sunday)
    WEEKEND_DAYS = {
        'KR': [5, 6],      # Saturday, Sunday
        'US': [5, 6],      # Saturday, Sunday
        'CN': [5, 6],      # Saturday, Sunday
        'HK': [5, 6],      # Saturday, Sunday
        'JP': [5, 6],      # Saturday, Sunday
        'VN': [5, 6]       # Saturday, Sunday
    }

    def __init__(self, region: str, holidays_file: Optional[str] = None):
        """
        Initialize market calendar

        Args:
            region: Region code (KR, US, CN, HK, JP, VN)
            holidays_file: Path to YAML file with market holidays (optional)
        """
        self.region = region
        self.holidays = []

        if region not in self.TRADING_HOURS:
            raise ValueError(f"Unsupported region: {region}")

        self.config = self.TRADING_HOURS[region]

        # Load holidays from file if provided
        if holidays_file and os.path.exists(holidays_file):
            self.load_holidays(holidays_file)

    def load_holidays(self, filepath: str) -> bool:
        """
        Load market holidays from YAML file

        Args:
            filepath: Path to holidays YAML file

        Returns:
            True if successful
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            # Extract holidays list
            if isinstance(data, dict):
                # Format: {2025: ['2025-01-01', '2025-07-04', ...]}
                all_holidays = []
                for year, dates in data.items():
                    if isinstance(dates, list):
                        all_holidays.extend(dates)
                self.holidays = all_holidays
            elif isinstance(data, list):
                # Format: ['2025-01-01', '2025-07-04', ...]
                self.holidays = data

            logger.info(f"✅ Loaded {len(self.holidays)} holidays for {self.region}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to load holidays from {filepath}: {e}")
            return False

    def is_trading_day(self, date: Optional[datetime] = None) -> bool:
        """
        Check if given date is a trading day

        Args:
            date: Date to check (default: today)

        Returns:
            True if trading day, False if weekend or holiday
        """
        if date is None:
            date = datetime.now()

        # Check if weekend
        if date.weekday() in self.WEEKEND_DAYS[self.region]:
            return False

        # Check if holiday
        date_str = date.strftime('%Y-%m-%d')
        if date_str in self.holidays:
            return False

        return True

    def is_market_open(self, now: Optional[datetime] = None) -> bool:
        """
        Check if market is currently open

        Args:
            now: Current time (default: now)

        Returns:
            True if market is open
        """
        if now is None:
            now = datetime.now()

        # Check if trading day
        if not self.is_trading_day(now):
            return False

        # Check trading hours
        current_time = now.time()
        open_time = self.config['open']
        close_time = self.config['close']

        # Check if within trading hours
        if not (open_time <= current_time <= close_time):
            return False

        # Check lunch break (if applicable)
        if 'lunch_break' in self.config:
            lunch_start, lunch_end = self.config['lunch_break']
            if lunch_start <= current_time <= lunch_end:
                return False

        return True

    def get_trading_hours(self) -> Tuple[time, time]:
        """
        Get trading hours for this market

        Returns:
            Tuple of (open_time, close_time)
        """
        return self.config['open'], self.config['close']

    def get_next_trading_day(self, date: Optional[datetime] = None) -> datetime:
        """
        Get next trading day after given date

        Args:
            date: Starting date (default: today)

        Returns:
            Next trading day
        """
        if date is None:
            date = datetime.now()

        next_day = date + timedelta(days=1)

        # Keep advancing until we find a trading day
        max_attempts = 30  # Prevent infinite loop
        attempts = 0

        while not self.is_trading_day(next_day) and attempts < max_attempts:
            next_day += timedelta(days=1)
            attempts += 1

        if attempts >= max_attempts:
            logger.warning(f"⚠️ Could not find next trading day within 30 days")

        return next_day

    def get_previous_trading_day(self, date: Optional[datetime] = None) -> datetime:
        """
        Get previous trading day before given date

        Args:
            date: Starting date (default: today)

        Returns:
            Previous trading day
        """
        if date is None:
            date = datetime.now()

        prev_day = date - timedelta(days=1)

        # Keep going back until we find a trading day
        max_attempts = 30
        attempts = 0

        while not self.is_trading_day(prev_day) and attempts < max_attempts:
            prev_day -= timedelta(days=1)
            attempts += 1

        if attempts >= max_attempts:
            logger.warning(f"⚠️ Could not find previous trading day within 30 days")

        return prev_day

    def get_trading_days_between(self, start_date: datetime, end_date: datetime) -> List[datetime]:
        """
        Get list of trading days between two dates

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of trading days
        """
        trading_days = []
        current_date = start_date

        while current_date <= end_date:
            if self.is_trading_day(current_date):
                trading_days.append(current_date)
            current_date += timedelta(days=1)

        return trading_days

    def get_trading_sessions(self) -> List[Tuple[time, time]]:
        """
        Get trading sessions (handles markets with lunch breaks)

        Returns:
            List of (start_time, end_time) tuples
        """
        sessions = []

        open_time = self.config['open']
        close_time = self.config['close']

        if 'lunch_break' in self.config:
            lunch_start, lunch_end = self.config['lunch_break']
            sessions.append((open_time, lunch_start))  # Morning session
            sessions.append((lunch_end, close_time))   # Afternoon session
        else:
            sessions.append((open_time, close_time))   # Single session

        return sessions

    def get_time_until_open(self, now: Optional[datetime] = None) -> Optional[timedelta]:
        """
        Get time until market opens

        Args:
            now: Current time (default: now)

        Returns:
            Time delta until market opens, or None if market is open
        """
        if now is None:
            now = datetime.now()

        if self.is_market_open(now):
            return None

        # Find next trading day
        next_trading_day = self.get_next_trading_day(now) if not self.is_trading_day(now) else now

        # Get opening time on next trading day
        open_datetime = datetime.combine(next_trading_day.date(), self.config['open'])

        # Calculate time difference
        time_until_open = open_datetime - now

        return time_until_open

    def get_time_until_close(self, now: Optional[datetime] = None) -> Optional[timedelta]:
        """
        Get time until market closes

        Args:
            now: Current time (default: now)

        Returns:
            Time delta until market closes, or None if market is closed
        """
        if now is None:
            now = datetime.now()

        if not self.is_market_open(now):
            return None

        # Get closing time today
        close_datetime = datetime.combine(now.date(), self.config['close'])

        # Calculate time difference
        time_until_close = close_datetime - now

        return time_until_close

    def get_market_status(self, now: Optional[datetime] = None) -> Dict:
        """
        Get comprehensive market status

        Args:
            now: Current time (default: now)

        Returns:
            Dictionary with market status information
        """
        if now is None:
            now = datetime.now()

        is_open = self.is_market_open(now)
        is_trading_day_today = self.is_trading_day(now)

        status = {
            'region': self.region,
            'market_name': self.config['name'],
            'current_time': now,
            'is_open': is_open,
            'is_trading_day': is_trading_day_today,
            'trading_hours': self.get_trading_hours(),
            'timezone': self.config['timezone']
        }

        if is_open:
            status['time_until_close'] = self.get_time_until_close(now)
            status['status_message'] = '🟢 Market is OPEN'
        elif is_trading_day_today:
            current_time = now.time()
            if current_time < self.config['open']:
                status['time_until_open'] = self.get_time_until_open(now)
                status['status_message'] = '🟡 Pre-market (waiting for open)'
            else:
                status['status_message'] = '🔴 After-hours (market closed)'
        else:
            status['time_until_open'] = self.get_time_until_open(now)
            status['next_trading_day'] = self.get_next_trading_day(now)
            status['status_message'] = '🔴 Market CLOSED (weekend/holiday)'

        return status

    def __repr__(self) -> str:
        return f"<MarketCalendar region={self.region} holidays={len(self.holidays)}>"
