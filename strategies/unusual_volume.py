#!/usr/bin/env python3
"""
异常成交量检测策略
检测冷门项目的突然放量
"""

import asyncio
from typing import List, Dict, Optional
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from core import ProfitStrategy, TradeSignal, Market, logger


@dataclass
class VolumeSpike:
    market_id: str
    token_id: str
    direction: str
    current_volume_1h: float
    avg_volume_24h: float
    spike_ratio: float
    price_change: float
    buy_ratio: float
    timestamp: datetime


class UnusualVolumeStrategy(ProfitStrategy):
    """异常成交量策略"""
    
    def __init__(self, config: Dict):
        super().__init__("UnusualVolume", config)
        self.max_daily_volume = config.get('max_daily_volume', 50000)
        self.min_spike_ratio = config.get('min_spike_ratio', 3.0)
        self.min_buy_ratio = config.get('min_buy_ratio', 0.70)
        self.max_price_change = config.get('max_price_change', 0.05)
    
    async def analyze(self, markets: List[Market]) -> List[TradeSignal]:
        signals = []
        
        # 筛选冷门市场
        cold_markets = [m for m in markets 
                       if m.volume_24h < self.max_daily_volume 
                       and m.liquidity > 5000
                       and 0.05 < m.mid_price < 0.95]
        
        for market in cold_markets:
            spike = await self._detect_spike(market)
            if spike and spike.spike_ratio >= self.min_spike_ratio:
                signal = TradeSignal(
                    strategy_name=self.name,
                    market=market,
                    action="UNUSUAL_VOLUME",
                    side=spike.direction,
                    size=100,
                    price=market.best_ask if spike.direction == "YES" else market.best_bid,
                    expected_profit=0.05,
                    confidence=min(spike.spike_ratio / 10, 0.9),
                    metadata={
                        'spike_ratio': spike.spike_ratio,
                        'buy_ratio': spike.buy_ratio,
                        'volume_1h': spike.current_volume_1h
                    }
                )
                signals.append(signal)
                logger.info(f"🚨 异常成交量: {market.question[:40]} "
                          f"突增{spike.spike_ratio:.1f}倍 "
                          f"方向{spike.direction}")
        
        return signals
    
    async def _detect_spike(self, market: Market) -> Optional[VolumeSpike]:
        """检测成交量突增"""
        # 模拟数据获取
        current_volume = market.volume_24h / 24 * (1 + self.min_spike_ratio)
        avg_volume = market.volume_24h / 24
        
        if avg_volume == 0:
            return None
        
        spike_ratio = current_volume / avg_volume
        
        if spike_ratio < self.min_spike_ratio:
            return None
        
        # 判断方向
        buy_ratio = 0.75  # 模拟
        if buy_ratio > self.min_buy_ratio:
            direction = "YES"
        elif buy_ratio < (1 - self.min_buy_ratio):
            direction = "NO"
        else:
            return None
        
        return VolumeSpike(
            market_id=market.condition_id,
            token_id=market.token_id,
            direction=direction,
            current_volume_1h=current_volume,
            avg_volume_24h=avg_volume,
            spike_ratio=spike_ratio,
            price_change=0.02,
            buy_ratio=buy_ratio,
            timestamp=datetime.now()
        )
    
    async def execute(self, signal: TradeSignal) -> bool:
        logger.info(f"执行异常成交量交易: {signal.market.question[:40]}")
        return True
