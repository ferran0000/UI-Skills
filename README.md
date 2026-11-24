# UI/UX Design Skill (v1.2)

AI に「Webサイトを作って」「資料やドキュメントをまとめて」と頼んだとき、**見た目が整っていて、読みやすく、操作しやすいアウトプットを自動で出してくれるようにする AI スキル**です。

専門的なデザインの知識がなくても、AI 側がプロのガイドラインに沿って作成・自己チェックまで行ってくれます。

## これを入れると何が便利？

- **「読みにくい・使いにくい」を自動で防ぐ**: 文字が薄くて読めない、スマホでボタンが押しにくい、長文がベタ打ちで見づらい……といった、AI がやりがちなデザインミスを自動で直してから出力します。
- **Webサイトも、普段の文書も両方カバー**: HTML/CSS の画面づくりはもちろん、Markdown の仕様書・解説記事・スライド構成案（Marp 等）まで、用途に合わせてルールを切り替えてくれます。
- **既存サイトや文書の「ダメ出し＆改善」もできる**: すでに作った画面や文章を渡せば、勝手に全部書き換えるのではなく「どこを直すべきか」の診断レポートを先に出してくれます。
- **AI の「根拠のない大丈夫」を防ぐ**: 色の見やすさ（コントラスト比）や見出し構造などは同梱のチェッカーで自動検査し、コードだけでは確認できない部分は「未検証」と正直に教えてくれます。

## 一番ラクな導入方法

難しい設定は不要です。お使いの AI エージェント（Claude Code やスキル対応エージェント等）のチャットに、以下をそのまま投げるだけで OK です。

> 導入は AI のチャットに **`https://github.com/ferran0000/UI-Skills これ追加して`** と投げちゃってください。

導入後は、普段どおり「お問い合わせフォームを作って」「この手順書を読みやすく整えて」「この HTML の UI をレビューして」と話しかけるだけでスキルが働きます。

---

## 開発者・上級者向けの詳細情報

### 手動で配置する場合

リポジトリをクローンまたは ZIP 解凍し、スキルディレクトリへ配置してください。

```bash
git clone https://github.com/ferran0000/UI-Skills.git
cp -r UI-Skills .claude/skills/ui-ux-design
```

### 主な技術的特徴（v1.2）

- **3層分離アーキテクチャ**: 生成時の戦術（`tactics/`）、評価フェーズでのみ遅延ロードする原則・チェックリスト（`evaluation/`）、決定論的な機械判定（`scripts/ui_ux_checker.py`）を分離。
- **一貫した名前空間ID**: `BLK-*`（Blocker）、`PRN-*`（共通6原則）、`DOC-*`/`VIS-*`/`INT-*`/`SLD-*`/`PRO-*`/`AI-*`（戦術）、`CHK-*`（機械判定）、`UNV-*`（未検証）を分離し、参照整合性をテストで保証。
- **カバレッジ明示付きチェッカー**: 評価済み色ペア数とスキップ理由（`coverage`）を JSON 出力。テーマ別 CSS 変数スコープ（Light / Dark）、`rgba()` アルファ合成、`hsl()`、8桁 hex、ローカル外部 CSS の読み込みに対応。
- **検証済みトークン同梱**: `tokens/design-tokens.css` と `.json` に、WCAG 2.2 AA を満たす Light / Dark 計 44 ペアを事前計算・同梱。

### ディレクトリ構成

```text
ui-ux-design-skill/
├── SKILL.md                         # スキル本体（権威順序・6原則・直交ルーター・実行フロー）
├── README.md                        # 本書
├── CHANGELOG.md                     # バージョン変更履歴
├── REFERENCES.md                    # 一次資料・出典一覧（URL・確認日）
├── LICENSE                          # MIT License
├── tokens/
│   ├── design-tokens.json           # 44ペア事前計算済みトークン定義
│   └── design-tokens.css            # そのまま貼れる Light/Dark CSS 変数定義
├── tactics/
│   ├── mod-doc.md                   # 文書・Markdown・日本語組版 (DOC-01〜DOC-08)
│   ├── mod-visual-a11y.md           # 視覚階層・M3サーフェス・WCAG 2.2主要項目・モーダルAPG (VIS-01〜VIS-12)
│   ├── mod-interaction-forms.md     # ボタン階層・GOV.UK式フォーム・5状態・マイクロコピー (INT-01〜INT-12)
│   ├── mod-slide.md                 # Markdown/Marp構成案向け Assertion-Evidence スライド設計 (SLD-01〜SLD-07)
│   └── mod-pro-ai.md                # 高密度データテーブル (PRO-01〜PRO-05) & AIチャットUI (AI-01〜AI-04)
├── evaluation/
│   ├── blockers.md                  # Blocker具体リスト (BLK-01〜BLK-07) & カバレッジ表 & 証拠義務
│   ├── checklist-web.md             # Web/UI用 3区分チェックリスト (CHK-W1〜W6 / PRN-1〜6 / UNV-W1〜W3)
│   └── checklist-doc.md             # 文書/スライド用 3区分チェックリスト (CHK-D1〜D4 / PRN-1〜6 / UNV-D1〜D2)
├── scripts/
│   └── ui_ux_checker.py             # 依存ゼロ（Python 3.9+ 標準ライブラリ）機械判定チェッカー
└── tests/
    ├── run_tests.py                 # unittest 検証スイート
    └── fixtures/                    # 検証用サンプル群
```

### 機械判定チェッカーとテストの実行（Python 3.9+・追加ライブラリ不要）

```bash
# HTML / CSS / Markdown を検査
python3 scripts/ui_ux_checker.py path/to/target.html
python3 scripts/ui_ux_checker.py path/to/styles.css --strict-tokens --json
python3 scripts/ui_ux_checker.py path/to/spec.md --doc-type spec

# デザイントークンの検証済みペア自体を検証
python3 scripts/ui_ux_checker.py --check-tokens tokens/design-tokens.json

# テストスイートを実行
python3 tests/run_tests.py
```

## ライセンス

[MIT License](LICENSE)
