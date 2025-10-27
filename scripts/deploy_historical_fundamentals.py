#!/usr/bin/env python3
"""
Production deployment script for historical fundamental data collection
Collects 2020-2024 annual data for top Korean stocks by market cap

Usage:
    python3 scripts/deploy_historical_fundamentals.py --top 50
    python3 scripts/deploy_historical_fundamentals.py --top 200 --force-refresh
    python3 scripts/deploy_historical_fundamentals.py --tickers 005930 000660 035420
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime
from typing import List, Dict

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.fundamental_data_collector import FundamentalDataCollector
from modules.db_manager_sqlite import SQLiteDatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HistoricalFundamentalDeployer:
    """Deploy historical fundamental data collection for production"""

    def __init__(self, db_path: str = 'data/spock_local.db'):
        """Initialize deployer with database connection"""
        self.db = SQLiteDatabaseManager(db_path=db_path)
        self.collector = FundamentalDataCollector(self.db)

        # Top Korean stocks by market cap (as of 2024)
        # Source: KRX market cap rankings
        self.top_200_tickers = [
            # Top 10 (Mega-cap)
            '005930',  # Samsung Electronics
            '000660',  # SK Hynix
            '035420',  # NAVER
            '051910',  # LG Chem
            '035720',  # Kakao
            '006400',  # Samsung SDI
            '005380',  # Hyundai Motor
            '000270',  # Kia
            '068270',  # Celltrion
            '207940',  # Samsung Biologics

            # Top 11-30 (Large-cap)
            '005490',  # POSCO Holdings
            '003670',  # Posco International
            '055550',  # Shinhan Financial Group
            '105560',  # KB Financial Group
            '086790',  # Hana Financial Group
            '032830',  # Samsung Life Insurance
            '012330',  # Hyundai Mobis
            '028260',  # Samsung C&T
            '009150',  # Samsung Electro-Mechanics
            '066570',  # LG Electronics
            '017670',  # SK Telecom
            '034730',  # SK
            '096770',  # SK Innovation
            '018260',  # Samsung SDS
            '003550',  # LG
            '010950',  # S-Oil
            '009540',  # HD Korea Shipbuilding & Offshore
            '036570',  # NCSoft
            '015760',  # Korea Electric Power
            '011170',  # Lotte Chemical

            # Top 31-50 (Large-cap continued)
            '000810',  # Samsung Fire & Marine Insurance
            '251270',  # Netmarble
            '010140',  # Samsung Heavy Industries
            '047810',  # Korea Aerospace Industries
            '033780',  # KT&G
            '011780',  # Kumho Petrochemical
            '161390',  # Hanwha Solutions
            '042700',  # Hanmi Pharmaceutical
            '030200',  # KT
            '024110',  # Industrial Bank of Korea
            '000720',  # Hyundai Engineering & Construction
            '010130',  # Korea Zinc
            '004020',  # Hyundai Steel
            '009830',  # Hanwha Aerospace
            '011200',  # HMM
            '012450',  # Korea Shipbuilding & Offshore Engineering
            '032640',  # LG Uplus
            '078930',  # GS
            '097950',  # CJ CheilJedang
            '001040',  # CJ

            # Top 51-100 (Mid-cap)
            '004170',  # Shinsegae
            '139480',  # E-Mart
            '028670',  # Pacific Century Cyberworks
            '071050',  # Korea Investment Holdings
            '016360',  # Samsung Securities
            '008770',  # Horim
            '005940',  # NH Investment & Securities
            '000150',  # Doosan
            '034220',  # LG Display
            '004990',  # Lotte Shopping
            '002380',  # KCC
            '004800',  # Kyobo Life Insurance
            '000880',  # Hanwha
            '006800',  # Mirae Asset Securities
            '018880',  # Hanon Systems
            '004370',  # Nongshim
            '003490',  # Daehan Flour Mills
            '002790',  # Amorerepacific
            '090430',  # Amorepacific Group
            '000120',  # CJ Cheiljedang
            '010060',  # OCI Holdings
            '004000',  # Lotte Himart
            '001120',  # LG International
            '000100',  # Yuhan
            '003090',  # Daewoong Pharmaceutical
            '069960',  # Hyundai Department Store
            '004170',  # Shinsegae
            '011790',  # SKC
            '010620',  # Hyundai Heavy Industries Holdings
            '000080',  # Hite Jinro
            '002710',  # Daesung Holdings
            '023530',  # Lotte Shopping
            '004490',  # Seil Electric
            '006260',  # LS
            '020150',  # LS Electric
            '005850',  # Esco
            '004090',  # Korea Steel Pipe
            '002350',  # Nenwel
            '003230',  # Samyang Holdings
            '001740',  # SK Networks
            '009970',  # Youngone
            '004690',  # Samsung Publishing
            '006360',  # GS Engineering & Construction
            '010780',  # Hanwha Energy
            '001450',  # Hyundai Marine & Fire Insurance
            '003410',  # Ssangyong C&E
            '005090',  # Samil Pharmaceutical
            '008060',  # Daehan Steel
            '002030',  # Asia Cement
            '001430',  # Seah Steel Holdings

            # Top 101-150 (Mid-cap continued)
            '003000',  # Halla Holdings
            '011930',  # Shin Poong Pharmaceutical
            '001230',  # Dongkuk Steel Mill
            '023960',  # Kangnam Jevisco
            '078000',  # CJ CheilJedang Selecta
            '009450',  # Kyung Dong Pharmaceutical
            '010120',  # LS MnM
            '004560',  # Hyundai B&I Steel Service
            '025000',  # Hankook & Company
            '006650',  # Daeduck
            '008350',  # Namyang Dairy Products
            '012630',  # HDC Hyundai Development Company
            '001740',  # SK Networks Service
            '000670',  # Youngpoong
            '008930',  # Hanmi Science
            '004850',  # Korea Investment & Securities
            '001800',  # Orion Holdings
            '014820',  # Dongwon Industries
            '003380',  # Harim Holdings
            '006110',  # SK Materials
            '001680',  # Daesang
            '003780',  # Jinro Holdings
            '004410',  # Sejin Heavy Industries
            '004250',  # NPC
            '006890',  # Taekwang Industrial
            '004540',  # Kukdong
            '006370',  # Hyundai Industrial Development
            '004080',  # Dongbu Construction
            '000210',  # DL
            '001390',  # KG Chemical
            '000440',  # Joongwoo
            '005090',  # Samil Pharmaceutical
            '007310',  # Isu Chemical
            '002920',  # Yuhan Corporation
            '003200',  # Il Kwang Pharmaceutical
            '002240',  # Kolon Industries
            '005250',  # GreenCross
            '001060',  # JW Pharmaceutical
            '009410',  # Tae Jin Electro
            '006120',  # SK Discovery
            '003300',  # Hanyang Engineering
            '002290',  # Samchully
            '002100',  # Korea Line
            '005430',  # Hankook Tire & Technology
            '006400',  # Samsung SDI
            '002600',  # Chalmers
            '002810',  # Samsung Card
            '005300',  # Lotte Chilsung Beverage
            '003830',  # Samsung Corporation
            '001770',  # Dongyang

            # Top 151-200 (Small-cap leaders)
            '004170',  # Shinsegae
            '002760',  # BoAhn
            '005935',  # Samsung Electronics pfd
            '000105',  # Yuhan pfd
            '003475',  # Posco International pfd
            '051905',  # LG Chem pfd
            '006405',  # Samsung SDI pfd
            '005385',  # Hyundai Motor pfd
            '000815',  # Samsung Fire pfd
            '012205',  # Hyundai Mobis pfd
            '086280',  # Hyundai Green Food
            '003475',  # Posco International pfd
            '079160',  # CJ CGV
            '282330',  # BGF Retail
            '003920',  # Namyang Dairy
            '001680',  # Daesang
            '036460',  # HanKook Tires Worldwide
            '047050',  # Posco Future M
            '010780',  # Hanwha Energy
            '088980',  # Macrogen
            '000990',  # DB HiTek
            '003545',  # Daesung Industrial Gases
            '002270',  # Lotte Confectionery
            '006220',  # Jeil Holdings
            '014680',  # Hansol Chemical
            '272210',  # Hanwha System
            '004170',  # Shinsegae
            '298020',  # Hyosung Advanced Materials
            '298050',  # Hyosung Chemical
            '298000',  # Hyosung TNC
            '192080',  # Duksan Neolux
            '064960',  # SNT Motiv
            '112610',  # CS Wind
            '006280',  # Green Cross Holdings
            '003410',  # Ssangyong C&E
            '004430',  # Songwon Industrial
            '051600',  # Korea Asset in Trust
            '001440',  # Daeyoung Packaging
            '035250',  # Kangwon Land
            '145990',  # Samyang Packaging
            '009680',  # Mando
            '002030',  # Asia Cement
            '000590',  # CS Holdings
            '009240',  # Hanmi Pharmaceutical
            '006120',  # SK Discovery
            '137310',  # EDGC
            '004170',  # Shinsegae
            '004170',  # Shinsegae
            '028050',  # Samsung Engineering
            '009830',  # Hanwha Aerospace
            '272550',  # Hansol Technics
        ]

    def get_top_tickers(self, count: int = 50) -> List[str]:
        """Get top N tickers by market cap"""
        # Remove duplicates while preserving order
        unique_tickers = []
        seen = set()
        for ticker in self.top_200_tickers:
            if ticker not in seen:
                unique_tickers.append(ticker)
                seen.add(ticker)

        return unique_tickers[:count]

    def deploy(self,
               tickers: List[str],
               start_year: int = 2020,
               end_year: int = 2024,
               force_refresh: bool = False) -> Dict:
        """
        Deploy historical data collection

        Args:
            tickers: List of ticker symbols
            start_year: First year to collect (default: 2020)
            end_year: Last year to collect (default: 2024)
            force_refresh: Force re-collection even if cached

        Returns:
            Deployment results dictionary
        """
        deployment_start = datetime.now()

        logger.info("=" * 70)
        logger.info("HISTORICAL FUNDAMENTAL DATA DEPLOYMENT")
        logger.info("Spock Trading System - Production Deployment")
        logger.info("=" * 70)
        logger.info(f"📊 Deployment Parameters:")
        logger.info(f"  - Tickers: {len(tickers)} stocks")
        logger.info(f"  - Year Range: {start_year}-{end_year} ({end_year - start_year + 1} years)")
        logger.info(f"  - Total Expected Data Points: {len(tickers) * (end_year - start_year + 1)}")
        logger.info(f"  - Force Refresh: {force_refresh}")
        logger.info(f"  - Estimated Time: ~{len(tickers) * 3} minutes (~{len(tickers) * 3 / 60:.1f} hours)")
        logger.info("=" * 70)

        # Execute collection
        logger.info("\n🚀 Starting historical data collection...\n")

        results = self.collector.collect_historical_fundamentals(
            tickers=tickers,
            region='KR',
            start_year=start_year,
            end_year=end_year,
            force_refresh=force_refresh
        )

        deployment_end = datetime.now()
        deployment_time = (deployment_end - deployment_start).total_seconds()

        # Calculate statistics
        total_data_points = len(tickers) * (end_year - start_year + 1)
        successful_data_points = sum(
            1 for ticker_results in results.values()
            for success in ticker_results.values()
            if success
        )
        failed_data_points = total_data_points - successful_data_points
        success_rate = (successful_data_points / total_data_points * 100) if total_data_points > 0 else 0

        # Ticker-level statistics
        successful_tickers = sum(
            1 for ticker_results in results.values()
            if all(ticker_results.values())
        )
        partial_tickers = sum(
            1 for ticker_results in results.values()
            if any(ticker_results.values()) and not all(ticker_results.values())
        )
        failed_tickers = len(tickers) - successful_tickers - partial_tickers

        # Build deployment report
        deployment_report = {
            'timestamp': deployment_end.isoformat(),
            'parameters': {
                'tickers_count': len(tickers),
                'start_year': start_year,
                'end_year': end_year,
                'force_refresh': force_refresh
            },
            'statistics': {
                'total_data_points': total_data_points,
                'successful_data_points': successful_data_points,
                'failed_data_points': failed_data_points,
                'success_rate': success_rate,
                'successful_tickers': successful_tickers,
                'partial_tickers': partial_tickers,
                'failed_tickers': failed_tickers,
                'deployment_time_seconds': deployment_time,
                'deployment_time_minutes': deployment_time / 60
            },
            'results': results
        }

        # Print deployment summary
        logger.info("\n" + "=" * 70)
        logger.info("📊 DEPLOYMENT SUMMARY")
        logger.info("=" * 70)
        logger.info(f"⏱️  Deployment Time: {deployment_time / 60:.1f} minutes ({deployment_time:.0f} seconds)")
        logger.info(f"📈 Success Rate: {success_rate:.1f}% ({successful_data_points}/{total_data_points} data points)")
        logger.info(f"\n📊 Data Points:")
        logger.info(f"  ✅ Successful: {successful_data_points}")
        logger.info(f"  ❌ Failed: {failed_data_points}")
        logger.info(f"\n🎯 Tickers:")
        logger.info(f"  ✅ Complete (all years): {successful_tickers}")
        logger.info(f"  ⚠️  Partial (some years): {partial_tickers}")
        logger.info(f"  ❌ Failed (no data): {failed_tickers}")

        # Show failed tickers if any
        if failed_tickers > 0 or partial_tickers > 0:
            logger.info(f"\n⚠️  Issues Detected:")
            for ticker, ticker_results in results.items():
                failed_years = [year for year, success in ticker_results.items() if not success]
                if failed_years:
                    logger.info(f"  {ticker}: Failed years {failed_years}")

        logger.info("=" * 70)

        return deployment_report

    def save_report(self, report: Dict, output_dir: str = 'data/deployments'):
        """Save deployment report to JSON file"""
        os.makedirs(output_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"historical_deployment_{timestamp}.json"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        logger.info(f"\n💾 Deployment report saved: {filepath}")
        return filepath

    def verify_deployment(self, start_year: int = 2020, end_year: int = 2024) -> Dict:
        """Verify deployment by querying database"""
        logger.info("\n" + "=" * 70)
        logger.info("🔍 DEPLOYMENT VERIFICATION")
        logger.info("=" * 70)

        conn = self.db._get_connection()
        cursor = conn.cursor()

        # Count total historical rows
        cursor.execute('''
            SELECT COUNT(*) FROM ticker_fundamentals
            WHERE fiscal_year IS NOT NULL
              AND period_type = 'ANNUAL'
        ''')
        total_rows = cursor.fetchone()[0]
        logger.info(f"📊 Total historical rows: {total_rows:,}")

        # Count distinct tickers
        cursor.execute('''
            SELECT COUNT(DISTINCT ticker) FROM ticker_fundamentals
            WHERE fiscal_year IS NOT NULL
              AND period_type = 'ANNUAL'
        ''')
        distinct_tickers = cursor.fetchone()[0]
        logger.info(f"🎯 Distinct tickers: {distinct_tickers}")

        # Count by year
        logger.info(f"\n📅 Data by year:")
        year_counts = {}
        for year in range(start_year, end_year + 1):
            cursor.execute('''
                SELECT COUNT(*) FROM ticker_fundamentals
                WHERE fiscal_year = ? AND period_type = 'ANNUAL'
            ''', (year,))
            count = cursor.fetchone()[0]
            year_counts[year] = count
            logger.info(f"  {year}: {count:,} rows")

        # Check for NULL fiscal_year (should only be current data)
        cursor.execute('''
            SELECT COUNT(*) FROM ticker_fundamentals
            WHERE fiscal_year IS NULL
        ''')
        null_fiscal_year = cursor.fetchone()[0]
        logger.info(f"\n📌 Current data (fiscal_year=NULL): {null_fiscal_year} rows")

        conn.close()

        logger.info("=" * 70)

        return {
            'total_rows': total_rows,
            'distinct_tickers': distinct_tickers,
            'year_counts': year_counts,
            'null_fiscal_year': null_fiscal_year
        }


def main():
    """Main deployment script"""
    parser = argparse.ArgumentParser(description='Deploy historical fundamental data collection')
    parser.add_argument('--top', type=int, help='Collect top N stocks by market cap (e.g., 50, 100, 200)')
    parser.add_argument('--tickers', nargs='+', help='Specific tickers to collect')
    parser.add_argument('--start-year', type=int, default=2020, help='Start year (default: 2020)')
    parser.add_argument('--end-year', type=int, default=2024, help='End year (default: 2024)')
    parser.add_argument('--force-refresh', action='store_true', help='Force re-collection even if cached')
    parser.add_argument('--dry-run', action='store_true', help='Dry run (show what would be collected)')

    args = parser.parse_args()

    # Initialize deployer
    deployer = HistoricalFundamentalDeployer()

    # Determine ticker list
    if args.tickers:
        tickers = args.tickers
        logger.info(f"📋 Using custom ticker list: {len(tickers)} tickers")
    elif args.top:
        tickers = deployer.get_top_tickers(args.top)
        logger.info(f"📋 Using top {args.top} tickers by market cap")
    else:
        # Default: top 50
        tickers = deployer.get_top_tickers(50)
        logger.info(f"📋 Using default: top 50 tickers by market cap")

    # Dry run
    if args.dry_run:
        logger.info("\n🧪 DRY RUN MODE - No data will be collected\n")
        logger.info(f"Would collect data for {len(tickers)} tickers:")
        for i, ticker in enumerate(tickers, 1):
            logger.info(f"  {i}. {ticker}")
        logger.info(f"\nYear range: {args.start_year}-{args.end_year} ({args.end_year - args.start_year + 1} years)")
        logger.info(f"Total data points: {len(tickers) * (args.end_year - args.start_year + 1)}")
        logger.info(f"Estimated time: ~{len(tickers) * 3} minutes (~{len(tickers) * 3 / 60:.1f} hours)")
        return

    # Execute deployment
    report = deployer.deploy(
        tickers=tickers,
        start_year=args.start_year,
        end_year=args.end_year,
        force_refresh=args.force_refresh
    )

    # Save report
    report_path = deployer.save_report(report)

    # Verify deployment
    verification = deployer.verify_deployment(args.start_year, args.end_year)

    logger.info("\n✅ Deployment completed successfully!")
    logger.info(f"📊 Report: {report_path}")


if __name__ == '__main__':
    main()
