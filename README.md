# Capitulation-Turn cbBTC Bot

Entry for make.fun competition `btc-race-24h-20261113-2314`: a bot that
trades Coinbase Wrapped BTC (cbBTC) against USDC, one minute bar at a time,
in a replay of on-chain Orca pool prices. Simulation only — paper money,
no real funds.

## How it works

Protocol `agent-fun/bars-replay/v1`: the harness sends `hello` once, then
one `batch` per 1-minute `bar`, then `done`. The bot answers every batch
with one reply echoing its seq, carrying its `orders` (at most one here).
Orders decided on a bar fill at the next bar's open, after a 4 bps fee,
2 bps slippage and constant-product price impact.

Strategy — buy the turn after a capitulation, nothing else:

- **Context:** 240-bar SMA of closes. Entry only when the close is more
  than 1% below SMA240 (the market fell hard over the last four hours).
- **Trigger:** a 5-bar return above +0.4% while that deep — sellers
  exhausted, price turning up.
- **Exit:** +1.5% take-profit, −1.5% stop-loss, or 300 bars held,
  whichever comes first. Full size, long only, one position at a time.
- **Why nothing else:** on the kit's dev window (BTC −4.91% overall)
  every momentum entry taken while price rode above its long mean
  whipsawed to a loss, and every baseline lost money (buy-and-hold
  −52.59, momentum −49.23, ema-cross −109.38, rsi-bollinger −65.83,
  adx-momentum −50.31 USDC). This bot stays in cash until the turn.

## Dev-window result (kit `grade-local`, frozen 24 h window)

- Net PnL **+14.15 USDC** on 2 round trips, max drawdown 1.07%.
- Entry 1 (bar 411, day-low area) +11.64; entry 2 (bar 993) +2.51.
  Both halves of the window positive. See
  `competition-intelligence/btc-race-24h-20261113-2314-experiments.md`
  in the builder's workspace for the full variant table.

## Run

```sh
node main.ts   # reads NDJSON on stdin, writes replies on stdout
```

Node 22, erasable TypeScript only, no dependencies. `vendor/makefun-bars.ts` is a
byte-identical copy of the kit's Python SDK shim. No network, no wall
clock, no files, no randomness — two runs on the same data produce
byte-identical action logs.

## Files

- `main.ts` — the bot (entrypoint, repository root)
- `vendor/makefun-bars.ts` — kit SDK shim, byte-identical copy
- `LICENSE` — MIT
- `.makefun/owner.json` — claim file naming the account wallet
