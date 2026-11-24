# UI/UX Design Skill (MVP)

文書（Markdown / 仕様書 / スライド）および Webサイト・Webアプリの UI/UX デザイン品質を向上させるための AI スキルパッケージです。  
Claude Code、Antigravity、その他カスタムインストラクション／スキル対応エージェントでそのまま利用できます。

## アーキテクチャの特徴

1. **3層分離**:
   - **Layer 1: 戦術 (`tactics/`)** — 生成時に適用する具体的なルール・パターン
   - **Layer 2: 原則・評価 (`evaluation/`)** — Phase 3 の自己評価時のみロードし、証拠義務付きで批評
   - **Layer 3: 機械判定 (`scripts/ui_ux_checker.py`)** — コントラスト比・見出し階層・属性・トークン逸脱などを LLM の印象ではなく決定論的に検査
2. **権威順序（Conflict Resolution）**:
   `法令・WCAG 2.2 AA > ユーザー明示要件・既存デザインシステム > 6原則 > 個別テクニック`
3. **3区分判定と証拠義務**:
   すべての評価項目を「機械判定」「LLM原則判断」「未検証（コードのみでは判定不可）」に分け、根拠（セレクタ・行番号・CSS値）のない合格／指摘を禁止します。
4. **生成と既存物レビューの明確な分離**:
   既存物レビュー時は勝手に全面リデザインせず、まず診断レポートを提示します。

## ディレクトリ構成

```text
ui-ux-design-skill/
├── SKILL.md                         # スキル本体（ルーター・権威順序・実行フロー）
├── tokens/
│   └── design-tokens.json           # 4/8pxスケール & WCAG 2.2 AA検証済みカラーペア
├── tactics/
│   ├── mod-doc.md                   # 文書・Markdown・日本語組版（DADS準拠）
│   ├── mod-visual-a11y.md           # 視覚階層・余白・色・WCAG 2.2・ダークモード
│   ├── mod-interaction-forms.md     # ボタン階層・フォーム・5状態・ダークパターン回避
│   ├── mod-slide.md                 # プレゼンスライド設計
│   └── mod-pro-ai.md                # 業務高密度UI・テーブル・AIチャットUI
├── evaluation/
│   ├── blockers.md                  # Blocker具体欠陥リスト (B-01〜B-07) & 重大度定義
│   ├── checklist-web.md             # Web/UI用 3区分チェックリスト
│   └── checklist-doc.md             # 文書/スライド用 3区分チェックリスト
├── scripts/
│   └── ui_ux_checker.py             # 依存ゼロ（Python標準ライブラリ）機械判定チェッカー
└── tests/
    ├── run_tests.py                 # 検出率＆誤検知テスト
    └── fixtures/                    # 埋め込み欠陥サンプル & クリーン参照サンプル
```

## クイックスタート

### 1. スキルとして配置する
- **Claude Code / 互換環境**: `.claude/skills/ui-ux-design/`（またはプロジェクトのスキルディレクトリ）にこのフォルダごと配置してください。
- **その他エージェント**: `SKILL.md` をエントリポイントとして参照させてください。

### 2. 機械判定チェッカーを実行する（Python 3.9+、外部ライブラリ不要）
```bash
# HTML / CSS / Markdown を検査
python3 scripts/ui_ux_checker.py path/to/target.html

# JSON形式で出力（AIエージェント連携用）
python3 scripts/ui_ux_checker.py path/to/target.html --json

# デザイントークンのコントラスト比ペア自体を検証
python3 scripts/ui_ux_checker.py --check-tokens tokens/design-tokens.json
```

### 3. テストスイートを実行する
```bash
python3 tests/run_tests.py
```

## ライセンス
MIT License（用途に合わせて自由に変更してください）
