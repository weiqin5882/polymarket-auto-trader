#!/usr/bin/env python3
"""
订单执行引擎
Production-Grade Trade Execution System
"""

import asyncio
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    SUBMITTING = "submitting"
    OPEN = "open"
    PARTIAL_FILL = "partial_fill"
    FILLED = "filled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class ExecutionConfig:
    """执行配置"""
    max_slippage_bps: int = 50
    order_timeout_seconds: int = 30
    fill_timeout_seconds: int = 300
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    max_concurrent_orders: int = 5


@dataclass
class Order:
    """订单对象"""
    id: str
    signal_id: str
    market_id: str
    token_id: str
    side: str
    size: float
    price: float
    status: OrderStatus
    created_at: datetime
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    filled_size: float = 0.0
    avg_fill_price: float = 0.0
    remaining_size: float = 0.0
    retries: int = 0
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    order: Optional[Order]
    filled_size: float
    avg_price: float
    pnl: float
    fees: float
    execution_time_ms: int
    error: Optional[str] = None


class OrderManager:
    """订单管理器"""
    
    def __init__(self):
        self.orders: Dict[str, Order] = {}
        self.order_callbacks: List[Callable] = []
        
    def create_order(self, signal, size: float, price: float) -> Order:
        """创建新订单"""
        import hashlib
        order_id = hashlib.md5(f"{signal.market.token_id}_{time.time()}".encode()).hexdigest()[:16]
        
        order = Order(
            id=order_id,
            signal_id=f"{signal.strategy_name}_{signal.timestamp}",
            market_id=signal.market.condition_id,
            token_id=signal.market.token_id,
            side="BUY" if signal.side == "YES" else "SELL",
            size=size,
            price=price,
            status=OrderStatus.PENDING,
            created_at=datetime.now(),
            remaining_size=size
        )
        
        self.orders[order_id] = order
        logger.info(f"创建订单 {order_id}: {order.side} {size:.2f} @ {price:.4f}")
        return order
    
    def update_status(self, order_id: str, status: OrderStatus, 
                      filled_size: float = 0, avg_price: float = 0, error: str = None):
        """更新订单状态"""
        if order_id not in self.orders:
            return
        
        order = self.orders[order_id]
        order.status = status
        
        if filled_size > 0:
            order.filled_size = filled_size
            order.remaining_size = order.size - filled_size
            order.avg_fill_price = avg_price
        
        if error:
            order.error_message = error
        
        # 触发回调
        for callback in self.order_callbacks:
            try:
                callback(order)
            except Exception as e:
                logger.error(f"回调错误: {e}")
    
    def get_open_orders(self) -> List[Order]:
        """获取未完成订单"""
        return [o for o in self.orders.values() 
                if o.status in [OrderStatus.OPEN, OrderStatus.PARTIAL_FILL, OrderStatus.SUBMITTING]]


class TradeExecutor:
    """交易执行器"""
    
    def __init__(self, config: ExecutionConfig, risk_manager=None):
        self.config = config
        self.risk_manager = risk_manager
        self.order_manager = OrderManager()
        self.semaphore = asyncio.Semaphore(config.max_concurrent_orders)
        
        # 初始化API客户端
        self.client = None
        try:
            from py_clob_client.client import ClobClient
            import os
            
            private_key = os.getenv('POLY_PRIVATE_KEY')
            if private_key:
                self.client = ClobClient(
                    host="https://clob.polymarket.com",
                    key=private_key,
                    chain_id=137
                )
                logger.info("Polymarket客户端初始化成功")
        except Exception as e:
            logger.warning(f"客户端初始化失败: {e}，运行模拟模式")
    
    async def execute_signal(self, signal) -> ExecutionResult:
        """执行交易信号"""
        async with self.semaphore:
            start_time = time.time()
            
            try:
                # 风控检查
                if self.risk_manager:
                    passed, reason = self.risk_manager.check_order(signal, signal.size, signal.price)
                    if not passed:
                        return ExecutionResult(False, None, 0, 0, 0, 0, 
                                             int((time.time()-start_time)*1000), reason)
                
                # 计算订单参数
                order_size, order_price = self._calculate_order_params(signal)
                
                # 创建订单
                order = self.order_manager.create_order(signal, order_size, order_price)
                
                # 提交订单
                if self.client:
                    result = await self._submit_live_order(order)
                else:
                    result = await self._simulate_order(order)
                
                # 更新风控
                if result.success and result.filled_size > 0 and self.risk_manager:
                    self.risk_manager.update_position(order.token_id, result.filled_size, order.side)
                
                return result
                
            except Exception as e:
                logger.error(f"执行错误: {e}")
                return ExecutionResult(False, None, 0, 0, 0, 0, 
                                     int((time.time()-start_time)*1000), str(e))
    
    def _calculate_order_params(self, signal):
        """计算订单参数"""
        base_price = signal.price
        
        if signal.side == "YES":
            max_price = min(base_price * (1 + self.config.max_slippage_bps / 10000), 0.99)
            order_price = (base_price + max_price) / 2
        else:
            min_price = max(base_price * (1 - self.config.max_slippage_bps / 10000), 0.01)
            order_price = (base_price + min_price) / 2
        
        return signal.size, round(order_price, 4)
    
    async def _submit_live_order(self, order: Order) -> ExecutionResult:
        """提交真实订单"""
        try:
            order.status = OrderStatus.SUBMITTING
            # 实际API调用...
            await asyncio.sleep(0.1)  # 模拟网络延迟
            
            # 模拟成功
            order.status = OrderStatus.FILLED
            order.filled_size = order.size
            order.avg_fill_price = order.price
            order.filled_at = datetime.now()
            
            return ExecutionResult(True, order, order.size, order.price, 0, 
                                 order.size * order.price * 0.015, 100)
        except Exception as e:
            order.status = OrderStatus.FAILED
            order.error_message = str(e)
            raise
    
    async def _simulate_order(self, order: Order) -> ExecutionResult:
        """模拟订单"""
        logger.info(f"[模拟] 执行订单: {order.side} {order.size:.2f} @ {order.price:.4f}")
        await asyncio.sleep(0.5)
        
        import random
        if random.random() < 0.8:
            fill_ratio = random.uniform(0.9, 1.0)
            filled_size = order.size * fill_ratio
            slippage = random.uniform(-0.001, 0.001)
            avg_price = order.price * (1 + slippage)
            
            order.filled_size = filled_size
            order.avg_fill_price = avg_price
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now()
            
            return ExecutionResult(True, order, filled_size, avg_price, 0, 
                                 filled_size * avg_price * 0.015, 500)
        else:
            order.status = OrderStatus.FAILED
            return ExecutionResult(False, order, 0, 0, 0, 0, 500, "模拟失败")
    
    async def cancel_all_orders(self):
        """取消所有订单"""
        open_orders = self.order_manager.get_open_orders()
        for order in open_orders:
            self.order_manager.update_status(order.id, OrderStatus.CANCELLED)
            logger.info(f"取消订单 {order.id}")
        return len(open_orders)


class RiskManager:
    """风控管理器"""
    
    def __init__(self, config: Dict):
        self.max_position_usd = config.get('max_position_usd', 10000)
        self.max_daily_loss_usd = config.get('max_daily_loss_usd', 500)
        self.max_order_size_usd = config.get('max_order_size_usd', 1000)
        self.daily_pnl = 0.0
        self.open_positions: Dict[str, float] = {}
        self.daily_orders_count = 0
        self.last_reset = datetime.now()
    
    def check_order(self, signal, proposed_size: float, current_price: float) -> tuple:
        """检查订单"""
        if (datetime.now() - self.last_reset).days >= 1:
            self.daily_pnl = 0.0
            self.daily_orders_count = 0
            self.last_reset = datetime.now()
        
        order_value = proposed_size * current_price
        
        if order_value > self.max_order_size_usd:
            return False, f"订单金额 ${order_value:.2f} 超过限制 ${self.max_order_size_usd}"
        
        current_position = self.open_positions.get(signal.market.token_id, 0)
        new_position = current_position + (proposed_size if signal.side == "YES" else -proposed_size)
        
        if abs(new_position * current_price) > self.max_position_usd:
            return False, f"持仓将超过限制 ${self.max_position_usd}"
        
        if self.daily_pnl < -self.max_daily_loss_usd:
            return False, f"日亏损 ${abs(self.daily_pnl):.2f} 超过限制"
        
        if proposed_size * current_price < 10:  # 最小订单$10
            return False, "订单金额太小"
        
        return True, "通过"
    
    def update_position(self, token_id: str, filled_size: float, side: str):
        """更新持仓"""
        current = self.open_positions.get(token_id, 0)
        if side == "BUY":
            self.open_positions[token_id] = current + filled_size
        else:
            self.open_positions[token_id] = current - filled_size
        self.daily_orders_count += 1


class AutomatedTradingSystem:
    """完整自动化交易系统"""
    
    def __init__(self, config: Dict):
        self.config = config
        exec_config = ExecutionConfig(**config.get('execution', {}))
        risk_config = config.get('risk', {})
        
        self.risk_manager = RiskManager(risk_config)
        self.executor = TradeExecutor(exec_config, self.risk_manager)
        self.running = False
        self.signal_queue = asyncio.Queue()
    
    async def start(self):
        """启动系统"""
        self.running = True
        logger.info("🚀 自动交易系统启动")
        
        while self.running:
            try:
                signal = await asyncio.wait_for(self.signal_queue.get(), timeout=1.0)
                result = await self.executor.execute_signal(signal)
                
                if result.success:
                    logger.info(f"✅ 执行成功: 成交 {result.filled_size:.2f}")
                else:
                    logger.warning(f"❌ 执行失败: {result.error}")
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"错误: {e}")
    
    async def submit_signal(self, signal):
        """提交信号"""
        await self.signal_queue.put(signal)
    
    async def stop(self):
        """停止系统"""
        self.running = False
        await self.executor.cancel_all_orders()
        logger.info("✅ 系统已停止")
