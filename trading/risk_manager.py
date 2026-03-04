#!/usr/bin/env python3
"""
风险管理模块
"""

from typing import Dict, Tuple
from datetime import datetime


class RiskManager:
    """风险管理器"""
    
    def __init__(self, config: Dict):
        self.max_position_usd = config.get('max_position_usd', 10000)
        self.max_daily_loss_usd = config.get('max_daily_loss_usd', 500)
        self.max_order_size_usd = config.get('max_order_size_usd', 1000)
        self.max_slippage_bps = config.get('max_slippage_bps', 100)
        
        self.daily_pnl = 0.0
        self.open_positions: Dict[str, float] = {}
        self.daily_orders_count = 0
        self.last_reset = datetime.now()
    
    def check_order(self, signal, proposed_size: float, current_price: float) -> Tuple[bool, str]:
        """
        检查订单是否通过风控
        
        Returns: (是否通过, 原因)
        """
        # 重置日计数
        if (datetime.now() - self.last_reset).days >= 1:
            self.daily_pnl = 0.0
            self.daily_orders_count = 0
            self.last_reset = datetime.now()
        
        order_value = proposed_size * current_price
        
        # 检查1: 单笔订单限制
        if order_value > self.max_order_size_usd:
            return False, f"订单金额 ${order_value:.2f} 超过最大限制 ${self.max_order_size_usd}"
        
        # 检查2: 最小订单金额
        if order_value < 10:
            return False, "订单金额太小（最小$10）"
        
        # 检查3: 总仓位限制
        current_position = self.open_positions.get(signal.market.token_id, 0)
        new_position = current_position + (proposed_size if signal.side == "YES" else -proposed_size)
        
        if abs(new_position * current_price) > self.max_position_usd:
            return False, f"持仓将超过最大限制 ${self.max_position_usd}"
        
        # 检查4: 单日亏损限制
        if self.daily_pnl < -self.max_daily_loss_usd:
            return False, f"日亏损 ${abs(self.daily_pnl):.2f} 超过限制 ${self.max_daily_loss_usd}"
        
        # 检查5: 单日订单数限制
        if self.daily_orders_count >= 50:
            return False, "日订单数量已达上限（50单）"
        
        # 检查6: 价格合理性
        if signal.price < 0.01 or signal.price > 0.99:
            return False, f"价格 {signal.price} 超出有效范围"
        
        return True, "通过风控检查"
    
    def update_position(self, token_id: str, filled_size: float, side: str):
        """更新持仓"""
        current = self.open_positions.get(token_id, 0)
        if side == "BUY":
            self.open_positions[token_id] = current + filled_size
        else:
            self.open_positions[token_id] = current - filled_size
        
        self.daily_orders_count += 1
    
    def update_pnl(self, pnl: float):
        """更新盈亏"""
        self.daily_pnl += pnl
    
    def get_position(self, token_id: str) -> float:
        """获取当前持仓"""
        return self.open_positions.get(token_id, 0.0)
    
    def get_total_exposure(self) -> float:
        """获取总敞口"""
        return sum(abs(pos) for pos in self.open_positions.values())
    
    def get_risk_report(self) -> Dict:
        """获取风险报告"""
        return {
            'daily_pnl': self.daily_pnl,
            'daily_orders': self.daily_orders_count,
            'total_exposure': self.get_total_exposure(),
            'max_position': self.max_position_usd,
            'position_usage': self.get_total_exposure() / self.max_position_usd if self.max_position_usd > 0 else 0,
            'open_positions': len(self.open_positions)
        }
