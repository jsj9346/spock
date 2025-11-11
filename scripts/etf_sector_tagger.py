#!/usr/bin/env python3
"""
ETF Sector Tagging Helper

Interactive tool to manually tag ETF sectors for improved classification accuracy.
Current: ~70% accuracy (name-based) → Target: ~95% accuracy (manual verification)

Usage:
    python3 scripts/etf_sector_tagger.py [--limit 200] [--volume-sort]

Features:
- Shows ETF details (name, volume, current sector)
- Suggests sector based on name parsing
- Interactive tagging with keyboard shortcuts
- Progress tracking and resume capability
- Database updates with sector_manual column

Author: Spock Quant Platform
Date: 2025-10-31
"""

import sys
import os
import argparse
from typing import Optional, List, Dict
from datetime import datetime

sys.path.insert(0, '/Users/13ruce/spock')
os.chdir('/Users/13ruce/spock')

from modules.screening.etf_screening_adapter import ETFScreeningAdapter
from config.database import get_connection
from loguru import logger


# Predefined sector categories (expandable)
SECTOR_CATEGORIES = [
    "1. Broad Market",
    "2. Semiconductor",
    "3. Battery/Secondary Battery",
    "4. Bio/Healthcare",
    "5. Finance",
    "6. IT/Technology",
    "7. Energy",
    "8. Real Estate",
    "9. Automotive",
    "10. Chemical",
    "11. Construction",
    "12. Steel/Materials",
    "13. Retail/Consumer",
    "14. Entertainment/Media",
    "15. Game/Contents",
    "16. ESG/Sustainable",
    "17. Dividend",
    "18. Leverage/Inverse",
    "19. Commodity",
    "20. International",
    "21. Bond",
    "22. Mixed/Other"
]


class ETFSectorTagger:
    """Interactive ETF sector tagging tool"""

    def __init__(self):
        self.adapter = ETFScreeningAdapter()
        self.session_stats = {
            "tagged": 0,
            "skipped": 0,
            "errors": 0,
            "start_time": datetime.now()
        }

    async def get_etfs_for_tagging(
        self,
        limit: int = 200,
        volume_sort: bool = True
    ) -> List[Dict]:
        """
        Get ETFs for manual tagging, prioritized by volume.

        Args:
            limit: Maximum number of ETFs to tag
            volume_sort: Sort by volume (most liquid first)

        Returns:
            List of ETF dicts ready for tagging
        """
        logger.info(f"Fetching top {limit} ETFs for sector tagging...")

        # Get all ETFs with technical data
        result = await self.adapter.screen_etfs(
            filters={},
            region="KR",
            limit=limit
        )

        etfs = result.get("etfs", [])

        if volume_sort:
            # Sort by volume (liquidity proxy)
            etfs = sorted(
                etfs,
                key=lambda x: x.get("volume_avg_20d", 0),
                reverse=True
            )

        logger.info(f"Retrieved {len(etfs)} ETFs for tagging")
        return etfs

    def display_etf(self, etf: Dict, index: int, total: int) -> None:
        """Display ETF information for tagging"""
        print("\n" + "="*80)
        print(f"ETF {index + 1}/{total}")
        print("="*80)
        print(f"Ticker:          {etf['ticker']}")
        print(f"Name:            {etf['name']}")
        print(f"Current Sector:  {etf.get('sector_theme', 'Unknown')}")
        print(f"Listing Date:    {etf.get('listing_date', 'N/A')}")
        print(f"Volume (20d):    {etf.get('volume_avg_20d', 0):,.0f}")
        print(f"Price:           {etf.get('current_price', 0):,.0f} KRW")
        print(f"RSI:             {etf.get('rsi', 0):.1f}")
        print(f"MA Trend:        {etf.get('ma_trend', 'N/A')}")
        print("="*80)

    def display_sector_menu(self) -> None:
        """Display available sector categories"""
        print("\nAvailable Sectors:")
        print("-"*80)
        for i in range(0, len(SECTOR_CATEGORIES), 2):
            left = SECTOR_CATEGORIES[i]
            right = SECTOR_CATEGORIES[i+1] if i+1 < len(SECTOR_CATEGORIES) else ""
            print(f"  {left:<40} {right}")
        print("-"*80)
        print("\nShortcuts:")
        print("  [s] Skip this ETF")
        print("  [q] Quit and save progress")
        print("  [h] Show this help menu")
        print("="*80)

    def get_sector_input(self) -> Optional[str]:
        """
        Get sector input from user.

        Returns:
            Sector name, "SKIP", "QUIT", or None
        """
        while True:
            choice = input("\nEnter sector number (1-22), 's' to skip, 'q' to quit, 'h' for help: ").strip()

            if choice.lower() == 's':
                return "SKIP"
            elif choice.lower() == 'q':
                return "QUIT"
            elif choice.lower() == 'h':
                self.display_sector_menu()
                continue
            elif choice.isdigit():
                num = int(choice)
                if 1 <= num <= len(SECTOR_CATEGORIES):
                    # Extract sector name (remove number prefix)
                    sector = SECTOR_CATEGORIES[num - 1].split(". ", 1)[1]
                    return sector
                else:
                    print(f"Invalid number. Please enter 1-{len(SECTOR_CATEGORIES)}")
            else:
                print("Invalid input. Enter a number, 's', 'q', or 'h'")

    def save_sector_tag(self, ticker: str, sector: str) -> bool:
        """
        Save manual sector tag to database.

        Args:
            ticker: ETF ticker
            sector: Manually assigned sector

        Returns:
            True if successful, False otherwise
        """
        try:
            with get_connection() as conn:
                cursor = conn.cursor()

                # Check if etf_details exists
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM etf_details WHERE ticker = %s AND region = 'KR'
                    )
                """, (ticker,))
                exists = cursor.fetchone()[0]

                if exists:
                    # Update existing record
                    cursor.execute("""
                        UPDATE etf_details
                        SET sector_manual = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE ticker = %s AND region = 'KR'
                    """, (sector, ticker))
                else:
                    # Insert new record
                    cursor.execute("""
                        INSERT INTO etf_details (ticker, region, sector_manual, created_at, updated_at)
                        VALUES (%s, 'KR', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (ticker, sector))

                conn.commit()
                logger.debug(f"Saved sector tag for {ticker}: {sector}")
                return True

        except Exception as e:
            logger.error(f"Failed to save sector tag for {ticker}: {e}")
            return False

    async def run_tagging_session(
        self,
        limit: int = 200,
        volume_sort: bool = True
    ) -> None:
        """
        Run interactive tagging session.

        Args:
            limit: Maximum ETFs to process
            volume_sort: Sort by volume (most liquid first)
        """
        print("\n" + "="*80)
        print("ETF SECTOR TAGGING SESSION")
        print("="*80)
        print(f"Target: Tag up to {limit} ETFs")
        print(f"Priority: {'Volume-sorted (most liquid first)' if volume_sort else 'Alphabetical'}")
        print("="*80)

        # Get ETFs
        etfs = await self.get_etfs_for_tagging(limit, volume_sort)

        if not etfs:
            print("No ETFs found for tagging.")
            return

        # Show menu once
        self.display_sector_menu()

        # Tag each ETF
        for i, etf in enumerate(etfs):
            self.display_etf(etf, i, len(etfs))

            sector = self.get_sector_input()

            if sector == "QUIT":
                print("\nQuitting and saving progress...")
                break
            elif sector == "SKIP":
                print("Skipped.")
                self.session_stats["skipped"] += 1
                continue
            else:
                # Save to database
                success = self.save_sector_tag(etf['ticker'], sector)
                if success:
                    print(f"✅ Saved: {etf['name']} → {sector}")
                    self.session_stats["tagged"] += 1
                else:
                    print(f"❌ Failed to save sector tag")
                    self.session_stats["errors"] += 1

        # Display session summary
        self.display_summary()

    def display_summary(self) -> None:
        """Display session statistics"""
        duration = (datetime.now() - self.session_stats["start_time"]).total_seconds()

        print("\n" + "="*80)
        print("SESSION SUMMARY")
        print("="*80)
        print(f"Tagged:   {self.session_stats['tagged']}")
        print(f"Skipped:  {self.session_stats['skipped']}")
        print(f"Errors:   {self.session_stats['errors']}")
        print(f"Duration: {duration:.1f} seconds")
        print(f"Rate:     {self.session_stats['tagged'] / (duration / 60):.1f} ETFs/minute")
        print("="*80)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Interactive ETF sector tagging tool"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=200,
        help="Maximum number of ETFs to tag (default: 200)"
    )
    parser.add_argument(
        "--volume-sort",
        action="store_true",
        default=True,
        help="Sort by volume (default: True)"
    )

    args = parser.parse_args()

    tagger = ETFSectorTagger()
    await tagger.run_tagging_session(
        limit=args.limit,
        volume_sort=args.volume_sort
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
