#!/usr/bin/env python3
"""
KIS API Credential Setup Helper

Purpose: Interactive helper to securely store KIS API credentials
Usage: python3 scripts/setup_credentials.py
"""

import os
import sys
from pathlib import Path
from getpass import getpass
import logging

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


class CredentialSetupHelper:
    """Interactive credential setup helper"""

    def __init__(self):
        """Initialize setup helper"""
        self.env_path = project_root / '.env'
        self.gitignore_path = project_root / '.gitignore'

    def run_interactive_setup(self):
        """Run interactive credential setup"""
        logger.info("🔐 KIS API Credential Setup Helper")
        logger.info("=" * 60)
        logger.info("")
        logger.info("This tool will help you securely store your KIS API credentials.")
        logger.info("Your credentials will be saved to .env file (not committed to git).")
        logger.info("")

        # Check if .env already exists
        if self.env_path.exists():
            logger.warning("⚠️  .env file already exists")
            response = input("Do you want to overwrite it? (y/N): ").strip().lower()
            if response != 'y':
                logger.info("❌ Setup cancelled")
                return False

        # Collect credentials
        logger.info("📝 Enter your KIS API credentials:")
        logger.info("   (You can find these in KIS API Portal → My Page → App Management)")
        logger.info("")

        app_key = self._prompt_credential(
            "APP_KEY (20 characters)",
            min_length=20,
            max_length=20
        )

        app_secret = self._prompt_credential(
            "APP_SECRET (40 characters)",
            min_length=40,
            max_length=40,
            secure=True
        )

        base_url = input("BASE_URL [https://openapi.koreainvestment.com:9443]: ").strip()
        if not base_url:
            base_url = "https://openapi.koreainvestment.com:9443"

        # Optional: Account information
        logger.info("")
        logger.info("📋 Optional: Account Information (for trading)")
        response = input("Do you want to add account information? (y/N): ").strip().lower()

        account_number = ""
        account_product_code = "01"

        if response == 'y':
            account_number = input("Account Number (format: 12345678-01): ").strip()
            account_product_code = input("Account Product Code [01]: ").strip() or "01"

        # Environment selection
        logger.info("")
        logger.info("🌐 API Environment:")
        logger.info("   1. Real (Production)")
        logger.info("   2. Mock (Testing)")
        env_choice = input("Select environment [1]: ").strip() or "1"
        environment = "real" if env_choice == "1" else "mock"

        # Create .env file
        self._write_env_file(
            app_key=app_key,
            app_secret=app_secret,
            base_url=base_url,
            account_number=account_number,
            account_product_code=account_product_code,
            environment=environment
        )

        # Setup .gitignore
        self._update_gitignore()

        # Set secure permissions
        self._set_secure_permissions()

        # Validation
        logger.info("")
        logger.info("✅ Credentials saved successfully!")
        logger.info("")
        logger.info("📋 Next Steps:")
        logger.info("   1. Validate credentials:")
        logger.info("      python3 scripts/validate_kis_credentials.py")
        logger.info("")
        logger.info("   2. Test connection:")
        logger.info("      python3 scripts/test_kis_connection.py")
        logger.info("")
        logger.info("   3. Run deployment:")
        logger.info("      python3 scripts/deploy_us_adapter.py --full")
        logger.info("")

        return True

    def _prompt_credential(self, name: str, min_length: int = 0, max_length: int = 0,
                          secure: bool = False) -> str:
        """Prompt for credential with validation

        Args:
            name: Credential name
            min_length: Minimum length
            max_length: Maximum length
            secure: Use secure input (hide characters)

        Returns:
            str: Validated credential
        """
        while True:
            if secure:
                value = getpass(f"{name}: ")
            else:
                value = input(f"{name}: ").strip()

            # Validate length
            if min_length > 0 and len(value) < min_length:
                logger.error(f"   ❌ Too short (minimum {min_length} characters)")
                continue

            if max_length > 0 and len(value) > max_length:
                logger.error(f"   ❌ Too long (maximum {max_length} characters)")
                continue

            # Confirm if not secure input
            if not secure:
                logger.info(f"   Preview: {value[:4]}***{value[-4:] if len(value) > 8 else ''}")

            return value

    def _write_env_file(self, app_key: str, app_secret: str, base_url: str,
                       account_number: str, account_product_code: str,
                       environment: str):
        """Write credentials to .env file

        Args:
            app_key: KIS APP_KEY
            app_secret: KIS APP_SECRET
            base_url: KIS API base URL
            account_number: KIS account number
            account_product_code: Account product code
            environment: API environment (real/mock)
        """
        env_content = f"""# KIS API Credentials
# Generated by setup_credentials.py

# API Credentials
KIS_APP_KEY={app_key}
KIS_APP_SECRET={app_secret}
KIS_BASE_URL={base_url}

# Account Information (for trading)
"""

        if account_number:
            env_content += f"""KIS_ACCOUNT_NUMBER={account_number}
KIS_ACCOUNT_PRODUCT_CODE={account_product_code}
"""
        else:
            env_content += f"""# KIS_ACCOUNT_NUMBER=12345678-01
# KIS_ACCOUNT_PRODUCT_CODE=01
"""

        env_content += f"""
# API Environment
KIS_ENVIRONMENT={environment}

# Optional: OpenAI GPT-4 (for chart analysis)
# OPENAI_API_KEY=your_openai_key_here
"""

        # Write to file
        with open(self.env_path, 'w') as f:
            f.write(env_content)

        logger.info(f"✅ .env file created: {self.env_path}")

    def _update_gitignore(self):
        """Update .gitignore to exclude .env file"""
        gitignore_entries = [
            '.env',
            '*.env',
            '.env.*',
            '*.log',
            '__pycache__/',
            '*.pyc'
        ]

        if self.gitignore_path.exists():
            # Read existing .gitignore
            with open(self.gitignore_path, 'r') as f:
                existing_content = f.read()

            # Add missing entries
            added_entries = []
            for entry in gitignore_entries:
                if entry not in existing_content:
                    added_entries.append(entry)

            if added_entries:
                with open(self.gitignore_path, 'a') as f:
                    f.write("\n# KIS API credentials (added by setup_credentials.py)\n")
                    for entry in added_entries:
                        f.write(f"{entry}\n")

                logger.info(f"✅ .gitignore updated: {len(added_entries)} entries added")
            else:
                logger.info(f"✅ .gitignore already configured")
        else:
            # Create new .gitignore
            with open(self.gitignore_path, 'w') as f:
                f.write("# KIS API credentials\n")
                for entry in gitignore_entries:
                    f.write(f"{entry}\n")

            logger.info(f"✅ .gitignore created: {self.gitignore_path}")

    def _set_secure_permissions(self):
        """Set secure file permissions (600 - owner read/write only)"""
        try:
            os.chmod(self.env_path, 0o600)
            logger.info(f"✅ Secure permissions set (600): {self.env_path}")
        except Exception as e:
            logger.warning(f"⚠️  Failed to set secure permissions: {str(e)}")
            logger.warning(f"   Run manually: chmod 600 {self.env_path}")

    def backup_existing_env(self):
        """Backup existing .env file"""
        if self.env_path.exists():
            backup_path = self.env_path.with_suffix('.env.backup')
            counter = 1

            while backup_path.exists():
                backup_path = self.env_path.with_suffix(f'.env.backup.{counter}')
                counter += 1

            import shutil
            shutil.copy2(self.env_path, backup_path)

            logger.info(f"✅ Backup created: {backup_path}")
            return backup_path

        return None


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Setup KIS API credentials')
    parser.add_argument('--backup', action='store_true', help='Backup existing .env before setup')

    args = parser.parse_args()

    helper = CredentialSetupHelper()

    # Backup if requested
    if args.backup and helper.env_path.exists():
        helper.backup_existing_env()

    # Run interactive setup
    success = helper.run_interactive_setup()

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
