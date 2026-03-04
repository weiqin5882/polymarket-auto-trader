#!/usr/bin/env python3
"""
配置管理API
提供前端配置接口
"""

import json
import os
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

CONFIG_PATH = "config/trading_config.json"


def load_config():
    """加载配置"""
    try:
        with open(CONFIG_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return get_default_config()


def save_config(config):
    """保存配置"""
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2)


def get_default_config():
    """默认配置"""
    return {
        "auto_trading": {
            "enabled": True,
            "mode": "adaptive",
            "adaptive": {
                "base_amount_usd": 500,
                "max_amount_usd": 2000,
                "min_amount_usd": 100,
                "confidence_multiplier": {
                    "low": 0.5,
                    "medium": 1.0,
                    "high": 1.5,
                    "very_high": 2.0
                }
            }
        },
        "risk": {
            "max_position_usd": 10000,
            "max_daily_loss_usd": 500,
            "max_order_size_usd": 1000
        }
    }


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置"""
    config = load_config()
    return jsonify({"success": True, "config": config})


@app.route('/api/config', methods=['POST'])
def update_config():
    """更新配置"""
    try:
        new_config = request.json
        save_config(new_config)
        return jsonify({"success": True, "message": "配置已保存"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/config/preview', methods=['POST'])
def preview_amount():
    """预览金额计算"""
    try:
        data = request.json
        
        # 导入计算器
        import sys
        sys.path.insert(0, '..')
        from trading.amount_calculator import DynamicAmountCalculator
        
        calculator = DynamicAmountCalculator(data.get('config', {}))
        
        # 模拟信号
        class MockSignal:
            def __init__(self, d):
                self.confidence = d.get('confidence', 0.7)
                self.strategy_name = d.get('strategy', 'UnusualVolume')
                self.market = type('Market', (), {'token_id': 'mock'})()
        
        mock_signal = MockSignal(data)
        result = calculator.get_calculation_breakdown(
            mock_signal, 
            account_balance=data.get('account_balance', 10000)
        )
        
        return jsonify({"success": True, "preview": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/status', methods=['GET'])
def get_status():
    """获取系统状态"""
    return jsonify({
        "success": True,
        "status": "running",
        "version": "1.0.0",
        "mode": os.getenv('TRADING_MODE', 'dry-run')
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
