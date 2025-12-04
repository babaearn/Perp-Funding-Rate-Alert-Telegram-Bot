from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class FundingRateConfig:
    """Configuration for Perpetual Funding Rate Alert Bot"""
    
    # Symbols to monitor (USDT Perpetuals)
    # Set to None or empty list to monitor ALL perpetuals automatically
    SYMBOLS: Optional[List[str]] = None
    
    # If True, fetch all available perpetuals from API
    # If False, use the SYMBOLS list above
    MONITOR_ALL_SYMBOLS: bool = True
    
    def __post_init__(self):
        # Default symbols only used if MONITOR_ALL_SYMBOLS is False
        if not self.MONITOR_ALL_SYMBOLS and self.SYMBOLS is None:
            self.SYMBOLS = [
                "BTCUSDT",
                "ETHUSDT",
                "SOLUSDT",
            ]
    
    # API settings (currently using Bybit)
    BYBIT_BASE_URL = "https://api.bybit.com"
    BYBIT_TICKERS_ENDPOINT = "/v5/market/tickers"
    BYBIT_FUNDING_HISTORY_ENDPOINT = "/v5/market/funding/history"
    
    # ==========================================================================
    # FUNDING INTERVAL AWARENESS
    # ==========================================================================
    # Bybit has 4 different funding intervals:
    #   - 1 hour:  65 symbols  (24 settlements/day)
    #   - 2 hours: 16 symbols  (12 settlements/day)
    #   - 4 hours: 290 symbols (6 settlements/day)
    #   - 8 hours: 179 symbols (3 settlements/day)
    #
    # We check every 30 minutes to catch ALL 1-hour funding settlements
    # ==========================================================================
    
    # Check interval in seconds (30 minutes to catch 1-hour funding)
    CHECK_INTERVAL = 1800  # 30 minutes
    
    # ==========================================================================
    # ALERT MODE: SETTLEMENT-BASED (No spam, covers everything)
    # ==========================================================================
    # Only alert when funding ACTUALLY settles (historical rate appears)
    # This ensures we cover ALL changes without spam from predicted rate fluctuations
    ALERT_ON_SETTLEMENT_ONLY = True
    
    # ==========================================================================
    # ALERT THRESHOLDS
    # ==========================================================================
    # Only alert when rate CHANGES between settlements
    # Set to a small value to catch any meaningful change
    # 0.0001 = 0.01% change (1 basis point) - catches real changes, ignores noise
    MIN_RATE_CHANGE_THRESHOLD = 0.0001
    
    # Alert on extreme funding rates (above this absolute value)
    # 0.001 = 0.1% funding rate (considered high)
    EXTREME_RATE_THRESHOLD = 0.001
    
    # Alert on funding rate sign change (positive to negative or vice versa)
    ALERT_ON_SIGN_CHANGE = True
    
    # ==========================================================================
    # ALERT RULES
    # ==========================================================================
    # BTCUSDT gets ALL alerts (any change, flip, extreme)
    # Other symbols only get alerts for EXTREME rates (>0.1%)
    FULL_ALERT_SYMBOLS: List[str] = field(default_factory=lambda: ["BTCUSDT"])
    
    # ==========================================================================
    # PREDICTED RATE ALERTS
    # ==========================================================================
    # Also alert on predicted (current) funding rates before settlement
    # These are the rates that WILL settle at next funding time
    ALERT_ON_PREDICTED_RATES = True
    
    # Only send predicted alerts for extreme rates (prevent spam)
    PREDICTED_RATE_THRESHOLD = 0.001  # 0.1% - same as extreme threshold
    
    # ==========================================================================
    # DATA STORAGE
    # ==========================================================================
    DATA_DIR = "data"
    STATE_FILE = "data/funding_state.json"
    SETTLEMENT_HISTORY_FILE = "data/settlement_history.json"
    LOG_FILE = "logs/funding_alerts.log"
    
    # ==========================================================================
    # RATE LIMITING
    # ==========================================================================
    # With settlement-based alerts, we expect:
    # - 1h symbols: ~65 per hour (worst case)
    # - 2h symbols: ~8 per hour
    # - 4h symbols: ~48 per hour (at settlement times)
    # - 8h symbols: ~22 per hour (at settlement times)
    # Total: ~50-150 alerts per hour at peak settlement times
    MAX_ALERTS_PER_HOUR = 200  # Allow all settlement alerts


# Create default config instance
config = FundingRateConfig()
