"""
Real-Time Data Streaming Extension (Phase 2.1)

Skeleton implementation for WebSocket-based real-time market data streaming.

Author: Spock Quant Platform
Date: 2025-10-29
Version: 1.0.0
Status: Skeleton Only (Not Implemented)
"""

from abc import ABC, abstractmethod
from typing import Callable, Optional, List, Dict, Any
import pandas as pd
from loguru import logger


class DataStreamManager(ABC):
    """
    Real-time data streaming interface.

    Skeleton implementation - override methods for actual streaming.

    Future Implementation:
        - WebSocket connection to KIS API
        - Reconnection logic with exponential backoff
        - Buffer management for missed data
        - Topic-based pub/sub pattern
    """

    def __init__(self, config: dict):
        """
        Initialize streaming manager.

        Args:
            config: Streaming configuration
                - enabled (bool): Whether streaming is enabled
                - websocket_url (str): WebSocket server URL
                - reconnect_interval (int): Seconds between reconnection attempts
                - buffer_size (int): Max buffer size for missed data
        """
        self.config = config
        self.enabled = config.get('enabled', False)
        self.websocket_url = config.get('websocket_url', '')
        self.reconnect_interval = config.get('reconnect_interval', 5)
        self.buffer_size = config.get('buffer_size', 1000)

        # Runtime state
        self.callbacks: List[Callable] = []
        self.subscriptions: Dict[str, List[Callable]] = {}
        self.ws_connection = None

        if self.enabled:
            logger.warning(
                "⚠️ DataStreamManager is enabled but not implemented. "
                "This is a skeleton - streaming will not work."
            )

    @abstractmethod
    def connect(self, ticker: str, region: str) -> bool:
        """
        Connect to real-time data stream.

        Args:
            ticker: Stock ticker symbol
            region: Market region code

        Returns:
            True if connection successful

        Raises:
            NotImplementedError: Skeleton method not implemented

        Future Implementation:
            ```python
            import websocket

            self.ws = websocket.WebSocketApp(
                f"{self.websocket_url}/{ticker}",
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close
            )
            self.ws.run_forever()
            return True
            ```
        """
        if not self.enabled:
            logger.debug(f"Streaming disabled, skipping connect for {ticker}")
            return False

        raise NotImplementedError(
            "DataStreamManager.connect() is a skeleton method. "
            "See docs/AUTO_BACKFILL_SKELETON_DESIGN.md for implementation guide."
        )

    @abstractmethod
    def subscribe(self, ticker: str, callback: Callable) -> None:
        """
        Subscribe to real-time updates.

        Args:
            ticker: Stock ticker to subscribe
            callback: Function to call on new data (signature: callback(data: dict))

        Raises:
            NotImplementedError: Skeleton method not implemented

        Future Implementation:
            ```python
            if ticker not in self.subscriptions:
                self.subscriptions[ticker] = []
            self.subscriptions[ticker].append(callback)

            # Send subscription message to WebSocket
            self.ws.send(json.dumps({
                'type': 'subscribe',
                'ticker': ticker,
                'region': region
            }))
            ```
        """
        if not self.enabled:
            logger.debug(f"Streaming disabled, skipping subscribe for {ticker}")
            return

        raise NotImplementedError(
            "DataStreamManager.subscribe() is a skeleton method. "
            "See docs/AUTO_BACKFILL_SKELETON_DESIGN.md for implementation guide."
        )

    @abstractmethod
    def disconnect(self, ticker: str) -> None:
        """
        Disconnect from data stream.

        Args:
            ticker: Stock ticker to disconnect

        Raises:
            NotImplementedError: Skeleton method not implemented

        Future Implementation:
            ```python
            # Send unsubscribe message
            self.ws.send(json.dumps({
                'type': 'unsubscribe',
                'ticker': ticker
            }))

            # Remove callbacks
            if ticker in self.subscriptions:
                del self.subscriptions[ticker]

            # Close WebSocket if no more subscriptions
            if not self.subscriptions:
                self.ws.close()
            ```
        """
        if not self.enabled:
            logger.debug(f"Streaming disabled, skipping disconnect for {ticker}")
            return

        raise NotImplementedError(
            "DataStreamManager.disconnect() is a skeleton method. "
            "See docs/AUTO_BACKFILL_SKELETON_DESIGN.md for implementation guide."
        )

    def is_enabled(self) -> bool:
        """
        Check if streaming is enabled.

        Returns:
            True if streaming is enabled in configuration
        """
        return self.enabled

    def _on_message(self, ws, message: str) -> None:
        """
        Handle incoming WebSocket messages (future implementation).

        Args:
            ws: WebSocket connection
            message: JSON message from server
        """
        # Future implementation
        pass

    def _on_error(self, ws, error: Exception) -> None:
        """
        Handle WebSocket errors (future implementation).

        Args:
            ws: WebSocket connection
            error: Error exception
        """
        # Future implementation
        pass

    def _on_close(self, ws, close_status_code: int, close_msg: str) -> None:
        """
        Handle WebSocket connection close (future implementation).

        Args:
            ws: WebSocket connection
            close_status_code: Status code
            close_msg: Close message
        """
        # Future implementation
        pass

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"DataStreamManager(enabled={self.enabled}, "
            f"subscriptions={len(self.subscriptions)}, "
            f"status='skeleton')"
        )
