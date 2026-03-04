#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Polymarket 盈利策略系统 - 核心模块
基于深度文档研究的多策略交易系统
"""

import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
from decimal import Decimal
import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/profit_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class Market:
    """市场数据结构"""
    token_id: str
    condition_id: str
    question: str
    slug: str
    
    # 价格信息
    best_bid: float = 0.0
    best_ask: float = 0.0
    last_price: float = 0.0
    
    # 市场属性
    volume_24h: float = 0.0
    liquidity: float = 0.0
    spread: float = 0.0
    
    # 特殊属性
    neg_risk: bool = False
    fee_rate: float = 0.0
    tick_size: float = 0.01
    
    # 时间信息
    expiration: Optional[datetime] = None
    
    @property
    def mid_price(self) -> float:
        """中点价"""
        if self.best_bid > 0 and self.best_ask > 0:
            return (self.best_bid + self.best_ask) / 2
        return self.last_price


@dataclass
class TradeSignal:
    """交易信号"""
    strategy_name: str
    market: Market
    action: str  # BUY, SELL, ARBITRAGE, HEDGE
    side: str    # YES, NO
    size: float
    price: float
    expected_profit: float
    confidence: float
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class ProfitStrategy(ABC):
    """盈利策略基类"""
    
    def __init__(self, name: str, config: Dict):
        self.name = name
        self.config = config
        self.enabled = config.get('enabled', True)
        self.min_confidence = config.get('min_confidence', 0.6)
        self.logger = logging.getLogger(f"Strategy.{name}")
    
    @abstractmethod
    async def analyze(self, markets: List[Market]) -> List[TradeSignal]:
        """分析市场，生成交易信号"""
        pass
    
    @abstractmethod
    async def execute(self, signal: TradeSignal) -> bool:
        """执行交易信号"""
        pass
    
    def is_enabled(self) -> bool:
        return self.enabled


class PolymarketAPI:
    """Polymarket API 封装"""
    
    def __init__(self):
        self.gamma_api = "https://gamma-api.polymarket.com"
        self.data_api = "https://data-api.polymarket.com"
        self.clob_api = "https://clob.polymarket.com"
        self.session = requests.Session()
    
    def get_markets(self, active: bool = True, limit: int = 100) -> List[Dict]:
        """获取市场列表"""
        try:
            response = self.session.get(
                f"{self.gamma_api}/markets",
                params={"active": str(active).lower(), "limit": limit},
                timeout=10
            )
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"获取市场列表失败: {e}")
            return []
    
    def get_order_book(self, token_id: str) -> Optional[Dict]:
        """获取订单簿"""
        try:
            response = self.session.get(
                f"{self.clob_api}/book/{token_id}",
                timeout=5
            )
            return response.json() if response.status_code == 200 else None
        except Exception as e:
            logger.error(f"获取订单簿失败: {e}")
            return None
    
    def get_price_history(self, token_id: str, interval: str = "1h", limit: int = 24) -> List[Dict]:
        """获取价格历史"""
        try:
            response = self.session.get(
                f"{self.clob_api}/prices-history",
                params={"token_id": token_id, "interval": interval, "limit": limit},
                timeout=5
            )
            return response.json().get('history', []) if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"获取价格历史失败: {e}")
            return []
    
    def get_fee_rate(self, token_id: str) -> float:
        """获取费率"""
        try:
            response = self.session.get(
                f"{self.clob_api}/fee-rate",
                params={"token_id": token_id},
                timeout=3
            )
            return response.json().get('feeRateBps', 0) / 10000 if response.status_code == 200 else 0
        except Exception as e:
            logger.error(f"获取费率失败: {e}")
            return 0
    
    def get_leaderboard(self, limit: int = 50) -> List[Dict]:
        """获取交易者排行榜"""
        try:
            response = self.session.get(
                f"{self.data_api}/leaderboard",
                params={"limit": limit, "timeframe": "30d"},
                timeout=10
            )
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"获取排行榜失败: {e}")
            return []
    
    def get_trades(self, user: str, limit: int = 100) -> List[Dict]:
        """获取用户交易记录"""
        try:
            response = self.session.get(
                f"{self.data_api}/trades",
                params={"user": user, "limit": limit},
                timeout=10
            )
            return response.json() if response.status_code == 200 else []
        except Exception as e:
            logger.error(f"获取交易记录失败: {e}")
            return []


class MarketDataManager:
    """市场数据管理器"""
    
    def __init__(self, api: PolymarketAPI):
        self.api = api
        self.markets_cache: Dict[str, Market] = {}
        self.last_update: datetime = datetime.min
        self.update_interval = 30  # 30秒更新一次
    
    async def update_markets(self) -> List[Market]:
        """更新市场数据"""
        now = datetime.now()
        if (now - self.last_update).seconds < self.update_interval:
            return list(self.markets_cache.values())
        
        logger.info("正在更新市场数据...")
        
        # 获取市场列表
        markets_data = self.api.get_markets(active=True, limit=100)
        
        updated_markets = []
        for data in markets_data:
            token_ids = data.get('clobTokenIds', [])
            if not token_ids:
                continue
            
            token_id = token_ids[0]  # Yes token
            
            # 创建市场对象
            market = Market(
                token_id=token_id,
                condition_id=data.get('conditionId', ''),
                question=data.get('question', ''),
                slug=data.get('slug', ''),
                volume_24h=float(data.get('volume24hr', 0)),
                neg_risk=data.get('negRisk', False),
                tick_size=float(data.get('minimumTickSize', 0.01)),
                expiration=datetime.fromisoformat(data.get('endDate', '').replace('Z', '+00:00')) 
                          if data.get('endDate') else None
            )
            
            # 获取订单簿数据
            order_book = self.api.get_order_book(token_id)
            if order_book:
                bids = order_book.get('bids', [])
                asks = order_book.get('asks', [])
                
                if bids:
                    market.best_bid = float(bids[0]['price'])
                if asks:
                    market.best_ask = float(asks[0]['price'])
                
                market.spread = market.best_ask - market.best_bid if market.best_ask and market.best_bid else 0
                
                # 计算流动性（前5档深度）
                bid_liquidity = sum(float(b['size']) * float(b['price']) for b in bids[:5])
                ask_liquidity = sum(float(a['size']) * float(a['price']) for a in asks[:5])
                market.liquidity = bid_liquidity + ask_liquidity
            
            # 获取费率
            market.fee_rate = self.api.get_fee_rate(token_id)
            
            self.markets_cache[token_id] = market
            updated_markets.append(market)
        
        self.last_update = now
        logger.info(f"已更新 {len(updated_markets)} 个市场")
        
        return updated_markets
    
    def get_market(self, token_id: str) -> Optional[Market]:
        """获取单个市场"""
        return self.markets_cache.get(token_id)
    
    def get_all_markets(self) -> List[Market]:
        """获取所有缓存的市场"""
        return list(self.markets_cache.values())
    
    def filter_liquid_markets(self, min_liquidity: float = 10000) -> List[Market]:
        """筛选流动性充足的市场"""
        return [m for m in self.markets_cache.values() if m.liquidity >= min_liquidity]


class ProfitSystem:
    """盈利系统主类"""
    
    def __init__(self, config_file: str = "config/system.json"):
        self.config = self._load_config(config_file)
        self.api = PolymarketAPI()
        self.data_manager = MarketDataManager(self.api)
        self.strategies: List[ProfitStrategy] = []
        self.signals_history: List[TradeSignal] = []
        self.running = False
        
        # 初始化策略
        self._init_strategies()
    
    def _load_config(self, config_file: str) -> Dict:
        """加载配置"""
        default_config = {
            "system": {
                "update_interval": 30,
                "analysis_interval": 60,
                "max_concurrent_trades": 5
            },
            "risk": {
                "max_total_exposure": 10000,
                "max_single_trade": 1000,
                "max_open_positions": 10,
                "stop_loss_pct": 0.15,
                "take_profit_pct": 0.30
            },
            "strategies": {
                "arbitrage": {"enabled": True, "min_profit": 0.02},
                "market_making": {"enabled": True, "spread_target": 0.02},
                "momentum": {"enabled": True, "timeframe": "1h"},
                "copy_trading": {"enabled": False}
            }
        }
        
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                user_config = json.load(f)
                # 合并配置
                for key in user_config:
                    if isinstance(user_config[key], dict) and key in default_config:
                        default_config[key].update(user_config[key])
                    else:
                        default_config[key] = user_config[key]
        
        return default_config
    
    def _init_strategies(self):
        """初始化策略"""
        # 延迟导入策略模块
        try:
            from strategies.arbitrage_strategy import ArbitrageStrategy
            from strategies.market_making_strategy import MarketMakingStrategy
            from strategies.momentum_strategy import MomentumStrategy
            from strategies.copy_trading_strategy import CopyTradingStrategy
            
            strategies_config = self.config.get('strategies', {})
            
            if strategies_config.get('arbitrage', {}).get('enabled', True):
                self.strategies.append(ArbitrageStrategy(strategies_config['arbitrage']))
                logger.info("已加载套利策略")
            
            if strategies_config.get('market_making', {}).get('enabled', True):
                self.strategies.append(MarketMakingStrategy(strategies_config['market_making']))
                logger.info("已加载做市策略")
            
            if strategies_config.get('momentum', {}).get('enabled', True):
                self.strategies.append(MomentumStrategy(strategies_config['momentum']))
                logger.info("已加载动量策略")
            
            if strategies_config.get('copy_trading', {}).get('enabled', False):
                self.strategies.append(CopyTradingStrategy(strategies_config['copy_trading']))
                logger.info("已加载跟单策略")
                
        except ImportError as e:
            logger.warning(f"策略模块导入失败: {e}")
    
    async def run(self):
        """运行系统"""
        self.running = True
        logger.info("=" * 60)
        logger.info("🚀 Polymarket 盈利系统启动")
        logger.info("=" * 60)
        
        while self.running:
            try:
                # 1. 更新市场数据
                markets = await self.data_manager.update_markets()
                
                if not markets:
                    logger.warning("没有获取到市场数据，等待重试...")
                    await asyncio.sleep(10)
                    continue
                
                # 2. 运行所有策略
                all_signals = []
                for strategy in self.strategies:
                    if not strategy.is_enabled():
                        continue
                    
                    try:
                        signals = await strategy.analyze(markets)
                        if signals:
                            all_signals.extend(signals)
                            logger.info(f"{strategy.name} 生成 {len(signals)} 个信号")
                    except Exception as e:
                        logger.error(f"{strategy.name} 分析失败: {e}")
                
                # 3. 筛选和执行信号
                if all_signals:
                    # 按预期收益排序
                    all_signals.sort(key=lambda x: x.expected_profit, reverse=True)
                    
                    logger.info(f"\n📊 本轮共发现 {len(all_signals)} 个交易机会")
                    
                    for signal in all_signals[:self.config['system']['max_concurrent_trades']]:
                        logger.info(f"\n🎯 信号: {signal.strategy_name}")
                        logger.info(f"   市场: {signal.market.question[:50]}")
                        logger.info(f"   操作: {signal.action} {signal.side}")
                        logger.info(f"   价格: {signal.price:.2%}")
                        logger.info(f"   预期收益: {signal.expected_profit:.2%}")
                        logger.info(f"   置信度: {signal.confidence:.1%}")
                        
                        # 保存信号
                        self.signals_history.append(signal)
                
                # 4. 等待下一轮
                interval = self.config['system']['analysis_interval']
                logger.info(f"\n⏱️ 等待 {interval} 秒...")
                await asyncio.sleep(interval)
                
            except KeyboardInterrupt:
                logger.info("\n👋 系统停止")
                self.running = False
            except Exception as e:
                logger.error(f"系统错误: {e}")
                await asyncio.sleep(10)
    
    def get_stats(self) -> Dict:
        """获取系统统计"""
        return {
            "total_signals": len(self.signals_history),
            "strategies_active": len([s for s in self.strategies if s.is_enabled()]),
            "markets_tracked": len(self.data_manager.markets_cache),
            "uptime": "running" if self.running else "stopped"
        }


async def main():
    """主函数"""
    # 创建日志目录
    os.makedirs('logs', exist_ok=True)
    
    # 创建系统实例
    system = ProfitSystem()
    
    # 运行
    await system.run()


if __name__ == "__main__":
    asyncio.run(main())
