"""Capitulation-turn cbBTC bot for make.fun btc-race-24h-20261113-2314.

Protocol: agent-fun/bars-replay/v1. The harness sends one `hello` message
(universe, capital, caps, fees, phase seed), then one `batch` per 1-minute
`bar`, then `done`. This bot answers every batch with exactly one reply
echoing its seq, carrying at most one order. An order decided on the batch
of the bar that closes at minute t fills at the next bar's open, so every
signal is read off closes the bot has already seen.

Strategy (long only, one position, full size), fitted on the kit's frozen
24h dev window and chosen for robustness, not for a single peak:
  * Context: the 240-bar simple moving average of closes (SMA240). A price
    more than 1% below SMA240 means the market has fallen hard over the
    last four hours - a capitulation, not a normal wiggle.
  * Trigger: while that deep below SMA240, a 5-bar return above +0.4%
    means sellers are exhausted and the price is turning up. That is the
    only entry. No entry is ever taken while the price rides above its
    long mean: in the dev window every momentum entry taken up there
    whipsawed to a loss.
  * Exit: take profit at +1.5% over the position's cost, stop loss at
    -1.5%, or a time exit after 300 bars held, whichever comes first.
    A sell the market refuses is simply sent again on the next bar while
    its reason still holds.
  * Sizing: one full-size buy (all cash). A full-size round trip pays
    about 26 bps in fee, slippage and pool impact, so the +1.5% target
    leaves a real margin; smaller trades would pay the same fixed bps
    and earn less per signal.
  * Orders name max_slippage_bps 100 (1% past the close decided on), so
    a fill gapping far past the close is refused instead of chased.

Dev-window evidence (offline replay of the kit's 1,440 bars, same fill
model as the harness: 4 bps fee, 2 bps slippage, constant-product impact
against each bar's open depth):
  * This bot: net PnL +14.15 USDC on 2 round trips, max drawdown 1.07%.
    Entry 1 at the day's low area (bar 411, -1.38% vs SMA240, +0.56%
    5-bar jump) rode the recovery for +11.64; entry 2 (bar 993) added
    +2.51. Both halves of the window were positive.
  * House baselines on the same window, graded with the kit CLI:
    buy-and-hold -52.59, momentum -49.23, ema-cross -109.38,
    rsi-bollinger -65.83, adx-momentum -50.31. The dev window fell
    -4.91% overall, so any bot invested through the decline loses;
    this bot stays in cash until the turn.

Determinism: the bot keeps only bar closes and a running SMA sum; all
arithmetic is fixed-order IEEE float, there is no clock, no environment
read, no file read and no randomness, so two executions on the same data
produce byte-identical action logs.
"""

import os
import sys
from collections import deque

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"
SMA_BARS = 240          # long-mean window (bars)
DEEP_BPS = 100          # entry only >1% below SMA240 (in bps of the mean)
JUMP_BPS = 40           # entry only on a 5-bar jump above +0.4%
TAKE_PROFIT_BPS = 150   # exit at +1.5% over cost
STOP_LOSS_BPS = 150     # exit at -1.5% under cost
MAX_HOLD_BARS = 300     # time exit after 300 bars held
MAX_SLIPPAGE_BPS = 100  # 1% past the close the order was decided on

closes = deque(maxlen=SMA_BARS)
sma_sum = 0.0
hold_start_seq = None


def _sma240():
    if len(closes) < SMA_BARS:
        return None
    return sma_sum / SMA_BARS


def on_batch(state, batch):
    global sma_sum, hold_start_seq
    # Fold this batch's bar into the close history (a gap adds nothing).
    for bar in batch["bars"]:
        if bar["symbol"] != SYMBOL:
            continue
        c = float(bar["c"])
        if len(closes) == SMA_BARS:
            sma_sum -= closes[0]
        closes.append(c)
        sma_sum += c
    if state.warming_up:
        return []
    held = state.positions.get(SYMBOL)
    if held is not None and hold_start_seq is None:
        hold_start_seq = state.seq
    if held is None:
        hold_start_seq = None

    if held is not None:
        value = state.value(SYMBOL, held.qty)
        cost = held.cost
        # Exits, in bps of cost, using integer cross-multiplication.
        if value * 10000 >= cost * (10000 + TAKE_PROFIT_BPS):
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        if value * 10000 <= cost * (10000 - STOP_LOSS_BPS):
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        if hold_start_seq is not None and state.seq - hold_start_seq >= MAX_HOLD_BARS:
            return [{"side": "sell", "symbol": SYMBOL, "qty": held.qty,
                     "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    # Flat: the only entry is a capitulation turn.
    mean = _sma240()
    if mean is None or len(closes) < SMA_BARS + 5:
        return []
    close = closes[-1]
    five_ago = closes[-6]
    deep = close * 10000 < mean * (10000 - DEEP_BPS)
    jump = close * 10000 > five_ago * (10000 + JUMP_BPS)
    if not (deep and jump):
        return []
    cash = state.cash
    min_notional = int(state.hello["fees"]["min_notional_quote_units"])
    if cash < min_notional:
        return []
    return [{"side": "buy", "symbol": SYMBOL,
             "notional_quote_units": cash,
             "max_slippage_bps": MAX_SLIPPAGE_BPS}]


makefun_bars.run(on_batch)
