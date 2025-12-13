import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from config import FundingRateConfig

logger = logging.getLogger(__name__)


class FundingRateMonitor:
    """Monitor funding rates and detect changes at settlement times"""
    
    def __init__(self, config: FundingRateConfig = None):
        self.config = config or FundingRateConfig()
        
        # Track last seen settlement timestamp per symbol
        # This ensures we only alert once per settlement
        self.last_settlement_timestamps: Dict[str, int] = {}
        
        # Track previous settlement rates for comparison
        self.previous_settlement_rates: Dict[str, float] = {}
        
        # Track predicted rates we've already alerted on (to avoid spam)
        self.alerted_predicted_rates: Dict[str, float] = {}
        
        # Rate limiting
        self.alert_count_this_hour = 0
        self.hour_start = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        
        # Load previous state
        self._load_state()
    
    def _load_state(self):
        """Load previous state from file"""
        try:
            state_file = getattr(self.config, 'SETTLEMENT_HISTORY_FILE', self.config.STATE_FILE)
            if os.path.exists(state_file):
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    self.last_settlement_timestamps = state.get("timestamps", {})
                    self.previous_settlement_rates = state.get("rates", {})
                    logger.info(f"Loaded state for {len(self.last_settlement_timestamps)} symbols")
        except Exception as e:
            logger.warning(f"Could not load state file: {e}")
    
    def _save_state(self):
        """Save current state to file"""
        try:
            state_file = getattr(self.config, 'SETTLEMENT_HISTORY_FILE', self.config.STATE_FILE)
            os.makedirs(os.path.dirname(state_file), exist_ok=True)
            state = {
                "timestamps": self.last_settlement_timestamps,
                "rates": self.previous_settlement_rates,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Could not save state file: {e}")
    
    def _reset_hourly_count_if_needed(self):
        """Reset alert count if we're in a new hour"""
        current_hour = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        if current_hour > self.hour_start:
            self.alert_count_this_hour = 0
            self.hour_start = current_hour
    
    def _can_send_alert(self) -> bool:
        """Check if we can send another alert (rate limiting)"""
        self._reset_hourly_count_if_needed()
        return self.alert_count_this_hour < self.config.MAX_ALERTS_PER_HOUR
    
    def _format_settlement_time(self, timestamp_ms: int) -> str:
        """Format settlement time as human-readable string"""
        if not timestamp_ms:
            return "Unknown"
        try:
            dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            return dt.strftime('%Y-%m-%d %H:%M UTC')
        except Exception:
            return "Unknown"
    
    def _format_settlement_time_ist(self, timestamp_ms: int) -> str:
        """Format settlement time in IST (UTC+5:30)"""
        if not timestamp_ms:
            return "Unknown"
        try:
            from datetime import timedelta
            dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
            # Convert to IST (UTC+5:30)
            ist_offset = timedelta(hours=5, minutes=30)
            dt_ist = dt + ist_offset
            return dt_ist.strftime('%d %b %Y, %I:%M %p IST')
        except Exception:
            return "Unknown"
    
    def check_settlements(self, settlements: Dict[str, Dict], ticker_data: Dict[str, Dict]) -> List[Dict]:
        """
        Check for new funding settlements and generate alerts
        
        Args:
            settlements: Dict mapping symbol to latest settlement data
                        Each has: symbol, fundingRate, fundingRateTimestamp
            ticker_data: Dict mapping symbol to current ticker data (for price, etc.)
        
        Returns:
            List of alert dictionaries for new settlements
        """
        alerts = []
        new_settlements = 0
        
        for symbol, settlement in settlements.items():
            current_timestamp = settlement.get("fundingRateTimestamp", 0)
            current_rate = settlement.get("fundingRate", 0)
            
            # Get previous data
            prev_timestamp = self.last_settlement_timestamps.get(symbol, 0)
            prev_rate = self.previous_settlement_rates.get(symbol)
            
            # Check if this is a NEW settlement (timestamp changed)
            if current_timestamp > prev_timestamp:
                new_settlements += 1
                
                # Generate alert if we have previous data to compare
                if prev_rate is not None:
                    alert = self._create_settlement_alert(
                        symbol, 
                        current_rate, 
                        prev_rate, 
                        current_timestamp,
                        ticker_data.get(symbol, {})
                    )
                    
                    if alert and self._can_send_alert():
                        alerts.append(alert)
                        self.alert_count_this_hour += 1
                else:
                    logger.debug(f"{symbol}: First settlement observation, rate = {current_rate:.6f}")
                
                # Update tracking
                self.last_settlement_timestamps[symbol] = current_timestamp
                self.previous_settlement_rates[symbol] = current_rate
        
        # Save state after checking
        if new_settlements > 0:
            self._save_state()
            logger.info(f"Detected {new_settlements} new settlements, generated {len(alerts)} alerts")
        
        return alerts
    
    def _create_settlement_alert(
        self,
        symbol: str,
        current_rate: float,
        prev_rate: float,
        settlement_timestamp: int,
        ticker_data: Dict
    ) -> Optional[Dict]:
        """
        Create an alert for a funding settlement
        
        Alert Rules:
        - BTCUSDT (and symbols in FULL_ALERT_SYMBOLS): Only SIGN CHANGE (flip) alerts
        - Other symbols: No settlement alerts (only predicted alerts)
        
        Returns:
            Alert dict if alert should be sent, None otherwise
        """
        # Check if this symbol gets flip alerts
        full_alert_symbols = getattr(self.config, 'FULL_ALERT_SYMBOLS', ['BTCUSDT'])
        is_full_alert_symbol = symbol in full_alert_symbols
        
        # Only BTCUSDT gets settlement alerts, and only for sign changes
        if not is_full_alert_symbol:
            return None
        
        # Determine alert type - only sign change for BTCUSDT
        alert_type = None
        
        # Check for sign change (flip)
        if self.config.ALERT_ON_SIGN_CHANGE:
            if prev_rate > 0 and current_rate < 0:
                alert_type = "sign_change"
                logger.info(f"{symbol}: Rate flipped from positive to negative at settlement")
            elif prev_rate < 0 and current_rate > 0:
                alert_type = "sign_change"
                logger.info(f"{symbol}: Rate flipped from negative to positive at settlement")
        
        if alert_type is None:
            return None
        
        # Calculate rate change
        rate_change = current_rate - prev_rate
        
        # Get funding interval from ticker if available
        funding_interval = ticker_data.get("fundingIntervalHours", 8)
        prev_interval = ticker_data.get("prevFundingIntervalHours", funding_interval)
        
        return {
            "symbol": symbol,
            "fundingRate": current_rate,
            "prevFundingRate": prev_rate,
            "rateChange": rate_change,
            "alertType": alert_type,
            "lastPrice": ticker_data.get("lastPrice", 0),
            "settlementTime": self._format_settlement_time_ist(settlement_timestamp),
            "fundingInterval": f"{funding_interval}h",
            "prevFundingInterval": f"{prev_interval}h",
            "volume24h": ticker_data.get("volume24h", 0),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_current_summary(self, rates: Dict[str, Dict]) -> Dict:
        """Get a summary of current funding rates"""
        if not rates:
            return {}
        
        # Find extremes
        most_positive = max(rates.items(), key=lambda x: x[1].get("fundingRate", 0))
        most_negative = min(rates.items(), key=lambda x: x[1].get("fundingRate", 0))
        
        positive_count = sum(1 for d in rates.values() if d.get("fundingRate", 0) > 0)
        negative_count = sum(1 for d in rates.values() if d.get("fundingRate", 0) < 0)
        
        return {
            "total_symbols": len(rates),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "most_positive": {
                "symbol": most_positive[0],
                "rate": most_positive[1].get("fundingRate", 0)
            },
            "most_negative": {
                "symbol": most_negative[0],
                "rate": most_negative[1].get("fundingRate", 0)
            }
        }

    def check_predicted_rates(self, ticker_data: Dict[str, Dict]) -> List[Dict]:
        """
        Check current (predicted) funding rates and generate alerts for extreme values

        These are the rates that WILL settle at the next funding time.
        Only alerts for extreme rates to avoid spam.

        Args:
            ticker_data: Dict mapping symbol to current ticker data with fundingRate

        Returns:
            List of alert dictionaries for extreme predicted rates
        """
        if not getattr(self.config, 'ALERT_ON_PREDICTED_RATES', False):
            return []

        threshold = getattr(self.config, 'PREDICTED_RATE_THRESHOLD', 0.001)
        alerts = []

        for symbol, data in ticker_data.items():
            current_rate = float(data.get("fundingRate", 0))

            # Handle non-extreme rates: clear from tracking and skip
            if not self._is_rate_extreme(current_rate, threshold):
                self._clear_alerted_rate(symbol)
                continue

            # Skip if we shouldn't re-alert for this rate yet
            if not self._should_alert_for_rate(symbol, current_rate):
                continue

            # Skip if we've hit rate limit
            if not self._can_send_alert():
                continue

            # Create and track alert
            alert = self._create_predicted_alert(symbol, current_rate, data)
            if alert:
                self._record_alert(symbol, current_rate, alerts, alert)

        if alerts:
            logger.info(f"Generated {len(alerts)} predicted rate alerts")

        return alerts

    def _is_rate_extreme(self, rate: float, threshold: float) -> bool:
        """Check if a funding rate exceeds the extreme threshold"""
        return abs(rate) >= threshold

    def _clear_alerted_rate(self, symbol: str):
        """Remove symbol from alerted rates tracking"""
        if symbol in self.alerted_predicted_rates:
            del self.alerted_predicted_rates[symbol]

    def _should_alert_for_rate(self, symbol: str, current_rate: float) -> bool:
        """
        Determine if we should alert for this rate

        We alert if:
        - This is the first time seeing an extreme rate for this symbol, OR
        - The rate changed significantly (50%+) from when we last alerted, OR
        - The rate flipped sign (positive to negative or vice versa)
        """
        prev_alerted = self.alerted_predicted_rates.get(symbol)

        # First time seeing extreme rate for this symbol
        if prev_alerted is None:
            return True

        # Check if rate flipped sign
        if self._rate_flipped_sign(current_rate, prev_alerted):
            return True

        # Check if rate changed significantly
        return self._rate_changed_significantly(current_rate, prev_alerted)

    def _rate_flipped_sign(self, current_rate: float, prev_rate: float) -> bool:
        """Check if rate changed from positive to negative or vice versa"""
        return (current_rate > 0) != (prev_rate > 0)

    def _rate_changed_significantly(self, current_rate: float, prev_rate: float, threshold: float = 0.5) -> bool:
        """Check if rate changed by more than threshold (default 50%)"""
        if prev_rate == 0:
            return True

        rate_change = abs(current_rate - prev_rate) / abs(prev_rate)
        return rate_change >= threshold

    def _record_alert(self, symbol: str, rate: float, alerts: List[Dict], alert: Dict):
        """Record that we've alerted for this symbol and rate"""
        alerts.append(alert)
        self.alert_count_this_hour += 1
        self.alerted_predicted_rates[symbol] = rate
        logger.info(f"{symbol}: Extreme PREDICTED funding rate: {rate:.6f}")
    
    def _create_predicted_alert(self, symbol: str, rate: float, ticker_data: Dict) -> Dict:
        """Create an alert for a predicted (upcoming) funding rate"""
        from datetime import timedelta
        
        # Calculate next funding time
        next_funding_time = int(ticker_data.get("nextFundingTime", 0))
        
        funding_interval = ticker_data.get("fundingIntervalHours", 8)
        
        return {
            "symbol": symbol,
            "fundingRate": rate,
            "prevFundingRate": None,  # No previous for predicted
            "rateChange": None,
            "alertType": "predicted",
            "lastPrice": ticker_data.get("lastPrice", 0),
            "settlementTime": self._format_settlement_time_ist(next_funding_time),
            "fundingInterval": f"{funding_interval}h",
            "prevFundingInterval": None,
            "volume24h": ticker_data.get("volume24h", 0),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def clear_predicted_alerts_after_settlement(self, symbol: str):
        """Clear predicted alert tracking after a settlement occurs"""
        if symbol in self.alerted_predicted_rates:
            del self.alerted_predicted_rates[symbol]
