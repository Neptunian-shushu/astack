"""AStack admitted factors — 15min frequency, passed full evaluation pipeline.

Data: 2022-03 → 2026-03 (4 years) | Split: 7:2:1 | Test: 147 days OOS
Symbols: SOL, ETH, BTC | 15m bars | Quantile breakout strategy
Criteria: every year positive returns + val sharpe > 0 + test sharpe > 0

15min-frequency admitted factors (signal updates every bar):
  A. Order flow consistency: of_consistency_352 (CLV mean/std)
  B. Volume quality regime: vc_prop_minmax (1m vol-confirm proportion, min-max normalized)
  C. Clean structure persistence: clean_struct_persist (soft low-wick, body-weighted, minmax)

Daily-frequency factors are in daily_factors.py (separate library).
"""

from __future__ import annotations
import torch
import numpy as np
import pandas as pd
from ..factors import FactorRegistry


# ══════════════════════════════════════════════════════════════════
# A. Order Flow Consistency (15min frequency)
# ══════════════════════════════════════════════════════════════════

# 5/5 quantile | val=0.23~0.71 test=0.18~0.77
# Correlation with B: 0.014

def _astack_of_consistency_352(d: dict) -> torch.Tensor:
    """Rolling 352-bar close-location-value 一致性压力。
    CLV = (2*close - high - low) / (high - low)，衡量close在bar range中的位置。
    signal = mean(CLV, 352) / std(CLV, 352)，即买卖压力的信噪比。
    高值 = 持续稳定偏向高位收盘（买压一致）；低值 = 持续偏低位（卖压一致）。
    15min频率信号，每根bar更新。"""
    close, high, low = d['close'], d['high'], d['low']
    rng = high - low + 1e-9
    clv = (2 * close - high - low) / rng  # [-1, 1]
    window = 352
    cum1 = clv.cumsum(dim=1)
    cum2 = (clv ** 2).cumsum(dim=1)
    out = torch.zeros_like(close)
    m = (cum1[:, window:] - cum1[:, :-window]) / window
    m2 = (cum2[:, window:] - cum2[:, :-window]) / window
    std = (m2 - m ** 2).clamp(min=0).sqrt() + 1e-9
    out[:, window:] = m / std
    return out


# ══════════════════════════════════════════════════════════════════
# B. Volume Quality Regime (15min frequency, uses 1m data)
# ══════════════════════════════════════════════════════════════════

# 5/5 quantile | val=1.21~3.08 test=0.17~1.15 (body-weighted upgrade)
# Correlation with A: 0.014 (completely independent)
# Uses 1m volume confirmation data

# ── 1m volume confirmation cache (shared with daily_factors) ──

_1M_VOL_CACHE = {}

def _load_1m_vol_confirm():
    if _1M_VOL_CACHE:
        return
    from db_conn import build_sqlalchemy_url
    from sqlalchemy import create_engine

    engine = create_engine(build_sqlalchemy_url())
    symbols = ("SOL-USDT", "ETH-USDT", "BTC-USDT")
    sym_str = "'" + "','".join(symbols) + "'"

    print("[Admitted] Loading 1m data for volume confirmation...")
    df = pd.read_sql(f"""
        SELECT time, instrument_id, open, close, volume
        FROM ohlcv_source
        WHERE source = 'okx_spot_1m' AND instrument_id IN ({sym_str})
        ORDER BY instrument_id, time
    """, engine)
    df['time'] = pd.to_datetime(df['time'], utc=True)

    results = {}
    for sym in symbols:
        sdf = df[df['instrument_id'] == sym].sort_values('time').copy()
        sdf['bar_15m'] = sdf['time'].dt.floor('15min')
        grouped = sdf.groupby('bar_15m')
        agg = pd.DataFrame()
        agg['time'] = grouped['time'].first()

        def _vol_confirm(g):
            c = g['close'].values
            v = g['volume'].values
            if len(c) < 3:
                return 0.5
            rets = np.diff(c)
            bar_ret = c[-1] - c[0]
            if abs(bar_ret) < 1e-10:
                return 0.5
            bar_sign = np.sign(bar_ret)
            aligned = np.sign(rets) == bar_sign
            v_aligned = v[1:][aligned].sum()
            v_total = v[1:].sum()
            return v_aligned / (v_total + 1e-9)

        agg['q_vol_confirm'] = grouped.apply(_vol_confirm).values
        results[sym] = agg.reset_index(drop=True)

    common_times = None
    for sym in symbols:
        times = set(results[sym]['time'])
        common_times = times if common_times is None else common_times & times
    common_times = sorted(common_times)

    N, T = len(symbols), len(common_times)
    arr = np.zeros((N, T))
    for i, sym in enumerate(symbols):
        sym_df = results[sym].set_index('time').loc[common_times]
        arr[i] = sym_df['q_vol_confirm'].fillna(0).values
    _1M_VOL_CACHE['q_vol_confirm'] = torch.tensor(arr, dtype=torch.float32)
    print(f"[Admitted] 1m vol confirm cached, shape [{N}, {T}]")


def _get_vol_confirm(d: dict) -> torch.Tensor:
    _load_1m_vol_confirm()
    t = _1M_VOL_CACHE['q_vol_confirm']
    if t.device != d['close'].device:
        t = t.to(d['close'].device)
    N, T = d['close'].shape
    if t.shape[1] > T:
        t = t[:, :T]
    elif t.shape[1] < T:
        t = torch.cat([t, torch.zeros(t.shape[0], T - t.shape[1], device=t.device)], dim=1)
    if t.shape[0] < N:
        t = torch.cat([t, torch.zeros(N - t.shape[0], t.shape[1], device=t.device)], dim=0)
    return t[:N]


def _astack_vc_prop_minmax(d: dict) -> torch.Tensor:
    """1m成交量确认质量的regime-adaptive信号（实体加权clipped版）。
    Step 1: score = (vol_confirm > 0.6) * clip(sqrt(body_ratio), 0.4, 1.0)
    Step 2: vc_prop = rolling_mean(score, 480) — 5天窗口累积
    Step 3: min-max归一化到[-1,1]，窗口3000 bars (~31天)
    clip下限0.4避免长影线bar被过度降权，改善2022年熊市表现。
    15min频率信号，每根bar更新。"""
    vol_conf = _get_vol_confirm(d)
    close, open_p, high, low = d['close'], d['open'], d['high'], d['low']
    N, T = close.shape

    # Step 1: body-weighted vol-confirm score (clipped to avoid over-penalizing wicks)
    body_ratio = (close - open_p).abs() / (high - low + 1e-9)
    score = (vol_conf > 0.6).float() * body_ratio.sqrt().clamp(0.4, 1.0)
    cum = score.cumsum(dim=1)
    inner = 480
    vc_prop = torch.zeros(N, T)
    vc_prop[:, inner:] = (cum[:, inner:] - cum[:, :-inner]) / inner

    # Step 2: min-max normalization over 3000-bar window (~31 days)
    # Total warmup = inner (480) + mm_window (3000) to ensure all values in
    # the min-max window are valid vc_prop values (not warmup zeros).
    mm_window = 3000
    total_warmup = inner + mm_window
    # Output NaN during warmup so factor_test skips these bars automatically
    out = torch.full((N, T), float('nan'))
    vc_valid = vc_prop[:, inner:]  # only use bars where vc_prop is valid
    if vc_valid.shape[1] < mm_window:
        return out
    vc_unf = vc_valid.unfold(1, mm_window, 1)
    rmax = vc_unf.max(dim=2).values
    rmin = vc_unf.min(dim=2).values
    start = total_warmup - 1
    out[:, start:start + rmax.shape[1]] = 2 * (vc_valid[:, mm_window - 1:] - rmin) / (rmax - rmin + 1e-9) - 1
    return out


# ══════════════════════════════════════════════════════════════════
# C. Clean Structure Persistence (15min frequency)
# ══════════════════════════════════════════════════════════════════

# 5/5 quantile | val=0.48~1.58 test=1.23~2.38
# Correlation with A: -0.04, with B: +0.19 (independent)

def _astack_clean_struct_persist(d: dict) -> torch.Tensor:
    """低影线bar持续出现的regime信号（soft连续版+实体加权）。
    Step 1: wick_dom = 1 - body_ratio (影线占比)
    Step 2: soft距离 = clamp(q30 - wick_dom, 0) / q30 (连续距离, 非binary)
    Step 3: score = soft距离 × clip(√body_ratio, 0.4, 1.0) (实体加权)
    Step 4: state = rolling_mean(score, 400)
    Step 5: signal = minmax(state, 2500)
    高值 = 近期持续出现'干净结构'bar（低影线+大实体）。
    15min频率信号，每根bar更新。"""
    close, high, low, open_p = d['close'], d['high'], d['low'], d['open']
    N, T = close.shape
    rng = high - low + 1e-9
    body_ratio = (close - open_p).abs() / rng
    wick_dom = 1 - body_ratio

    # Rolling q30 over 3000 bars
    wick_unf = wick_dom.unfold(1, 3000, 1)
    q30 = torch.zeros(N, T)
    q30[:, 2999:] = torch.quantile(wick_unf, 0.3, dim=2)

    # Soft threshold + body weight
    soft = (q30 - wick_dom).clamp(min=0) / (q30 + 1e-9)
    score = soft * body_ratio.sqrt().clamp(0.4, 1.0)

    # State accumulation
    inner = 400
    cum = score.cumsum(dim=1)
    state = torch.zeros(N, T)
    state[:, inner:] = (cum[:, inner:] - cum[:, :-inner]) / inner

    # Minmax regime normalization
    mm_w = 2500
    warmup = 3000 + inner
    sv = state[:, warmup:]
    out = torch.full((N, T), float('nan'))
    if sv.shape[1] >= mm_w:
        su = sv.unfold(1, mm_w, 1)
        rmax = su.max(dim=2).values
        rmin = su.min(dim=2).values
        s = warmup + mm_w - 1
        out[:, s:s + rmax.shape[1]] = 2 * (sv[:, mm_w - 1:] - rmin) / (rmax - rmin + 1e-9) - 1
    return out


# ══════════════════════════════════════════════════════════════════
# Registration
# ══════════════════════════════════════════════════════════════════

def register_astack_admitted_factors():
    """Register 15min-frequency astack factors."""
    R = FactorRegistry.register
    R("astack_of_consistency_352", _astack_of_consistency_352,
      "Admitted: CLV consistency (mean/std) 352-bar | 5/5 quantile | 15min freq")
    R("astack_vc_prop_minmax", _astack_vc_prop_minmax,
      "Admitted: 1m vol-confirm proportion, minmax-3000 normalized | 5/5 quantile | 15min freq | corr=0.014")
    R("astack_clean_struct_persist", _astack_clean_struct_persist,
      "Admitted: soft low-wick persistence, body-weighted, minmax-2500 | 5/5 quantile | 15min freq | corr<0.2")
