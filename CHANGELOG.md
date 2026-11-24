# Changelog

## [1.2.0] - 2026-11-25
### Added
- **ID名前空間の完全分離**: Blocker (`BLK-*`), 共通原則 (`PRN-*`), 文書 (`DOC-*`), 視覚・A11y (`VIS-*`), 操作・フォーム (`INT-*`), スライド (`SLD-*`), 業務UI (`PRO-*`), AI UI (`AI-*`), 機械判定 (`CHK-*`), 未検証 (`UNV-*`) に統一し欠番を解消。
- **トークンCSS実体 (`tokens/design-tokens.css`)**: `prefers-color-scheme: dark` と `[data-theme="dark"]` 両対応のCSS変数を同梱。`border-input`, `focus-ring`, `success-bg`, `on-success` を追加し、44ペアの全数コントラスト比を事前計算・検証。
- **チェッカーのカバレッジ報告 (`coverage`)**: 評価済みペア数・スキップ理由をJSON出力に追加。テーマ別CSS変数スコープ、`rgba()`/`hsl()`/8桁hex、外部CSS相対パス読み込み、`min-width`/`min-height`、アクセシブルネーム欠落、キーボードハンドラ欠如を検出対応。
- **監査可能性と出典整備**: `review-log.md` への証跡保存規定、`REFERENCES.md`（一次資料URL・確認日）、`LICENSE` を同梱。
- **テスト拡充 (`unittest`)**: 敵対的エッジケース、行番号精度、参照整合性チェック、JSON↔CSS一致検証、自己文書適用テストを追加。

### Changed
- `SKILL.md` 本体へ6原則（`PRN-1`〜`PRN-6`）の1行定義を配置し、既存DS探索手順と衝突調停パターン3種を追加。
- 壁テキスト判定（`CHK-D2`）を Blocker から Major へ較正し、`--doc-type spec` および英語文書（単語数ベース）に対応。
- 最終出力サマリーを「機械判定の対象範囲内では Blocker 0件（評価 X/Y ペア、スキップ Z 件）」へ改訂。
- `tactics/` の細部修正（和文約物の全角維持、GOV.UKフォームの通常時/エラー時併記、WCAG 2.2 SC 2.4.11 とモーダルAPG追記、スライドをMarkdown/Marp構成案向けと明記）。

### Fixed
- CSS 2つ目以降のルールの行番号1行ずれバグを修正。
- `:focus:not(:focus-visible) { outline: none }` 等の現代的パターンに対する偽陽性、および `border: 0` / `box-shadow: transparent` による偽陰性を修正。
- Markdown の `~~~` フェンス、水平線 `***`、インラインコード内言及での偽陽性を修正。

## [1.1.0] - 2026-11-24
- 「良い作り方」ベースの戦術書き換えと Good Pattern コードスニペット追加。
- CSS変数解決・単体 `.css` 検査・`--strict-tokens` 対応。

## [1.0.0] - 2026-11-24
- 初回 MVP リリース（3層分離・直交ルーター・証拠義務・自己評価ループ）。
