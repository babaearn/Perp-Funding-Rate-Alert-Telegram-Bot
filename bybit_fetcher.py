import logging
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone, timedelta
import time

logger = logging.getLogger(__name__)


class BybitDataFetcher:
    """Fetch funding rate data from Bybit API"""
    
    def __init__(self, base_url: str = "https://api.bybit.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json"
        })
        self._all_symbols_cache = None
        self._cache_timestamp = None
    
    def get_all_perpetual_symbols_with_intervals(self) -> Dict[str, Dict]:
        """
        Get all available USDT perpetual symbols with their funding intervals
        
        Returns:
            Dict mapping symbol to info including funding interval
        """
        try:
            url = f"{self.base_url}/v5/market/tickers"
            params = {"category": "linear"}
            
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get("retCode") != 0:
                logger.error(f"Bybit API error: {data.get('retMsg')}")
                return {}
            
            result = {}
            for ticker in data.get("result", {}).get("list", []):
                symbol = ticker.get("symbol", "")
                if not symbol.endswith("USDT"):
                    continue
                
                interval_hours = int(ticker.get("fundingIntervalHour", 8))
                
                result[symbol] = {
                    "symbol": symbol,
                    "fundingIntervalHours": interval_hours,
                    "nextFundingTime": int(ticker.get("nextFundingTime", 0)),
                    "currentRate": float(ticker.get("fundingRate", 0)),
                }
            
            logger.info(f"Found {len(result)} USDT perpetual symbols on Bybit")
            return result
            
        except Exception as e:
            logger.error(f"Error fetching perpetual symbols: {e}")
            return {}
    
    def get_all_perpetual_symbols(self) -> List[str]:
        """
        Get all available USDT perpetual symbols from Bybit
        
        Returns:
            List of all perpetual symbol names
        """
        try:
            url = f"{self.base_url}/v5/market/tickers"
            params = {"category": "linear"}
            
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            if data.get("retCode") != 0:
                logger.error(f"Bybit API error: {data.get('retMsg')}")
                return []
            
            symbols = []
            for ticker in data.get("result", {}).get("list", []):
                symbol = ticker.get("symbol", "")
                # Only include USDT perpetuals (exclude futures with expiry dates)
                if symbol.endswith("USDT") and not any(char.isdigit() for char in symbol.replace("USDT", "").replace("1000", "").replace("10000", "")):
                    symbols.append(symbol)
            
            logger.info(f"Found {len(symbols)} USDT perpetual symbols on Bybit")
            return sorted(symbols)
            
        except Exception as e:
            logger.error(f"Error fetching perpetual symbols: {e}")
            return []
    
    def get_tickers(self, symbols: List[str] = None) -> Dict[str, Dict]:
        """
        Get current ticker data including funding rates for all linear perpetuals
        
        Args:
            symbols: Optional list of specific symbols to filter
        
        Returns:
            Dict mapping symbol to ticker data including funding rate
        """
        try:
            url = f"{self.base_url}/v5/market/tickers"
            params = {"category": "linear"}
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("retCode") != 0:
                logger.error(f"Bybit API error: {data.get('retMsg')}")
                return {}
            
            result = {}
            ticker_list = data.get("result", {}).get("list", [])
            
            for ticker in ticker_list:
                symbol = ticker.get("symbol", "")
                
                # Filter by symbols if specified
                if symbols and symbol not in symbols:
                    continue
                
                # Only include perpetuals (not futures with expiry)
                if not symbol.endswith("USDT"):
                    continue
                
                funding_rate = ticker.get("fundingRate", "0")
                next_funding_time = ticker.get("nextFundingTime", "0")
                
                result[symbol] = {
                    "symbol": symbol,
                    "lastPrice": float(ticker.get("lastPrice", 0)),
                    "fundingRate": float(funding_rate) if funding_rate else 0,
                    "nextFundingTime": int(next_funding_time) if next_funding_time else 0,
                    "price24hPcnt": float(ticker.get("price24hPcnt", 0)),
                    "volume24h": float(ticker.get("volume24h", 0)),
                    "openInterest": float(ticker.get("openInterest", 0)),
                    "timestamp": datetime.utcnow().isoformat()
                }
            
            logger.debug(f"Fetched {len(result)} tickers from Bybit")
            return result
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Bybit tickers: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error fetching tickers: {e}")
            return {}
    
    def get_funding_rate_history(self, symbol: str, limit: int = 10) -> List[Dict]:
        """
        Get historical funding rates for a symbol
        
        Args:
            symbol: Symbol name (e.g., "BTCUSDT")
            limit: Number of records to fetch (1-200)
        
        Returns:
            List of funding rate records
        """
        try:
            url = f"{self.base_url}/v5/market/funding/history"
            params = {
                "category": "linear",
                "symbol": symbol,
                "limit": min(limit, 200)
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("retCode") != 0:
                logger.error(f"Bybit API error for {symbol}: {data.get('retMsg')}")
                return []
            
            records = []
            for item in data.get("result", {}).get("list", []):
                records.append({
                    "symbol": item.get("symbol"),
                    "fundingRate": float(item.get("fundingRate", 0)),
                    "fundingRateTimestamp": int(item.get("fundingRateTimestamp", 0))
                })
            
            return records
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching funding history for {symbol}: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error fetching funding history: {e}")
            return []
    
    def get_funding_rate_history_by_date(self, symbol: str, date_str: str) -> Tuple[List[Dict], str]:
        """
        Get historical funding rates for a symbol on a specific date
        
        Args:
            symbol: Symbol name (e.g., "BTCUSDT")
            date_str: Date in DDMMYY format (e.g., "010126" for 01 Jan 2026)
        
        Returns:
            Tuple of (List of funding rate records for that date, error message if any)
        """
        try:
            # Parse DDMMYY format
            day = int(date_str[0:2])
            month = int(date_str[2:4])
            year = int(date_str[4:6]) + 2000  # Convert YY to YYYY
            
            # Create start and end timestamps for the date (UTC)
            start_dt = datetime(year, month, day, 0, 0, 0, tzinfo=timezone.utc)
            end_dt = start_dt + timedelta(days=1) - timedelta(milliseconds=1)
            
            start_time = int(start_dt.timestamp() * 1000)
            end_time = int(end_dt.timestamp() * 1000)
            
            url = f"{self.base_url}/v5/market/funding/history"
            params = {
                "category": "linear",
                "symbol": symbol,
                "startTime": start_time,
                "endTime": end_time,
                "limit": 200
            }
            
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get("retCode") != 0:
                error_msg = data.get('retMsg', 'Unknown error')
                logger.error(f"Bybit API error for {symbol}: {error_msg}")
                return [], error_msg
            
            records = []
            for item in data.get("result", {}).get("list", []):
                records.append({
                    "symbol": item.get("symbol"),
                    "fundingRate": float(item.get("fundingRate", 0)),
                    "fundingRateTimestamp": int(item.get("fundingRateTimestamp", 0))
                })
            
            # Sort by timestamp ascending (oldest first)
            records.sort(key=lambda x: x["fundingRateTimestamp"])
            
            return records, ""
            
        except ValueError as e:
            logger.error(f"Invalid date format: {date_str}")
            return [], "Invalid date format. Use DDMMYY (e.g., 010126)"
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching funding history for {symbol}: {e}")
            return [], str(e)
        except Exception as e:
            logger.error(f"Unexpected error fetching funding history: {e}")
            return [], str(e)
    
    def get_current_funding_rates(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current funding rates for specific symbols
        
        Args:
            symbols: List of symbol names
        
        Returns:
            Dict mapping symbol to current funding rate
        """
        tickers = self.get_tickers(symbols)
        return {
            symbol: data["fundingRate"]
            for symbol, data in tickers.items()
        }
    
    def get_latest_settlement(self, symbol: str) -> Optional[Dict]:
        """
        Get the most recent funding settlement for a symbol
        
        Args:
            symbol: Symbol name
        
        Returns:
            Dict with settlement info or None
        """
        history = self.get_funding_rate_history(symbol, limit=1)
        if history:
            return history[0]
        return None
    
    def get_latest_settlements_batch(self, symbols: List[str], batch_size: int = 50) -> Dict[str, Dict]:
        """
        Get latest settlements for multiple symbols with rate limiting
        
        Args:
            symbols: List of symbol names
            batch_size: Number of API calls before a small delay
        
        Returns:
            Dict mapping symbol to latest settlement info
        """
        results = {}
        
        for i, symbol in enumerate(symbols):
            settlement = self.get_latest_settlement(symbol)
            if settlement:
                results[symbol] = settlement
            
            # Rate limiting: pause briefly every batch_size requests
            if (i + 1) % batch_size == 0:
                time.sleep(0.5)
        
        return results
