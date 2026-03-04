#!/usr/bin/env python3
"""
动态交易金额计算器
支持自适应、固定、百分比三种模式
"""

from typing import Dict
from enum import Enum


class AmountMode(Enum):
    ADAPTIVE = "adaptive"
    FIXED = "fixed"
    PERCENTAGE = "percentage"


class DynamicAmountCalculator:
    """动态金额计算器"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.mode = AmountMode(config.get('mode', 'adaptive'))
    
    def calculate(self, signal, account_balance: float = 10000) -> float:
        """计算交易金额"""
        if self.mode == AmountMode.FIXED:
            return self._calculate_fixed()
        elif self.mode == AmountMode.PERCENTAGE:
            return self._calculate_percentage(account_balance)
        else:
            return self._calculate_adaptive(signal)
    
    def _calculate_fixed(self) -> float:
        """固定金额"""
        fixed_config = self.config.get('fixed', {})
        return fixed_config.get('amount_usd', 500)
    
    def _calculate_percentage(self, account_balance: float) -> float:
        """百分比模式"""
        pct_config = self.config.get('percentage', {})
        percent = pct_config.get('percent_of_balance', 2.0)
        amount = account_balance * (percent / 100)
        
        max_amount = pct_config.get('max_amount_usd', 2000)
        min_amount = pct_config.get('min_amount_usd', 100)
        
        return max(min_amount, min(amount, max_amount))
    
    def _calculate_adaptive(self, signal) -> float:
        """自适应金额"""
        adaptive_config = self.config.get('adaptive', {})
        
        base = adaptive_config.get('base_amount_usd', 500)
        confidence = signal.confidence
        
        # 信心度乘数
        multipliers = adaptive_config.get('confidence_multiplier', {
            "low": 0.5, "medium": 1.0, "high": 1.5, "very_high": 2.0
        })
        
        if confidence < 0.6:
            conf_mult = multipliers.get('low', 0.5)
        elif confidence < 0.8:
            conf_mult = multipliers.get('medium', 1.0)
        elif confidence < 0.9:
            conf_mult = multipliers.get('high', 1.5)
        else:
            conf_mult = multipliers.get('very_high', 2.0)
        
        # 策略权重
        strategy_weights = adaptive_config.get('strategy_weights', {})
        strategy_mult = strategy_weights.get(signal.strategy_name, 1.0)
        
        raw_amount = base * conf_mult * strategy_mult
        
        max_amount = adaptive_config.get('max_amount_usd', 2000)
        min_amount = adaptive_config.get('min_amount_usd', 100)
        
        amount = max(min_amount, min(raw_amount, max_amount))
        
        return round(amount, 2)
    
    def get_calculation_breakdown(self, signal, account_balance: float = 10000) -> Dict:
        """获取计算分解"""
        if self.mode != AmountMode.ADAPTIVE:
            return {"mode": self.mode.value, "amount": self.calculate(signal, account_balance)}
        
        adaptive_config = self.config.get('adaptive', {})
        base = adaptive_config.get('base_amount_usd', 500)
        confidence = signal.confidence
        
        if confidence < 0.6:
            conf_level, conf_mult = "low", 0.5
        elif confidence < 0.8:
            conf_level, conf_mult = "medium", 1.0
        elif confidence < 0.9:
            conf_level, conf_mult = "high", 1.5
        else:
            conf_level, conf_mult = "very_high", 2.0
        
        strategy_weights = adaptive_config.get('strategy_weights', {})
        strategy_mult = strategy_weights.get(signal.strategy_name, 1.0)
        raw_amount = base * conf_mult * strategy_mult
        
        return {
            "mode": "adaptive",
            "base_amount": base,
            "confidence_level": conf_level,
            "confidence_multiplier": conf_mult,
            "strategy": signal.strategy_name,
            "strategy_weight": strategy_mult,
            "raw_amount": round(raw_amount, 2),
            "final_amount": self.calculate(signal, account_balance),
            "formula": f"{base} × {conf_mult} × {strategy_mult} = {round(raw_amount, 2)}"
        }
