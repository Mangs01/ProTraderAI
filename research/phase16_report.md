# Phase 16 — Entry edge forensics

**Decision: A — NEW ENTRY HYPOTHESIS REQUIRED.** Diagnostic only; no tuning, strategy rerun, production or engine changes.

## Integrity, event source and methodology

Dataset `data/validation_NSE_3045_FIVE_MINUTE_2026-03-08_2026-09-08.csv`; SHA256 `fe9126c1745f61957ae24a840569600ff7e036b59d0cc55be6c68ae6d3603ed6`. Metadata SHA256 `e10135f17a9bf00cc9aa62c5150c081d461461f7ad8b13652f7323832b56ee67`. Phase15 JSON SHA256 `17243c8ee6b7d8cb5c160c48226895b95b0ccc30bc329090ea9ce532d8faaf89`. Both exact requested hashes verified; 9,309 rows, 9,294 regular, 15 CAS auxiliary excluded, 125 sessions (98 LEGACY / 27 CAS). 92 frozen file hashes verified before and after diagnostics.

LOADED: saved signal_events and trades; zero reconstruction or strategy runs

**universe:** All 482 canonical emitted entries, E=92 F=142 G=248; every saved signal executed. No filtering, strategy generation, tuning or engine calls.

**source:** Phase15 signal_events, trades and correctness_audit.details.signal_atr loaded. Existing causal Indicators functions reconstruct signal context only, after regular-bar filtering.

**reference:** Signal N is a completed candle labelled by its start. Execution at physical N+1 open equals signal completion time. A references signal close; B references raw N+1 open. Slipped fill retained separately.

**forward:** H=1,2,3,6,12 uses close at entry_index+H-1 = signal_index+H. The entry candle is the first completed future candle. Continue measurement after actual exit, never after regular session ends; unavailable = null. Approximate elapsed horizons 5/10/15/30/60 minutes.

**direction:** BUY=future/reference-1; SELL=reference/future-1. Percent tables multiply by 100. ATR moves use (future-reference)/signal_ATR for BUY and (reference-future)/signal_ATR for SELL; this is price-linear, unlike reciprocal SELL percentage.

**statistics:** Sample standard deviation ddof=1; linear quantiles; zero return is not positive. Null for unavailable statistics or undefined PF (no gross losses). N always reports actual availability. Net pnl >0 winner, <0 loser; all zero/breakeven groups retained in JSON.

**excursions:** Raw entry reference; zero floor. Confirmed lower bound uses all entry-to-pre-exit candles plus exit open and recorded raw exit. EOD includes full final candle. Upper bound additionally uses entire exit-candle high/low, which may occur after fill. Exact pre-exit extrema and ordering are unknowable from OHLC; bounds replace invented precision. In gap exits, confirmed is exact; upper deliberately remains a loose candle bound.

**geometry:** Actual levels are around SLIPPED entry: stop 1.5 ATR and target 2 ATR, RR=4/3. Raw-reference threshold diagnostic is separately labelled and censored at actual exit; it is not an alternative backtest. Gap precedes range; STOP wins unresolved same-bar collisions. Full exit-candle raw-threshold probabilities are candle proxies; confirmed-path probabilities and unresolved counts are also provided.

**duration:** bars = exit_index-entry_index; minutes = bar-start timestamp difference = bars*5, not precise fill elapsed time. Executable candles = bars+1, so same-entry-candle exit=1 candle, 0 bar-start minutes. Within-N probabilities use candles<=N (within N*5 minutes upper bound). Intrabar actual duration lies between reported minutes and minutes+5; gap exit is at lower bound; EOD at upper bound.

**immediate:** Entry candle high/low vs raw entry: favorable/adverse/BOTH/neither. BOTH asserts no sequence. Next-bar close return equals raw-open 1-bar diagnostic, independent of exit.

**characteristics:** Only family-used frozen fields: RSI, ATR, ATR/close%, VWAP distance, signal clock minute; E additionally EMA20/50 distances and spread; F Volume/VolumeSMA20 and side-relative OR boundary distance; G EMA20 distance. Distances price units, ATR/close percent, time minutes since midnight; no new indicators. Winner/loser comparison is descriptive, with side splits in JSON.

**time_buckets:** Buckets use physical entry time, final bucket ends at regime entry limit. Six entries predate 09:30 (E4, G2); retained in OUTSIDE_PREDEFINED rather than discarded or misassigned. Exact signal cutoffs LEGACY 15:05, CAS 15:00; corresponding entry limits 15:10 and 15:05.

**volatility:** Pooled complete 482-trade sample; one linear quantile computation at 1/3 and 2/3; <= lower LOW, <= upper MID, else HIGH. Labels are post-hoc and never signal inputs.

**cost:** All saved charges used at full precision. Gross pnl includes slippage and excludes explicit fees. Raw-price pnl minus quantity*(entry_slippage+exit_slippage) equals saved gross. Raw-price pnl holds actual fills/exit levels/quantity/path fixed: not a zero-slippage strategy counterfactual. Ratios use saved fill turnover and absolute saved gross.

**safety:** Diagnostic process blocks socket/DNS/process calls and broker/live/SmartAPI imports before project imports. Zero attempts. Regression suite separately has intentional caught network-denial probes and fake historical transport/auth tests; zero external network activity, not zero synthetic test invocations.

## Samples and saved outcomes

| Family | Side/group | N | Gross INR | Net INR | Gross PF | Net win % |
| --- | --- | --- | --- | --- | --- | --- |
| E | ALL | 92 | -21985.0678 | -35768.3083 | 0.5787 | 35.8696 |
| E | BUY | 44 | -11718.0244 | -18061.8044 | 0.5411 | 34.0909 |
| E | SELL | 48 | -10267.0434 | -17706.5039 | 0.6147 | 37.5000 |
| E | WINNER | 33 | 30181.5079 | 25204.6076 | NA | 100.0000 |
| E | LOSER | 59 | -52166.5758 | -60972.9158 | 0.0003 | 0.0000 |
| E | BREAKEVEN | 0 | 0 | 0 | NA | NA |
| E | STOP_LOSS | 52 | -50542.2995 | -58372.8285 | 0.0000 | 0.0000 |
| E | TARGET | 31 | 28999.0114 | 24304.3023 | NA | 100.0000 |
| E | END_OF_SESSION | 9 | -441.7798 | -1699.7821 | 0.7304 | 22.2222 |
| F | ALL | 142 | -29636.8787 | -48672.6276 | 0.6124 | 37.3239 |
| F | BUY | 66 | -25570.3911 | -33936.1147 | 0.3791 | 27.2727 |
| F | SELL | 76 | -4066.4876 | -14736.5129 | 0.8847 | 46.0526 |
| F | WINNER | 53 | 46817.0173 | 39609.1120 | NA | 100.0000 |
| F | LOSER | 89 | -76453.8960 | -88281.7396 | 0.0000 | 0.0000 |
| F | BREAKEVEN | 0 | 0 | 0 | NA | NA |
| F | STOP_LOSS | 84 | -74983.1591 | -86083.5948 | 0.0000 | 0.0000 |
| F | TARGET | 50 | 46270.4581 | 39394.5307 | NA | 100.0000 |
| F | END_OF_SESSION | 8 | -924.1777 | -1983.5635 | 0.3716 | 37.5000 |
| G | ALL | 248 | -53290.4684 | -79818.2109 | 0.4765 | 31.4516 |
| G | BUY | 135 | -33039.9927 | -47441.2517 | 0.4291 | 28.1481 |
| G | SELL | 113 | -20250.4758 | -32376.9593 | 0.5389 | 35.3982 |
| G | WINNER | 78 | 48314.8351 | 40221.6951 | NA | 100.0000 |
| G | LOSER | 170 | -101605.3035 | -120039.9060 | 0.0018 | 0.0000 |
| G | BREAKEVEN | 0 | 0 | 0 | NA | NA |
| G | STOP_LOSS | 162 | -101145.5490 | -118819.8293 | 0.0000 | 0.0000 |
| G | TARGET | 77 | 48229.0089 | 40208.1187 | NA | 100.0000 |
| G | END_OF_SESSION | 9 | -373.9284 | -1206.5004 | 0.4213 | 11.1111 |

## Fixed forward returns and ATR units

All statistics use every available observation. Both reference prices shown. Signal-close forward measurement is not an executable fill assumption. Std is sample standard deviation. Full winner/loser and exit-conditioned horizon tables are in JSON, alongside all event records.

### E: signal_close

| Side | H | N | Mean % | Median % | Std % | Positive % | p25 % | p75 % | Mean ATR | Median ATR | p25 ATR | p75 ATR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | 1 | 92 | 0.0039 | 0.0071 | 0.0991 | 53.2609 | -0.0522 | 0.0502 | 0.0149 | 0.0339 | -0.2845 | 0.2897 |
| ALL | 2 | 92 | 0.0294 | 0.0266 | 0.1650 | 63.0435 | -0.0580 | 0.1139 | 0.1405 | 0.1562 | -0.3269 | 0.5100 |
| ALL | 3 | 92 | 0.0047 | 0.0104 | 0.2071 | 54.3478 | -0.1055 | 0.1448 | 0.0312 | 0.0579 | -0.4983 | 0.6405 |
| ALL | 6 | 85 | -0.0317 | -0.0195 | 0.2975 | 45.8824 | -0.1533 | 0.0968 | -0.0879 | -0.1273 | -0.8522 | 0.6495 |
| ALL | 12 | 75 | 0.0330 | 0.0390 | 0.4029 | 56.0000 | -0.1445 | 0.2046 | 0.1795 | 0.1965 | -0.7694 | 0.9496 |
| BUY | 1 | 44 | 0.0074 | 0.0071 | 0.1088 | 56.8182 | -0.0541 | 0.0691 | 0.0430 | 0.0359 | -0.2942 | 0.3346 |
| BUY | 2 | 44 | 0.0328 | 0.0219 | 0.1876 | 61.3636 | -0.0580 | 0.1139 | 0.1571 | 0.1377 | -0.2960 | 0.5221 |
| BUY | 3 | 44 | 0.0167 | 0.0145 | 0.1741 | 56.8182 | -0.0751 | 0.1506 | 0.0828 | 0.0639 | -0.4448 | 0.6405 |
| BUY | 6 | 40 | -0.0073 | -0.0048 | 0.3287 | 47.5000 | -0.1550 | 0.1151 | 0.0187 | -0.0235 | -0.7688 | 0.5921 |
| BUY | 12 | 37 | 0.0568 | 0.0048 | 0.3369 | 51.3514 | -0.1332 | 0.1732 | 0.2735 | 0.0365 | -0.5818 | 0.7047 |
| SELL | 1 | 48 | 0.0008 | 0.0048 | 0.0904 | 50.0000 | -0.0522 | 0.0392 | -0.0108 | 0.0167 | -0.2525 | 0.2098 |
| SELL | 2 | 48 | 0.0262 | 0.0290 | 0.1431 | 64.5833 | -0.0612 | 0.0898 | 0.1253 | 0.1562 | -0.4748 | 0.4543 |
| SELL | 3 | 48 | -0.0064 | 0.0078 | 0.2347 | 52.0833 | -0.1085 | 0.1011 | -0.0160 | 0.0421 | -0.6236 | 0.6093 |
| SELL | 6 | 45 | -0.0533 | -0.0311 | 0.2687 | 44.4444 | -0.1533 | 0.0872 | -0.1826 | -0.1923 | -0.8720 | 0.6495 |
| SELL | 12 | 38 | 0.0099 | 0.0668 | 0.4617 | 60.5263 | -0.2658 | 0.2460 | 0.0879 | 0.4523 | -1.4578 | 1.3099 |

### E: raw_open

| Side | H | N | Mean % | Median % | Std % | Positive % | p25 % | p75 % | Mean ATR | Median ATR | p25 ATR | p75 ATR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | 1 | 92 | 0.0040 | 0.0073 | 0.0995 | 52.1739 | -0.0522 | 0.0562 | 0.0125 | 0.0313 | -0.2911 | 0.2957 |
| ALL | 2 | 92 | 0.0294 | 0.0215 | 0.1644 | 61.9565 | -0.0556 | 0.1055 | 0.1381 | 0.1326 | -0.3491 | 0.4775 |
| ALL | 3 | 92 | 0.0047 | 0.0144 | 0.2060 | 54.3478 | -0.0838 | 0.1299 | 0.0288 | 0.0899 | -0.4764 | 0.6287 |
| ALL | 6 | 85 | -0.0320 | -0.0195 | 0.2947 | 45.8824 | -0.1488 | 0.1016 | -0.0926 | -0.1099 | -0.7410 | 0.5350 |
| ALL | 12 | 75 | 0.0328 | 0.0292 | 0.4024 | 54.6667 | -0.1445 | 0.1994 | 0.1762 | 0.1915 | -0.7741 | 0.9496 |
| BUY | 1 | 44 | 0.0034 | 0.0048 | 0.1083 | 52.2727 | -0.0607 | 0.0691 | 0.0177 | 0.0262 | -0.2924 | 0.3226 |
| BUY | 2 | 44 | 0.0288 | 0.0192 | 0.1872 | 56.8182 | -0.0510 | 0.1000 | 0.1318 | 0.1114 | -0.3439 | 0.4775 |
| BUY | 3 | 44 | 0.0128 | 0.0172 | 0.1740 | 52.2727 | -0.0732 | 0.1399 | 0.0575 | 0.0881 | -0.4004 | 0.6405 |
| BUY | 6 | 40 | -0.0121 | -0.0097 | 0.3263 | 47.5000 | -0.1538 | 0.1046 | -0.0111 | -0.0491 | -0.7179 | 0.5179 |
| BUY | 12 | 37 | 0.0525 | -0.0193 | 0.3386 | 48.6486 | -0.1332 | 0.1735 | 0.2461 | -0.1458 | -0.5761 | 0.8456 |
| SELL | 1 | 48 | 0.0045 | 0.0098 | 0.0919 | 52.0833 | -0.0515 | 0.0510 | 0.0078 | 0.0403 | -0.2683 | 0.2609 |
| SELL | 2 | 48 | 0.0299 | 0.0297 | 0.1424 | 66.6667 | -0.0588 | 0.1055 | 0.1438 | 0.1818 | -0.4275 | 0.4477 |
| SELL | 3 | 48 | -0.0027 | 0.0144 | 0.2330 | 56.2500 | -0.1091 | 0.0988 | 0.0025 | 0.0899 | -0.6385 | 0.5981 |
| SELL | 6 | 45 | -0.0498 | -0.0290 | 0.2660 | 44.4444 | -0.1282 | 0.0968 | -0.1651 | -0.1923 | -0.7742 | 0.5350 |
| SELL | 12 | 38 | 0.0137 | 0.0656 | 0.4600 | 60.5263 | -0.2656 | 0.2434 | 0.1081 | 0.4523 | -1.4656 | 1.2558 |

### F: signal_close

| Side | H | N | Mean % | Median % | Std % | Positive % | p25 % | p75 % | Mean ATR | Median ATR | p25 ATR | p75 ATR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | 1 | 142 | -0.0078 | -0.0195 | 0.1566 | 44.3662 | -0.0964 | 0.0887 | -0.0288 | -0.0651 | -0.4368 | 0.4456 |
| ALL | 2 | 142 | -0.0091 | -0.0097 | 0.2169 | 46.4789 | -0.1167 | 0.1030 | -0.0114 | -0.0568 | -0.4991 | 0.5348 |
| ALL | 3 | 142 | 0.0021 | 0.0023 | 0.2857 | 50.0000 | -0.1131 | 0.1374 | 0.0355 | 0.0102 | -0.6945 | 0.6621 |
| ALL | 6 | 140 | -0.0019 | -0.0095 | 0.3680 | 49.2857 | -0.2186 | 0.2144 | 0.0048 | -0.0381 | -1.0076 | 0.8335 |
| ALL | 12 | 133 | 0.0178 | 0.0413 | 0.4974 | 54.8872 | -0.2501 | 0.3268 | 0.0567 | 0.2258 | -1.2383 | 1.3880 |
| BUY | 1 | 66 | -0.0294 | -0.0495 | 0.1748 | 40.9091 | -0.1349 | 0.0812 | -0.0768 | -0.1813 | -0.5542 | 0.3920 |
| BUY | 2 | 66 | -0.0200 | -0.0395 | 0.2470 | 43.9394 | -0.1657 | 0.1304 | -0.0220 | -0.1694 | -0.7119 | 0.5842 |
| BUY | 3 | 66 | -0.0309 | -0.0330 | 0.3376 | 42.4242 | -0.2346 | 0.1213 | -0.1052 | -0.1564 | -1.0135 | 0.4625 |
| BUY | 6 | 64 | -0.0292 | -0.0665 | 0.4272 | 42.1875 | -0.3165 | 0.2283 | -0.0736 | -0.3354 | -1.3360 | 0.8113 |
| BUY | 12 | 62 | -0.0203 | -0.1166 | 0.5794 | 40.3226 | -0.3972 | 0.3781 | -0.1288 | -0.5280 | -1.5245 | 1.2560 |
| SELL | 1 | 76 | 0.0111 | 0.0000 | 0.1373 | 47.3684 | -0.0685 | 0.0963 | 0.0128 | 0.0000 | -0.3565 | 0.4585 |
| SELL | 2 | 76 | 0.0003 | 0.0000 | 0.1880 | 48.6842 | -0.0778 | 0.0925 | -0.0022 | 0.0000 | -0.3844 | 0.4920 |
| SELL | 3 | 76 | 0.0306 | 0.0352 | 0.2300 | 56.5789 | -0.0776 | 0.1500 | 0.1576 | 0.1321 | -0.4955 | 0.7048 |
| SELL | 6 | 76 | 0.0211 | 0.0389 | 0.3106 | 55.2632 | -0.0999 | 0.2071 | 0.0708 | 0.2132 | -0.5857 | 0.8335 |
| SELL | 12 | 71 | 0.0510 | 0.0861 | 0.4143 | 67.6056 | -0.0845 | 0.3186 | 0.2187 | 0.4016 | -0.3985 | 1.3980 |

### F: raw_open

| Side | H | N | Mean % | Median % | Std % | Positive % | p25 % | p75 % | Mean ATR | Median ATR | p25 ATR | p75 ATR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | 1 | 142 | -0.0060 | -0.0100 | 0.1551 | 44.3662 | -0.1029 | 0.0840 | -0.0186 | -0.0412 | -0.4325 | 0.4192 |
| ALL | 2 | 142 | -0.0074 | -0.0046 | 0.2143 | 47.8873 | -0.1112 | 0.0968 | -0.0012 | -0.0192 | -0.4715 | 0.5009 |
| ALL | 3 | 142 | 0.0038 | 0.0047 | 0.2843 | 50.0000 | -0.1205 | 0.1400 | 0.0457 | 0.0160 | -0.6646 | 0.6572 |
| ALL | 6 | 140 | 0.0001 | -0.0097 | 0.3669 | 49.2857 | -0.2127 | 0.2183 | 0.0167 | -0.0628 | -0.9401 | 0.8574 |
| ALL | 12 | 133 | 0.0199 | 0.0567 | 0.4982 | 54.1353 | -0.2434 | 0.3373 | 0.0704 | 0.2625 | -1.2130 | 1.4080 |
| BUY | 1 | 66 | -0.0322 | -0.0482 | 0.1724 | 39.3939 | -0.1286 | 0.0758 | -0.0909 | -0.2160 | -0.5412 | 0.3662 |
| BUY | 2 | 66 | -0.0228 | -0.0347 | 0.2448 | 43.9394 | -0.1556 | 0.1134 | -0.0361 | -0.1427 | -0.7165 | 0.5778 |
| BUY | 3 | 66 | -0.0336 | -0.0243 | 0.3362 | 42.4242 | -0.2353 | 0.0910 | -0.1193 | -0.1318 | -1.0326 | 0.4059 |
| BUY | 6 | 64 | -0.0316 | -0.0807 | 0.4261 | 40.6250 | -0.3079 | 0.2512 | -0.0848 | -0.3441 | -1.3598 | 0.8144 |
| BUY | 12 | 62 | -0.0224 | -0.1116 | 0.5804 | 38.7097 | -0.3972 | 0.3973 | -0.1378 | -0.5280 | -1.5142 | 1.3228 |
| SELL | 1 | 76 | 0.0167 | 0.0000 | 0.1353 | 48.6842 | -0.0622 | 0.1043 | 0.0441 | 0.0000 | -0.3229 | 0.4398 |
| SELL | 2 | 76 | 0.0060 | 0.0099 | 0.1845 | 51.3158 | -0.0780 | 0.0822 | 0.0291 | 0.0535 | -0.3887 | 0.4688 |
| SELL | 3 | 76 | 0.0363 | 0.0414 | 0.2275 | 56.5789 | -0.0640 | 0.1500 | 0.1890 | 0.1187 | -0.3702 | 0.7048 |
| SELL | 6 | 76 | 0.0268 | 0.0438 | 0.3088 | 56.5789 | -0.0987 | 0.2054 | 0.1021 | 0.2501 | -0.5553 | 0.8574 |
| SELL | 12 | 71 | 0.0569 | 0.0956 | 0.4141 | 67.6056 | -0.0845 | 0.3144 | 0.2522 | 0.4308 | -0.3985 | 1.4220 |

### G: signal_close

| Side | H | N | Mean % | Median % | Std % | Positive % | p25 % | p75 % | Mean ATR | Median ATR | p25 ATR | p75 ATR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | 1 | 248 | -0.0091 | 0.0096 | 0.1761 | 51.6129 | -0.0799 | 0.0808 | -0.0395 | 0.0519 | -0.3693 | 0.3929 |
| ALL | 2 | 248 | -0.0134 | 0.0096 | 0.2031 | 51.2097 | -0.1161 | 0.1042 | -0.0678 | 0.0519 | -0.5617 | 0.4923 |
| ALL | 3 | 247 | -0.0154 | 0.0185 | 0.2771 | 51.8219 | -0.1228 | 0.1245 | -0.0619 | 0.0714 | -0.6372 | 0.6095 |
| ALL | 6 | 240 | -0.0297 | 0.0071 | 0.3594 | 50.4167 | -0.1997 | 0.1718 | -0.1609 | 0.0330 | -0.8724 | 0.7817 |
| ALL | 12 | 234 | -0.0329 | 0.0020 | 0.4554 | 50.0000 | -0.2652 | 0.2162 | -0.1840 | 0.0070 | -1.2045 | 1.0832 |
| BUY | 1 | 135 | -0.0020 | 0.0000 | 0.1287 | 49.6296 | -0.0745 | 0.0585 | 0.0069 | 0.0000 | -0.3123 | 0.3074 |
| BUY | 2 | 135 | -0.0037 | 0.0096 | 0.1639 | 51.1111 | -0.0880 | 0.0952 | -0.0201 | 0.0411 | -0.4474 | 0.4530 |
| BUY | 3 | 134 | -0.0059 | 0.0193 | 0.2188 | 54.4776 | -0.1156 | 0.1086 | 0.0016 | 0.0975 | -0.5091 | 0.5395 |
| BUY | 6 | 129 | -0.0123 | -0.0097 | 0.3050 | 46.5116 | -0.1512 | 0.1425 | -0.0533 | -0.0498 | -0.7913 | 0.5969 |
| BUY | 12 | 129 | -0.0154 | -0.0103 | 0.3771 | 47.2868 | -0.2262 | 0.1624 | -0.1104 | -0.0773 | -1.0270 | 0.7829 |
| SELL | 1 | 113 | -0.0177 | 0.0189 | 0.2201 | 53.9823 | -0.1124 | 0.0924 | -0.0950 | 0.0690 | -0.4290 | 0.4455 |
| SELL | 2 | 113 | -0.0250 | 0.0098 | 0.2420 | 51.3274 | -0.1323 | 0.1178 | -0.1248 | 0.0664 | -0.6779 | 0.6222 |
| SELL | 3 | 113 | -0.0266 | 0.0000 | 0.3341 | 48.6726 | -0.1870 | 0.1382 | -0.1372 | 0.0000 | -0.8317 | 0.7937 |
| SELL | 6 | 111 | -0.0500 | 0.0487 | 0.4143 | 54.9550 | -0.2882 | 0.2213 | -0.2860 | 0.2917 | -1.0876 | 0.9797 |
| SELL | 12 | 105 | -0.0543 | 0.0720 | 0.5373 | 53.3333 | -0.4159 | 0.3241 | -0.2744 | 0.3993 | -1.6295 | 1.4620 |

### G: raw_open

| Side | H | N | Mean % | Median % | Std % | Positive % | p25 % | p75 % | Mean ATR | Median ATR | p25 ATR | p75 ATR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | 1 | 248 | -0.0094 | 0.0095 | 0.1754 | 51.2097 | -0.0860 | 0.0761 | -0.0390 | 0.0487 | -0.3825 | 0.3797 |
| ALL | 2 | 248 | -0.0137 | 0.0095 | 0.2020 | 51.6129 | -0.1161 | 0.1080 | -0.0673 | 0.0430 | -0.5892 | 0.5216 |
| ALL | 3 | 247 | -0.0156 | 0.0096 | 0.2766 | 51.4170 | -0.1362 | 0.1206 | -0.0614 | 0.0513 | -0.6347 | 0.6435 |
| ALL | 6 | 240 | -0.0302 | 0.0095 | 0.3582 | 51.2500 | -0.2008 | 0.1764 | -0.1623 | 0.0383 | -0.8640 | 0.7887 |
| ALL | 12 | 234 | -0.0335 | -0.0026 | 0.4538 | 49.1453 | -0.2652 | 0.2186 | -0.1861 | -0.0109 | -1.1931 | 1.0419 |
| BUY | 1 | 135 | -0.0043 | 0.0000 | 0.1294 | 48.1481 | -0.0752 | 0.0577 | -0.0029 | 0.0000 | -0.3460 | 0.3004 |
| BUY | 2 | 135 | -0.0061 | 0.0049 | 0.1635 | 50.3704 | -0.0880 | 0.0916 | -0.0300 | 0.0176 | -0.4645 | 0.4468 |
| BUY | 3 | 134 | -0.0083 | 0.0184 | 0.2188 | 52.9851 | -0.1074 | 0.1114 | -0.0083 | 0.0814 | -0.5330 | 0.5293 |
| BUY | 6 | 129 | -0.0150 | -0.0097 | 0.3036 | 45.7364 | -0.1607 | 0.1425 | -0.0657 | -0.0405 | -0.7913 | 0.6158 |
| BUY | 12 | 129 | -0.0182 | -0.0193 | 0.3735 | 45.7364 | -0.2344 | 0.1572 | -0.1229 | -0.0809 | -1.0811 | 0.7420 |
| SELL | 1 | 113 | -0.0154 | 0.0189 | 0.2186 | 54.8673 | -0.0958 | 0.0956 | -0.0821 | 0.1144 | -0.4313 | 0.4689 |
| SELL | 2 | 113 | -0.0227 | 0.0185 | 0.2405 | 53.0973 | -0.1331 | 0.1260 | -0.1119 | 0.0664 | -0.6484 | 0.6222 |
| SELL | 3 | 113 | -0.0243 | 0.0000 | 0.3333 | 49.5575 | -0.1633 | 0.1398 | -0.1243 | 0.0000 | -0.7582 | 0.7900 |
| SELL | 6 | 111 | -0.0479 | 0.0487 | 0.4134 | 57.6577 | -0.2882 | 0.2166 | -0.2746 | 0.2481 | -1.0876 | 0.9797 |
| SELL | 12 | 105 | -0.0523 | 0.0744 | 0.5377 | 53.3333 | -0.4409 | 0.3241 | -0.2637 | 0.4444 | -1.6658 | 1.4620 |

## MFE / MAE bounds before recorded exit

Confirmed is a lower bound, candle_upper is a loose upper bound. Neither should be represented as exact intrabar extrema. All price/percentage/ATR distributions are retained in JSON.

### confirmed

| Family | Side | Mean MFE ATR | Median MFE ATR | Mean MAE ATR | Median MAE ATR | MFE>=.5 % | >=1 % | >=1.5 % | >=2 % | MAE>=.5 % | >=1 % | >=1.5 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E | ALL | 1.3662 | 1.4133 | 0.9596 | 1.1483 | 77.1739 | 58.6957 | 50.0000 | 35.8696 | 81.5217 | 61.9565 | 0.0000 |
| E | BUY | 1.2859 | 1.1719 | 0.9756 | 1.1577 | 70.4545 | 54.5455 | 47.7273 | 31.8182 | 79.5455 | 65.9091 | 0.0000 |
| E | SELL | 1.4397 | 1.5447 | 0.9450 | 1.1014 | 83.3333 | 62.5000 | 52.0833 | 39.5833 | 83.3333 | 58.3333 | 0.0000 |
| F | ALL | 1.3166 | 1.4712 | 0.9694 | 1.1981 | 71.1268 | 56.3380 | 49.2958 | 38.0282 | 78.8732 | 66.1972 | 0.0000 |
| F | BUY | 1.0759 | 0.8698 | 1.0819 | 1.2418 | 57.5758 | 43.9394 | 40.9091 | 28.7879 | 86.3636 | 80.3030 | 0.0000 |
| F | SELL | 1.5256 | 1.8279 | 0.8717 | 1.0929 | 82.8947 | 67.1053 | 56.5789 | 46.0526 | 72.3684 | 53.9474 | 0.0000 |
| G | ALL | 1.1792 | 1.0843 | 0.9957 | 1.1843 | 67.7419 | 52.4194 | 40.3226 | 33.8710 | 83.4677 | 68.1452 | 0.0000 |
| G | BUY | 1.1412 | 0.9453 | 1.0377 | 1.1915 | 65.9259 | 48.8889 | 36.2963 | 31.1111 | 88.1481 | 70.3704 | 0.0000 |
| G | SELL | 1.2247 | 1.2635 | 0.9456 | 1.1735 | 69.9115 | 56.6372 | 45.1327 | 37.1681 | 77.8761 | 65.4867 | 0.0000 |

### candle_upper

| Family | Side | Mean MFE ATR | Median MFE ATR | Mean MAE ATR | Median MAE ATR | MFE>=.5 % | >=1 % | >=1.5 % | >=2 % | MAE>=.5 % | >=1 % | >=1.5 % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E | ALL | 1.5160 | 1.5307 | 1.2698 | 1.2816 | 77.1739 | 59.7826 | 51.0870 | 36.9565 | 81.5217 | 63.0435 | 32.6087 |
| E | BUY | 1.4208 | 1.1719 | 1.1952 | 1.2973 | 70.4545 | 54.5455 | 47.7273 | 31.8182 | 79.5455 | 65.9091 | 25.0000 |
| E | SELL | 1.6034 | 1.6073 | 1.3382 | 1.2314 | 83.3333 | 64.5833 | 54.1667 | 41.6667 | 83.3333 | 60.4167 | 39.5833 |
| F | ALL | 1.4890 | 1.5166 | 1.2169 | 1.3355 | 73.2394 | 56.3380 | 50.0000 | 38.7324 | 78.8732 | 67.6056 | 35.9155 |
| F | BUY | 1.2024 | 0.9202 | 1.3115 | 1.3991 | 60.6061 | 43.9394 | 40.9091 | 28.7879 | 86.3636 | 80.3030 | 42.4242 |
| F | SELL | 1.7379 | 1.8773 | 1.1347 | 1.1847 | 84.2105 | 67.1053 | 57.8947 | 47.3684 | 72.3684 | 56.5789 | 30.2632 |
| G | ALL | 1.3401 | 1.0889 | 1.3142 | 1.3759 | 69.3548 | 52.8226 | 40.3226 | 33.8710 | 83.4677 | 69.7581 | 37.5000 |
| G | BUY | 1.2764 | 0.9453 | 1.3019 | 1.3818 | 67.4074 | 48.8889 | 36.2963 | 31.1111 | 88.1481 | 72.5926 | 36.2963 |
| G | SELL | 1.4161 | 1.2635 | 1.3289 | 1.3676 | 71.6814 | 57.5221 | 45.1327 | 37.1681 | 77.8761 | 66.3717 | 38.9381 |

## STOP favorable excursion

| Family | Side | Bound | N | Mean ATR | Median ATR | >=.25 ATR % | >=.5 ATR % | >=1 ATR % | >=1.5 ATR % | >=2 ATR % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E | ALL | confirmed | 52 | 0.8119 | 0.6785 | 82.6923 | 59.6154 | 30.7692 | 21.1538 | 1.9231 |
| E | ALL | candle_upper | 52 | 0.8734 | 0.6785 | 86.5385 | 59.6154 | 32.6923 | 23.0769 | 3.8462 |
| E | BUY | confirmed | 26 | 0.7371 | 0.5891 | 73.0769 | 50.0000 | 23.0769 | 19.2308 | 0.0000 |
| E | BUY | candle_upper | 26 | 0.7516 | 0.5891 | 76.9231 | 50.0000 | 23.0769 | 19.2308 | 0.0000 |
| E | SELL | confirmed | 26 | 0.8868 | 0.6785 | 92.3077 | 69.2308 | 38.4615 | 23.0769 | 3.8462 |
| E | SELL | candle_upper | 26 | 0.9952 | 0.6785 | 96.1538 | 69.2308 | 42.3077 | 26.9231 | 7.6923 |
| F | ALL | confirmed | 84 | 0.7313 | 0.5122 | 75.0000 | 51.1905 | 27.3810 | 16.6667 | 3.5714 |
| F | ALL | candle_upper | 84 | 0.7913 | 0.5529 | 82.1429 | 54.7619 | 27.3810 | 17.8571 | 4.7619 |
| F | BUY | confirmed | 47 | 0.6268 | 0.4118 | 63.8298 | 40.4255 | 21.2766 | 17.0213 | 4.2553 |
| F | BUY | candle_upper | 47 | 0.6811 | 0.4211 | 72.3404 | 44.6809 | 21.2766 | 17.0213 | 4.2553 |
| F | SELL | confirmed | 37 | 0.8641 | 0.7913 | 89.1892 | 64.8649 | 35.1351 | 16.2162 | 2.7027 |
| F | SELL | candle_upper | 37 | 0.9313 | 0.7913 | 94.5946 | 67.5676 | 35.1351 | 18.9189 | 5.4054 |
| G | ALL | confirmed | 162 | 0.6663 | 0.5206 | 67.2840 | 51.2346 | 29.0123 | 11.7284 | 3.7037 |
| G | ALL | candle_upper | 162 | 0.7073 | 0.5351 | 72.8395 | 53.7037 | 29.6296 | 11.7284 | 3.7037 |
| G | BUY | confirmed | 94 | 0.7111 | 0.5228 | 71.2766 | 52.1277 | 29.7872 | 11.7021 | 4.2553 |
| G | BUY | candle_upper | 94 | 0.7269 | 0.5306 | 72.3404 | 54.2553 | 29.7872 | 11.7021 | 4.2553 |
| G | SELL | confirmed | 68 | 0.6044 | 0.4958 | 61.7647 | 50.0000 | 27.9412 | 11.7647 | 2.9412 |
| G | SELL | candle_upper | 68 | 0.6803 | 0.5439 | 73.5294 | 52.9412 | 29.4118 | 11.7647 | 2.9412 |

## TARGET adverse excursion

| Family | Side | Bound | N | Mean ATR | Median ATR | >=.25 ATR % | >=.5 ATR % | >=1 ATR % | >=1.5 ATR % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E | ALL | confirmed | 31 | 0.6116 | 0.5738 | 80.6452 | 58.0645 | 16.1290 | 0.0000 |
| E | ALL | candle_upper | 31 | 0.6116 | 0.5738 | 80.6452 | 58.0645 | 16.1290 | 0.0000 |
| E | BUY | confirmed | 13 | 0.6052 | 0.4427 | 76.9231 | 46.1538 | 23.0769 | 0.0000 |
| E | BUY | candle_upper | 13 | 0.6052 | 0.4427 | 76.9231 | 46.1538 | 23.0769 | 0.0000 |
| E | SELL | confirmed | 18 | 0.6162 | 0.6301 | 83.3333 | 66.6667 | 11.1111 | 0.0000 |
| E | SELL | candle_upper | 18 | 0.6162 | 0.6301 | 83.3333 | 66.6667 | 11.1111 | 0.0000 |
| F | ALL | confirmed | 50 | 0.4742 | 0.3319 | 62.0000 | 42.0000 | 16.0000 | 0.0000 |
| F | ALL | candle_upper | 50 | 0.4776 | 0.3319 | 62.0000 | 42.0000 | 16.0000 | 0.0000 |
| F | BUY | confirmed | 17 | 0.5411 | 0.3867 | 70.5882 | 47.0588 | 29.4118 | 0.0000 |
| F | BUY | candle_upper | 17 | 0.5511 | 0.3867 | 70.5882 | 47.0588 | 29.4118 | 0.0000 |
| F | SELL | confirmed | 33 | 0.4398 | 0.3156 | 57.5758 | 39.3939 | 9.0909 | 0.0000 |
| F | SELL | candle_upper | 33 | 0.4398 | 0.3156 | 57.5758 | 39.3939 | 9.0909 | 0.0000 |
| G | ALL | confirmed | 77 | 0.5027 | 0.4573 | 70.1299 | 48.0519 | 7.7922 | 0.0000 |
| G | ALL | candle_upper | 77 | 0.5027 | 0.4573 | 70.1299 | 48.0519 | 7.7922 | 0.0000 |
| G | BUY | confirmed | 38 | 0.5748 | 0.5989 | 78.9474 | 57.8947 | 7.8947 | 0.0000 |
| G | BUY | candle_upper | 38 | 0.5748 | 0.5989 | 78.9474 | 57.8947 | 7.8947 | 0.0000 |
| G | SELL | confirmed | 39 | 0.4325 | 0.3475 | 61.5385 | 38.4615 | 7.6923 | 0.0000 |
| G | SELL | candle_upper | 39 | 0.4325 | 0.3475 | 61.5385 | 38.4615 | 7.6923 | 0.0000 |

## Time to outcome

### bars (bar-start convention)

| Family | Group | N | Mean | Median | p25 | p75 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E | ALL | 92 | 8.3478 | 5.0000 | 3.0000 | 11.0000 | 44.0000 |
| E | STOP_LOSS | 52 | 6.1538 | 4.0000 | 2.0000 | 8.0000 | 25.0000 |
| E | TARGET | 31 | 11.6452 | 10.0000 | 4.0000 | 13.5000 | 44.0000 |
| E | END_OF_SESSION | 9 | 9.6667 | 9.0000 | 3.0000 | 12.0000 | 24.0000 |
| E | BUY | 44 | 8.0455 | 5.5000 | 3.0000 | 12.0000 | 25.0000 |
| E | SELL | 48 | 8.6250 | 5.0000 | 3.0000 | 10.2500 | 44.0000 |
| F | ALL | 142 | 9.3521 | 5.0000 | 2.0000 | 11.0000 | 69.0000 |
| F | STOP_LOSS | 84 | 7.3810 | 4.0000 | 1.0000 | 10.2500 | 46.0000 |
| F | TARGET | 50 | 8.5000 | 7.0000 | 2.2500 | 11.0000 | 37.0000 |
| F | END_OF_SESSION | 8 | 35.3750 | 35.0000 | 9.5000 | 55.0000 | 69.0000 |
| F | BUY | 66 | 6.7424 | 3.0000 | 1.0000 | 8.7500 | 67.0000 |
| F | SELL | 76 | 11.6184 | 8.0000 | 3.0000 | 15.2500 | 69.0000 |
| G | ALL | 248 | 9.2823 | 5.0000 | 2.0000 | 13.0000 | 65.0000 |
| G | STOP_LOSS | 162 | 6.8951 | 4.0000 | 1.0000 | 10.0000 | 47.0000 |
| G | TARGET | 77 | 11.0909 | 8.0000 | 4.0000 | 18.0000 | 33.0000 |
| G | END_OF_SESSION | 9 | 36.7778 | 57.0000 | 4.0000 | 59.0000 | 65.0000 |
| G | BUY | 135 | 9.4519 | 6.0000 | 2.5000 | 14.0000 | 65.0000 |
| G | SELL | 113 | 9.0796 | 4.0000 | 1.0000 | 10.0000 | 59.0000 |

### minutes (bar-start convention)

| Family | Group | N | Mean | Median | p25 | p75 | Max |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E | ALL | 92 | 41.7391 | 25.0000 | 15.0000 | 55.0000 | 220.0000 |
| E | STOP_LOSS | 52 | 30.7692 | 20.0000 | 10.0000 | 40.0000 | 125.0000 |
| E | TARGET | 31 | 58.2258 | 50.0000 | 20.0000 | 67.5000 | 220.0000 |
| E | END_OF_SESSION | 9 | 48.3333 | 45.0000 | 15.0000 | 60.0000 | 120.0000 |
| E | BUY | 44 | 40.2273 | 27.5000 | 15.0000 | 60.0000 | 125.0000 |
| E | SELL | 48 | 43.1250 | 25.0000 | 15.0000 | 51.2500 | 220.0000 |
| F | ALL | 142 | 46.7606 | 25.0000 | 10.0000 | 55.0000 | 345.0000 |
| F | STOP_LOSS | 84 | 36.9048 | 20.0000 | 5.0000 | 51.2500 | 230.0000 |
| F | TARGET | 50 | 42.5000 | 35.0000 | 11.2500 | 55.0000 | 185.0000 |
| F | END_OF_SESSION | 8 | 176.8750 | 175.0000 | 47.5000 | 275.0000 | 345.0000 |
| F | BUY | 66 | 33.7121 | 15.0000 | 5.0000 | 43.7500 | 335.0000 |
| F | SELL | 76 | 58.0921 | 40.0000 | 15.0000 | 76.2500 | 345.0000 |
| G | ALL | 248 | 46.4113 | 25.0000 | 10.0000 | 65.0000 | 325.0000 |
| G | STOP_LOSS | 162 | 34.4753 | 20.0000 | 5.0000 | 50.0000 | 235.0000 |
| G | TARGET | 77 | 55.4545 | 40.0000 | 20.0000 | 90.0000 | 165.0000 |
| G | END_OF_SESSION | 9 | 183.8889 | 285.0000 | 20.0000 | 295.0000 | 325.0000 |
| G | BUY | 135 | 47.2593 | 30.0000 | 12.5000 | 70.0000 | 325.0000 |
| G | SELL | 113 | 45.3982 | 20.0000 | 5.0000 | 50.0000 | 295.0000 |

| Family | Exit | Within1 candle % | Within2 % | Within3 % | Within6 % | Within12 % |
| --- | --- | --- | --- | --- | --- | --- |
| E | STOP_LOSS | 3.8462 | 11.5385 | 26.9231 | 63.4615 | NA |
| E | TARGET | 0.0000 | 3.2258 | 12.9032 | 35.4839 | 67.7419 |
| F | STOP_LOSS | 10.7143 | 32.1429 | 39.2857 | 61.9048 | NA |
| F | TARGET | 4.0000 | 14.0000 | 26.0000 | 46.0000 | 76.0000 |
| G | STOP_LOSS | 20.3704 | 31.4815 | 40.7407 | 60.4938 | NA |
| G | TARGET | 1.2987 | 2.5974 | 12.9870 | 35.0649 | 59.7403 |

## Immediate entry-candle quality

| Family | Side | Favorable N/% | Adverse N/% | BOTH N/% | Neither N/% | Next close mean % | Next close median % |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E | BUY | 1/2.27 | 3/6.82 | 40/90.91 | 0/0.0 | 0.0034 | 0.0048 |
| E | SELL | 2/4.17 | 2/4.17 | 44/91.67 | 0/0.0 | 0.0045 | 0.0098 |
| F | BUY | 0/0.0 | 1/1.52 | 65/98.48 | 0/0.0 | -0.0322 | -0.0482 |
| F | SELL | 7/9.21 | 0/0.0 | 69/90.79 | 0/0.0 | 0.0167 | 0.0000 |
| G | BUY | 2/1.48 | 7/5.19 | 126/93.33 | 0/0.0 | -0.0043 | 0.0000 |
| G | SELL | 8/7.08 | 2/1.77 | 103/91.15 | 0/0.0 | -0.0154 | 0.0189 |

## Stop versus target geometry

| Family | Mean stop price | Mean target price | Mean stop ATR | Mean target ATR | Mean RR |
| --- | --- | --- | --- | --- | --- |
| E | 3.1014 | 4.1352 | 1.5000 | 2.0000 | 1.3333 |
| F | 3.6136 | 4.8181 | 1.5000 | 2.0000 | 1.3333 |
| G | 3.4662 | 4.6216 | 1.5000 | 2.0000 | 1.3333 |

| Family | Reference | P target first % | P stop first % | Neither/censored % | Ambiguous collisions |
| --- | --- | --- | --- | --- | --- |
| E | slipped_entry | 33.6957 | 56.5217 | 9.7826 | 1 |
| E | raw_open | 35.8696 | 32.6087 | 31.5217 | 1 |
| F | slipped_entry | 35.2113 | 59.1549 | 5.6338 | 1 |
| F | raw_open | 38.0282 | 35.2113 | 26.7606 | 1 |
| G | slipped_entry | 31.0484 | 65.3226 | 3.6290 | 0 |
| G | raw_open | 33.8710 | 35.0806 | 31.0484 | 0 |

Slipped-entry rows reproduce actual engine thresholds and exits. Raw-open rows above are full exit-candle proxies and can include post-exit range; do not interpret them as exact pre-exit probabilities. The conservative confirmed-path counts below establish reaches using prior candles and known exit open/fill only. NEITHER is censored/unresolved, not proof a threshold would never be hit. No path is extended beyond recorded exit.

| Family | N | Confirmed target-first N / % | Confirmed stop-first N / % | Unresolved/neither N / % |
| --- | --- | --- | --- | --- |
| E | 92 | 33 / 35.8696 | 0 / 0.0 | 59 / 64.1304 |
| F | 142 | 54 / 38.0282 | 0 / 0.0 | 88 / 61.9718 |
| G | 248 | 84 / 33.871 | 0 / 0.0 | 164 / 66.129 |

## Cost attribution

| Metric (INR unless ratio) | E | F | G |
| --- | --- | --- | --- |
| raw_price_pnl | 4629.7569 | 5132.5468 | -11499.3130 |
| slippage_drag | 26614.8248 | 34769.4255 | 41791.1554 |
| gross_pnl | -21985.0678 | -29636.8787 | -53290.4684 |
| brokerage | 3680.0000 | 5680.0000 | 9920.0000 |
| stt | 6650.9578 | 8688.6514 | 10441.1283 |
| stamp_duty | 798.7745 | 1043.5273 | 1254.5341 |
| transaction_charges | 1634.0969 | 2134.7731 | 2565.8935 |
| sebi_charges | 53.2296 | 69.5388 | 83.5823 |
| ipft | 0.0532 | 0.0695 | 0.0836 |
| gst | 966.1284 | 1419.1887 | 2262.5207 |
| charges | 13783.2404 | 19035.7489 | 26527.7425 |
| pnl | -35768.3083 | -48672.6276 | -79818.2109 |
| gross_turnover | 53229647.2064 | 69538848.4420 | 83582316.5887 |
| charges_over_turnover | 0.0003 | 0.0003 | 0.0003 |
| charges_over_absolute_gross | 0.6269 | 0.6423 | 0.4978 |
| average_charge | 149.8178 | 134.0546 | 106.9667 |
| gross_average | -238.9681 | -208.7104 | -214.8809 |
| net_average | -388.7860 | -342.7650 | -321.8476 |

| Family | Mean combined cost ATR | Median combined cost ATR |
| --- | --- | --- |
| E | 0.8276 | 0.8132 |
| F | 0.7575 | 0.7249 |
| G | 0.8606 | 0.8306 |

Cost ratios above are fractions, not percentages. Slippage attribution is exact on saved fixed trades; no alternative execution assumptions or strategy reruns. Raw-price pnl is not a zero-slippage backtest.

## Entry edge before exits

| Family | Side | Positive mean H | Positive median H | Positive-frequency >50% H | All horizon means positive? |
| --- | --- | --- | --- | --- | --- |
| E | BUY | 1,2,3,12 | 1,2,3 | 1,2,3 | False |
| E | SELL | 1,2,12 | 1,2,3,12 | 1,2,3,12 | False |
| F | BUY | none | none | none | False |
| F | SELL | 1,2,3,6,12 | 2,3,6,12 | 2,3,6,12 | True |
| G | BUY | none | 2,3 | 2,3 | False |
| G | SELL | none | 1,2,6,12 | 1,2,6,12 | False |

Positive descriptive means exist, most clearly F SELL (all five means positive; 12-bar 67.61% positive). F BUY has negative means/medians at every horizon. G both-side means are negative at every horizon. E changes sign. No independent or economically sufficient alpha established. Positive magnitudes are small relative to measured actual round-trip costs; forward horizons are descriptive, not new exit rules or tradable strategies. ATR means can differ in sign from percent means due to volatility weighting.

## Winner versus loser signal characteristics

| Family | Outcome | Field | N | Mean | Median | p25 | p75 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E | WINNER | RSI | 33 | 51.1627 | 50.0000 | 46.8468 | 55.2419 |
| E | WINNER | ATR | 33 | 2.0530 | 2.0571 | 1.5571 | 2.4643 |
| E | WINNER | atr_close_pct | 33 | 0.1974 | 0.1923 | 0.1522 | 0.2466 |
| E | WINNER | vwap_distance_price | 33 | 0.0026 | -0.1209 | -1.3305 | 1.3623 |
| E | WINNER | time_minutes | 33 | 750.0000 | 770.0000 | 670.0000 | 840.0000 |
| E | WINNER | ema20_distance_price | 33 | 0.0402 | 0.0402 | -0.1965 | 0.2767 |
| E | WINNER | ema50_distance_price | 33 | -0.2023 | -0.1933 | -1.0853 | 1.1138 |
| E | WINNER | ema20_ema50_spread | 33 | -0.2425 | -0.2336 | -1.4212 | 1.3102 |
| E | LOSER | RSI | 59 | 50.5718 | 50.0000 | 46.6667 | 54.9027 |
| E | LOSER | ATR | 59 | 2.0758 | 1.9107 | 1.5482 | 2.4750 |
| E | LOSER | atr_close_pct | 59 | 0.2027 | 0.1856 | 0.1507 | 0.2458 |
| E | LOSER | vwap_distance_price | 59 | -0.5975 | 0.0000 | -2.4506 | 0.7021 |
| E | LOSER | time_minutes | 59 | 792.4576 | 800.0000 | 747.5000 | 857.5000 |
| E | LOSER | ema20_distance_price | 59 | -0.0082 | 0.0258 | -0.2837 | 0.3253 |
| E | LOSER | ema50_distance_price | 59 | -0.6509 | -0.3317 | -2.2017 | 0.8508 |
| E | LOSER | ema20_ema50_spread | 59 | -0.6426 | -0.5175 | -2.7747 | 1.3586 |
| F | WINNER | RSI | 53 | 43.7470 | 35.4298 | 24.2775 | 67.4312 |
| F | WINNER | ATR | 53 | 2.3285 | 2.1857 | 1.7429 | 2.7000 |
| F | WINNER | atr_close_pct | 53 | 0.2243 | 0.2140 | 0.1676 | 0.2565 |
| F | WINNER | vwap_distance_price | 53 | -0.3652 | -2.7810 | -4.4783 | 4.7095 |
| F | WINNER | time_minutes | 53 | 700.2830 | 690.0000 | 645.0000 | 760.0000 |
| F | WINNER | volume_ratio | 53 | 1.8992 | 1.4798 | 1.2208 | 2.0303 |
| F | WINNER | opening_range_distance_price | 53 | 1.8821 | 1.5000 | 0.7000 | 2.6000 |
| F | LOSER | RSI | 89 | 53.3493 | 61.5108 | 32.5137 | 75.9615 |
| F | LOSER | ATR | 89 | 2.4570 | 2.2214 | 1.7929 | 2.9500 |
| F | LOSER | atr_close_pct | 89 | 0.2382 | 0.2188 | 0.1744 | 0.2829 |
| F | LOSER | vwap_distance_price | 89 | 0.4910 | 2.2152 | -3.6988 | 4.4164 |
| F | LOSER | time_minutes | 89 | 681.7978 | 660.0000 | 615.0000 | 735.0000 |
| F | LOSER | volume_ratio | 89 | 1.9118 | 1.6369 | 1.3213 | 2.2299 |
| F | LOSER | opening_range_distance_price | 89 | 2.2860 | 1.9000 | 0.8000 | 3.3000 |
| G | WINNER | RSI | 78 | 49.9325 | 65.3964 | 30.3867 | 69.3791 |
| G | WINNER | ATR | 78 | 2.4312 | 2.2911 | 1.8580 | 2.7179 |
| G | WINNER | atr_close_pct | 78 | 0.2345 | 0.2158 | 0.1745 | 0.2626 |
| G | WINNER | vwap_distance_price | 78 | 0.0393 | 1.6439 | -3.4808 | 3.6379 |
| G | WINNER | time_minutes | 78 | 686.8590 | 650.0000 | 625.0000 | 757.5000 |
| G | WINNER | ema20_distance_price | 78 | 0.6565 | 0.9870 | -2.5295 | 3.9750 |
| G | LOSER | RSI | 170 | 47.0564 | 33.8962 | 29.0543 | 68.4211 |
| G | LOSER | ATR | 170 | 2.2555 | 2.0375 | 1.6446 | 2.5821 |
| G | LOSER | atr_close_pct | 170 | 0.2182 | 0.2001 | 0.1599 | 0.2512 |
| G | LOSER | vwap_distance_price | 170 | -0.5063 | -2.1195 | -3.3069 | 3.0700 |
| G | LOSER | time_minutes | 170 | 706.9118 | 692.5000 | 630.0000 | 775.0000 |
| G | LOSER | ema20_distance_price | 170 | -0.2263 | -1.1570 | -3.1492 | 3.6615 |

Winners versus losers have median signal ATR E 2.057/1.911, F 2.186/2.221, G 2.291/2.038. E median signal times are 12:50/13:20; F 11:30/11:00; G 10:50/11:32:30. F/G pooled RSI differences strongly mix BUY and SELL, so they do not establish an RSI effect. These are outcome-conditioned descriptions, not threshold discovery. Side-specific descriptive distributions are also in JSON to expose direction mixing; no indicator or value is proposed as a filter.

## Time of day

| Family | Bucket | N | Gross INR | Net INR | Gross PF | Win % | Avg net INR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E | 09:30-10:29 | 3 | 2713.8898 | 2334.5471 | NA | 100.0000 | 778.1824 |
| E | 10:30-11:29 | 7 | 1006.4928 | 42.9971 | 1.3534 | 57.1429 | 6.1424 |
| E | 11:30-12:29 | 13 | -629.2949 | -2519.1936 | 0.9034 | 46.1538 | -193.7841 |
| E | 12:30-13:29 | 26 | -13427.8947 | -17430.0507 | 0.2905 | 23.0769 | -670.3866 |
| E | 13:30-14:29 | 22 | -5759.4973 | -9188.1904 | 0.5426 | 31.8182 | -417.6450 |
| E | 14:30-final | 17 | -5695.8596 | -8326.1199 | 0.3924 | 29.4118 | -489.7718 |
| E | OUTSIDE_PREDEFINED | 4 | -192.9040 | -682.2980 | 0.8997 | 50.0000 | -170.5745 |
| F | 09:30-10:29 | 36 | -14380.6981 | -18236.3183 | 0.3358 | 27.7778 | -506.5644 |
| F | 10:30-11:29 | 49 | -14953.1680 | -21803.7067 | 0.4954 | 32.6531 | -444.9736 |
| F | 11:30-12:29 | 21 | 1214.8865 | -1844.3395 | 1.1414 | 52.3810 | -87.8257 |
| F | 12:30-13:29 | 12 | 3166.7783 | 1481.3905 | 1.8256 | 58.3333 | 123.4492 |
| F | 13:30-14:29 | 15 | 670.8609 | -1531.3195 | 1.0983 | 53.3333 | -102.0880 |
| F | 14:30-final | 9 | -5355.5383 | -6738.3342 | 0.0946 | 11.1111 | -748.7038 |
| F | OUTSIDE_PREDEFINED | 0 | 0 | 0 | NA | NA | NA |
| G | 09:30-10:29 | 49 | -5129.1019 | -9309.4547 | 0.6793 | 38.7755 | -189.9889 |
| G | 10:30-11:29 | 71 | -12302.4618 | -19888.2816 | 0.5772 | 35.2113 | -280.1166 |
| G | 11:30-12:29 | 41 | -12606.3258 | -17404.6728 | 0.3603 | 26.8293 | -424.5042 |
| G | 12:30-13:29 | 46 | -16887.0638 | -22157.7947 | 0.2691 | 23.9130 | -481.6912 |
| G | 13:30-14:29 | 26 | -4041.5769 | -7107.3964 | 0.5714 | 38.4615 | -273.3614 |
| G | 14:30-final | 13 | -1442.2757 | -2900.0445 | 0.5961 | 15.3846 | -223.0803 |
| G | OUTSIDE_PREDEFINED | 2 | -881.6626 | -1050.5663 | 0.0000 | 0.0000 | -525.2831 |

Losses concentrate differently: E12:30-13:29 ~48.7% of net loss; F first two buckets ~82.3%; G11:30-13:29 ~49.6%. Sparse positive E/F buckets do not show a shared time-of-day remedy or causal explanation.

## Volatility tertiles

{'cuts_atr_close_pct': [0.17888619951627666, 0.23602136245890518], 'method': 'Pooled 482 trades; linear quantiles 1/3 and 2/3, ties <= cut go lower', 'counts': {'LOW': 161, 'MID': 160, 'HIGH': 161}}

| Family | Bucket | N | Gross INR | Net INR | Gross PF | Win % | Avg net INR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E | LOW | 40 | -9179.0186 | -16007.1311 | 0.5682 | 37.5000 | -400.1783 |
| E | MID | 25 | -7356.1051 | -10989.1955 | 0.5227 | 32.0000 | -439.5678 |
| E | HIGH | 27 | -5449.9441 | -8771.9817 | 0.6487 | 37.0370 | -324.8882 |
| F | LOW | 38 | -8630.2193 | -14696.6107 | 0.5365 | 39.4737 | -386.7529 |
| F | MID | 50 | -6829.7392 | -13760.7066 | 0.7386 | 40.0000 | -275.2141 |
| F | HIGH | 54 | -14176.9202 | -20215.3103 | 0.5529 | 33.3333 | -374.3576 |
| G | LOW | 83 | -22293.1725 | -31817.1067 | 0.2952 | 24.0964 | -383.3386 |
| G | MID | 85 | -12242.1247 | -21429.9409 | 0.6082 | 34.1176 | -252.1170 |
| G | HIGH | 80 | -18755.1712 | -26571.1633 | 0.5181 | 36.2500 | -332.1395 |

All nine family-by-tertile groups are gross and net negative. G LOW is particularly weak, but no common profitable regime or large-share causal explanation is established.

## LEGACY / CAS

| Family | Regime | N | 3bar N | 3bar mean % | 3bar median % | 6bar N | 6bar mean % | 6bar median % | Median MFE ATR lower | Median MAE ATR lower | STOP % | TARGET % | Gross INR | Net INR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E | LEGACY | 74 | 74 | 0.0034 | 0.0202 | 69 | -0.0491 | -0.0422 | 1.2584 | 1.1690 | 59.4595 | 32.4324 | -20947.2741 | -31938.8857 |
| E | CAS | 18 | 18 | 0.0102 | 0.0096 | 16 | 0.0413 | 0.0573 | 1.8834 | 1.0274 | 44.4444 | 38.8889 | -1037.7938 | -3829.4226 |
| F | LEGACY | 112 | 112 | 0.0096 | 0.0094 | 111 | 0.0071 | -0.0099 | 1.4712 | 1.2176 | 58.0357 | 36.6071 | -22267.9544 | -37459.9775 |
| F | CAS | 30 | 30 | -0.0179 | -0.0189 | 29 | -0.0266 | -0.0096 | 1.2536 | 1.1410 | 63.3333 | 30.0000 | -7368.9243 | -11212.6501 |
| G | LEGACY | 193 | 193 | -0.0186 | 0.0140 | 188 | -0.0377 | 0.0024 | 1.0590 | 1.2031 | 67.3575 | 29.0155 | -49699.7870 | -71791.2474 |
| G | CAS | 55 | 54 | -0.0049 | 0.0000 | 52 | -0.0032 | 0.0484 | 1.2556 | 1.0999 | 58.1818 | 38.1818 | -3590.6814 | -8026.9635 |

E/G CAS per-trade losses and PF improve; F worsens. All six legacy/CAS gross and net results remain negative. Small and chronological/confounded samples; no common material structural improvement established.

## Failure classifications

**E: MIXED_FAILURE.** Weak/sign-changing forward edge plus reversal after modest initial movement and material costs. >=0.5 ATR before stop 59.62%, >=1.5 only21.15%; raw-open mean ATR at 3/6/12 bars 0.029/-0.093/0.176 vs 0.828 ATR average costs. No geometry mismatch demonstrated.

**F: MIXED_FAILURE.** Direction contrast (BUY wrong-direction descriptively; SELL small positive means), pooled weak entry edge, and material costs. SELL12-bar mean0.252 ATR vs pooled average cost0.758 ATR. Both realized sides negative; no direction removal or tuning.

**G: ENTRY_EDGE_WEAK.** Both sides negative mean returns at every horizon; pooled ATR means -0.039,-0.067,-0.061,-0.162,-0.186. Medians/frequencies are mixed, so systematic wrong direction is not claimed. Costs amplify already negative raw-price accounting; modest stop reversals coexist.

## Cross-family common failure

**shared_failure:** Weak directional expectancy relative to execution friction; frequent modest favorable excursions are not sustained into sufficient realized reward.

**directional_alpha:** Positive descriptive means exist, most clearly F SELL (all five means positive; 12-bar 67.61% positive). F BUY has negative means/medians at every horizon. G both-side means are negative at every horizon. E changes sign. No independent or economically sufficient alpha established.

**stops:** Confirmed >=0.5 ATR before STOP: E59.62%, F51.19%, G51.23%; >=1 ATR only 30.77%,27.38%,29.01%. Within first candle: 3.85%,10.71%,20.37%. Many modest reversals, not predominantly immediate failures; substantial reversals are a minority.

**targets:** Actual target rates 33.70%,35.21%,31.05%; median confirmed MFE 1.41,1.47,1.08 ATR. Targets are not impossible, but target reach is insufficient. Censoring and weak forward means prevent concluding target/stop geometry is the root cause.

**costs:** Costs are a primary arithmetic contributor, not a small secondary effect: combined slippage+fees about 0.83,0.76,0.86 ATR/trade. Explicit fees are an additional loss after negative saved gross. Foundational entry edge is weak; COST_DRAG_DOMINANT is not assigned solely from fixed-path raw-price accounting.

**buy_sell:** BUY is worse in realized gross PF and average net trade for all three. SELL remains net-negative. Forward SELL superiority is not consistent: G SELL mean directional returns are worse than BUY at all horizons; E mixed. F has strongest direction-specific descriptive contrast.

**time:** Losses concentrate differently: E12:30-13:29 ~48.7% of net loss; F first two buckets ~82.3%; G11:30-13:29 ~49.6%. Sparse positive E/F buckets do not show a shared time-of-day remedy or causal explanation.

**volatility:** All nine family-by-tertile groups are gross and net negative. G LOW is particularly weak, but no common profitable regime or large-share causal explanation is established.

**cas:** E/G CAS per-trade losses and PF improve; F worsens. All six legacy/CAS gross and net results remain negative. Small and chronological/confounded samples; no common material structural improvement established.

## Correctness, leakage and safety audit

482/482 saved events audited; 0 violations. Signal/event timestamps, physical N+1 open, same session, horizon indexing, signal ATR against unchanged causal ATR14, regular timestamps, cutoffs, no CAS auxiliary input, mirrored direction, saved exit/index reproduction and slippage reconciliation passed. Future bars are used only in measurements; no signal is regenerated or mutated. Existing frozen sources and Phase15 JSON retained. Research network attempts=0; no SmartAPI/broker/live imports, HistoricalClient activity, AngelOneBroker instantiation or real auth/account/profile/order calls. Regression probes/stubs are separately documented in methodology.

## Limitations and future hypotheses

- Single instrument and 125 represented sessions; non-independent, overlapping forward windows and many descriptive comparisons. Positive sample means are not established directional alpha or tradability.

- Exit-conditioned excursions are censored and subject to exit-bar sequence ambiguity. Target-trade small MAE is also a consequence of stop selection; it cannot justify a different stop.

- Horizon availability changes near session end; 12-bar groups differ from 1-bar groups. No overnight carrying or imputation.

- Actual intrabar timestamps are unavailable. Duration minutes are bar-start differences with a five-minute interval, not exact fill times.

- CAS is only 27 sessions and occurs later chronologically; capital/quantity also decline. Regime pnl differences are not causal effects.

- Costs dominate the accounting bridge but gross after slippage is already negative. Positive raw-price accounting for E/F does not establish a profitable no-slippage strategy because actual exit levels and trade selection depended on slipped entries.

- No optimized thresholds, alternative rules or versions tested; every bad bucket and losing observation remains included.

- A future preregistered entry hypothesis must demonstrate directional magnitude relative to unchanged execution costs on independent data.

- F direction asymmetry and modest pre-stop favorable movement may be recorded as observations for that future protocol; no rule, parameter or filter is proposed.

## Validation and artifacts

Baseline: 341 passed, 0 failed; 79 Python files compiled; diff check PASS. Final regression: 356 passed, 0 failed in 10.66s (15 new Phase16 tests). Compile: all 82 project Python files PASS, excluding venv/.venv/site-packages/.git. Final git diff --check PASS. All 92 frozen source files and canonical Phase15 JSON remain unchanged. No commit.

Git status retains pre-existing modifications to broker/angelone.py, config/settings.py and live/live_feed.py, and pre-existing untracked broker/data/research/tests files. Phase16 adds only its two research modules, report, JSON, and tests/test_phase16_forensics.py. The untracked research directory appears as a single Git status entry. No production or engine modifications were made during Phase16.

Report: `research/phase16_report.md`. JSON: `research/phase16_results.json`, including all 482 event diagnostics and all outcome/side distributions. No duplicate CSV created. Research code: `research/phase16_forensics.py` and `research/phase16_report_builder.py`; tests: `tests/test_phase16_forensics.py`. No commit.

## Phase 17 decision

**A — NEW ENTRY HYPOTHESIS REQUIRED.** Across families the fixed-horizon directional magnitudes are weak relative to measured friction; G lacks mean edge and E is unstable. F SELL is a descriptive pocket but insufficient to choose direction removal or exit redesign. No robust positive pre-exit expectancy supports prioritizing stop/target research.
