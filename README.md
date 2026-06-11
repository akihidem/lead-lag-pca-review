# lead-lag-pca-review

**日米セクター lead-lag × subspace-regularized PCA の独立再現・検証**
*Independent replication of a US–Japan sector lead-lag strategy built on subspace-regularized PCA.*

Nakagawa, Takemoto, Kubo, Kato (2026, JSAI SIG) の戦略と、SmartScope による再現記事を、
**独立に再実装して検証**したリポジトリ。米国11セクターETF→日本TOPIX-17セクターの
overnight lead-lag を、subspace-regularized PCA で低ランク予測する戦略を対象とする。

## 要旨

- **gross は再現できる**：執行可能な intraday（寄り→引け）の gross Sharpe ≈ **2.0**（論文 reg PCA 2.22 とほぼ一致）。
- **派手な close-to-close の数字の 62% は捕れない夜間ギャップ**。シグナル（米国終値）は前日 JP 引け後に届くため、引け→引けで建てるのは構造的に**ルックアヘッド**。唯一執行できるのは intraday。
- 唯一執行可能な intraday を**正直なコスト（毎日フル往復 = slip×2）**で評価すると **2bp で Sharpe≈0**。
- **流動的な器が無い**：¥100M/日超の TOPIX-17 ETF は 2024-25 で **0/17**。流動的な上位4本に絞ると gross が 2.01→0.76 に崩壊。17セクター先物も日本に実質非存在 → **構造的に運用不可**。
- 正則化は中程度（w≈0.5）なら plain PCA を改善する逆U字だが、**論文採用の w=0.90 は過剰収縮**で plain を下回る。
- 総じて、**結論は原著者自身の "not live-tradeable" と整合**する。本リポジトリはその境界を分解・定量化したもの。

詳細レポートは **[FINDINGS.md](FINDINGS.md)**。

## 検証項目

| # | 検証 | スクリプト |
|---|---|---|
| 1 | momentum / plain PCA / reg PCA の再現 | `src/leadlag.py` |
| 2 | コスト感応度 | `src/leadlag.py` / `src/extras.py` |
| 3 | 夜間ギャップ vs intraday の分解（執行可能性） | `src/extras.py` |
| 4 | リバランス頻度スイープ | `src/leadlag.py` |
| 5 | OOS・レジーム分割 | `src/leadlag.py` / `src/extras.py` |
| 6 | 流動性で絞ると崩壊するか | `src/liquidity.py` |
| 7 | prior weight (w_reg) スイープ | `src/regsweep.py` |

## 再現

```bash
python3 -m venv .venv && .venv/bin/pip install pandas yfinance matplotlib
.venv/bin/python src/download.py    # 米11 + 日17 セクターETF OHLC (yfinance) -> data/raw/
.venv/bin/python src/leadlag.py     # 検証(1)-(5)            -> out/results.json
.venv/bin/python src/extras.py      # 正直な執行版 + 図      -> out/results_honest.json, out/equity.png
.venv/bin/python src/liquidity.py   # 流動性検証(6)          -> out/results_liquidity.json
.venv/bin/python src/regsweep.py    # prior weight スイープ(7) -> out/results_regsweep.json
```

データ期間 2019-2025、米11セクターETF（XLB…XLY）＋日 TOPIX-17 ETF（1617.T…1633.T）、日次OHLC。

## 出典・謝辞

- Nakagawa, K., Takemoto, Y., Kubo, K., Kato, M. (2026). *Investment Strategy Exploiting US-Japan Sector Lead-Lag Relationship Using Subspace-Regularized PCA*. JSAI SIG Technical Report.
- SmartScope による独立再現記事。

本リポジトリは原著者の貢献を尊重した上での **independent replication** であり、批判ではなく
「どこまでが本物で、どこで運用境界に当たるか」を実データで切り分けることを目的とする。
forward-looking なタイミング整合・正直なコスト・流動性制約まで踏み込んだ点が原実装との差分。

## ライセンス

コードは [MIT](LICENSE)。市場データは研究・再現目的で Yahoo Finance（yfinance 経由）から取得。
