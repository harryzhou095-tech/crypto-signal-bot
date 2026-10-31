import os
import requests
import numpy as np

# ==================== 配置区域 ====================
# 将下面的 "YOUR_SENDKEY" 换成你在 Server酱 复制的 SendKey
SERVERCHAN_KEY = os.getenv("SERVERCHAN_KEY", "SCT456982T9XamVAyJHgYDo5DFDcbyiUHD")

# 在这里配置你想监控的所有品类（ETH 和 BTC）
SYMBOLS = ["ETHUSDT", "BTCUSDT"] 
# ==================================================

def send_serverchan_message(title, content):
    """通过 Server酱 发送微信通知"""
    url = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
    data = {
        "title": title,
        "desp": content
    }
    try:
        response = requests.post(url, data=data, timeout=10)
        result = response.json()
        if result.get("code") == 0:
            print(f"[{title}] Server酱微信推送成功！")
        else:
            print(f"推送失败: {result.get('message')}")
    except Exception as e:
        print(f"网络请求异常: {e}")

def get_binance_klines(symbol, interval="1h", limit=200):
    """从币安公开接口免费获取指定品种的 K 线数据"""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url, timeout=10)
    data = response.json()
    closes = np.array([float(k[4]) for k in data])
    highs = np.array([float(k[2]) for k in data])
    lows = np.array([float(k[3]) for k in data])
    return closes, highs, lows

def calculate_ema(data, period):
    """计算指数移动平均线 (EMA)"""
    weights = np.exp(np.linspace(-1., 0., period))
    weights /= weights.sum()
    a = np.convolve(data, weights, mode='full')[:len(data)]
    a[:period] = a[period]
    return a

def calculate_macd(closes, fast=12, slow=26, signal=9):
    """计算 MACD 指标"""
    ema_fast = calculate_ema(closes, fast)
    ema_slow = calculate_ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    hist = macd_line - signal_line
    return macd_line, signal_line, hist

def check_single_symbol(symbol):
    """单币种策略检测：4H大方向 + 1H Vegas回踩 + MACD金叉"""
    try:
        # 1. 获取 4H 数据定大方向
        closes_4h, _, _ = get_binance_klines(symbol, "4h", 200)
        ema144_4h = calculate_ema(closes_4h, 144)
        ema169_4h = calculate_ema(closes_4h, 169)
        htf_bull = closes_4h[-1] >= min(ema144_4h[-1], ema169_4h[-1])
        
        # 2. 获取 1H 数据找买点
        closes_1h, highs_1h, lows_1h = get_binance_klines(symbol, "1h", 200)
        ema12_1h = calculate_ema(closes_1h, 12)
        ema144_1h = calculate_ema(closes_1h, 144)
        ema169_1h = calculate_ema(closes_1h, 169)
        
        macd_line, signal_line, _ = calculate_macd(closes_1h)
        
        # 判断 1H 级别金叉 (前一根线 MACD<Signal，当前线 MACD>Signal)
        macd_cross_up = (macd_line[-2] < signal_line[-2]) and (macd_line[-1] > signal_line[-1])
        
        tunnel_top = max(ema144_1h[-1], ema169_1h[-1])
        tunnel_bottom = min(ema144_1h[-1], ema169_1h[-1])
        
        # 过去 6 根 K 线内最低价回踩过通道上方或内部，且当前收盘站稳
        touch_support = np.min(lows_1h[-6:]) <= tunnel_top * 1.02 and closes_1h[-1] > tunnel_bottom
        
        # 触发多头共振条件
        if htf_bull and touch_support and ema12_1h[-1] >= tunnel_bottom and macd_cross_up:
            price = closes_1h[-1]
            title = f"🔥【10U期权提醒】{symbol} 触发 1H/4H 多头共振！"
            content = (
                f"### 🚀 交易信号触发\n\n"
                f"- **标的**: `{symbol}` (1H/4H Vegas + MACD)\n"
                f"- **当前现价**: `{price}`\n"
                f"- **触发形态**: 1H回踩Vegas通道 + 发生MACD金叉\n\n"
                f"--- \n"
                f"### 💡 期权操盘建议：\n"
                f"1. 打开币安期权，挑选距离到期 **4 ~ 7 天**、Delta 在 **0.25 ~ 0.35** 的看涨 Call。\n"
                f"2. 严格按 10U 仓位买入（ETH可买0.04张，BTC可买0.01张）。\n"
                f"3. 立即挂好 **2倍保本单**（卖出一半）与 **4倍暴利单**（卖出另一半）。"
            )
            send_serverchan_message(title, content)
            print(f"已向微信发送 {symbol} 的看涨信号！")
        else:
            print(f"{symbol} 暂无信号，当前 1H 价格: {closes_1h[-1]}")
    except Exception as e:
        print(f"检测 {symbol} 时发生错误: {e}")

def run_all():
    """循环检测所有配置的品类"""
    print(f"开始执行多币种行情巡检...")
    for symbol in SYMBOLS:
        check_single_symbol(symbol)

if __name__ == "__main__":
    run_all()
