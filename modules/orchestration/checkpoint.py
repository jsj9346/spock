"""
Checkpoint Manager for Database Update Pipeline

Provides checkpoint save/restore functionality for fault-tolerant pipeline execution.
Allows resuming from the last successful step after interruption or failure.

Author: Quant Investment Platform
Date: 2025-11-01
"""

import json
import glob
import os
from datetime import datetime
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class CheckpointManager:
    """
    Checkpoint manager for saving and restoring pipeline execution state

    Features:
    - Save checkpoint after each step completion
    - Load latest checkpoint for resume
    - Identify next step to execute
    - Cleanup old checkpoints

    Usage:
        manager = CheckpointManager()
        manager.save('fundamentals', {'success': True, ...})
        checkpoint = manager.load_latest()
        if checkpoint:
            next_step = checkpoint['next_step']
    """

    # Step execution order
    STEP_ORDER = [
        'tickers',
        'ticker_refresh',    # New: Multi-region ticker refresh with OTC filtering
        'fx_tracking',       # New: Exchange rate tracking and FX signals
        'ohlcv',
        'fundamentals',
        'classification',    # New: Stock classification (SPAC, preferred, sector/industry)
        'dividend',
        'etf_data',          # New: ETF details and holdings
        'quarterly'
    ]

    def __init__(self, checkpoint_dir: str = "logs"):
        """
        Initialize checkpoint manager

        Args:
            checkpoint_dir: Directory to store checkpoint files
        """
        self.checkpoint_dir = checkpoint_dir
        os.makedirs(checkpoint_dir, exist_ok=True)

        logger.info(f"CheckpointManager initialized (dir: {checkpoint_dir})")

    def save(self, step: str, result: Dict, metadata: Optional[Dict] = None) -> str:
        """
        Save checkpoint after step completion

        Args:
            step: Step name ('tickers', 'ohlcv', etc.)
            result: Step execution result dictionary
            metadata: Optional metadata (regions, flags, etc.)

        Returns:
            Path to saved checkpoint file
        """
        checkpoint = {
            "timestamp": datetime.now().isoformat(),
            "step": step,
            "result": result,
            "next_step": self._get_next_step(step),
            "metadata": metadata or {}
        }

        # Generate unique filename
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.checkpoint_dir}/checkpoint_{timestamp_str}.json"

        # Save to file
        with open(filename, 'w') as f:
            json.dump(checkpoint, f, indent=2, default=str)

        logger.info(f"✅ Checkpoint saved: {filename} (step: {step})")
        return filename

    def load_latest(self) -> Optional[Dict]:
        """
        Load latest checkpoint

        Returns:
            Checkpoint dictionary or None if no checkpoints found
        """
        checkpoint_files = glob.glob(f"{self.checkpoint_dir}/checkpoint_*.json")

        if not checkpoint_files:
            logger.info("No checkpoints found")
            return None

        # Get latest checkpoint by modification time
        latest_file = max(checkpoint_files, key=os.path.getmtime)

        with open(latest_file, 'r') as f:
            checkpoint = json.load(f)

        logger.info(
            f"📂 Loaded checkpoint: {latest_file} "
            f"(step: {checkpoint['step']}, next: {checkpoint.get('next_step')})"
        )

        return checkpoint

    def resume_from_checkpoint(self) -> Optional[str]:
        """
        Get next step to resume from latest checkpoint

        Returns:
            Next step name or None if no checkpoint or pipeline complete
        """
        checkpoint = self.load_latest()

        if not checkpoint:
            return None

        next_step = checkpoint.get('next_step')

        if not next_step:
            logger.info("Pipeline already complete (no next step)")
            return None

        logger.info(f"🔄 Resuming from step: {next_step}")
        return next_step

    def get_completed_steps(self) -> List[str]:
        """
        Get list of completed steps from latest checkpoint

        Returns:
            List of completed step names
        """
        checkpoint = self.load_latest()

        if not checkpoint:
            return []

        completed = []
        current_step = checkpoint['step']

        for step in self.STEP_ORDER:
            completed.append(step)
            if step == current_step:
                break

        return completed

    def clear_checkpoints(self, keep_latest: bool = True) -> int:
        """
        Clear old checkpoint files

        Args:
            keep_latest: If True, keep the most recent checkpoint

        Returns:
            Number of files deleted
        """
        checkpoint_files = glob.glob(f"{self.checkpoint_dir}/checkpoint_*.json")

        if not checkpoint_files:
            return 0

        if keep_latest and len(checkpoint_files) > 1:
            # Keep latest, delete others
            latest_file = max(checkpoint_files, key=os.path.getmtime)
            checkpoint_files.remove(latest_file)

        # Delete files
        deleted_count = 0
        for filepath in checkpoint_files:
            os.remove(filepath)
            deleted_count += 1

        logger.info(f"🗑️ Cleared {deleted_count} checkpoint files")
        return deleted_count

    def _get_next_step(self, current_step: str) -> Optional[str]:
        """
        Get next step in pipeline sequence

        Args:
            current_step: Current step name

        Returns:
            Next step name or None if current step is last
        """
        if current_step not in self.STEP_ORDER:
            logger.warning(f"Unknown step: {current_step}")
            return None

        current_index = self.STEP_ORDER.index(current_step)

        # Check if current step is last
        if current_index == len(self.STEP_ORDER) - 1:
            return None  # Pipeline complete

        return self.STEP_ORDER[current_index + 1]

    def _is_valid_step(self, step: str) -> bool:
        """Check if step name is valid"""
        return step in self.STEP_ORDER
