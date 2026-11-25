# UI/UX Design Skill (v2.0)

AI に「Webサイトを作って」「資料やドキュメントをまとめて」と頼んだとき、**見た目が整っていて、読みやすく、操作しやすいアウトプットを自動で出してくれるようにする AI スキル**です。

専門的なデザインの知識がなくても、AI 側がプロのガイドラインに沿って作成・自己チェックまで行ってくれます。

## これを入れると何が便利？

- **「読みにくい・使いにくい」を自動で防ぐ**: 文字が薄くて読めない、スマホでボタンが押しにくい、長文がベタ打ちで見づらい……といった、AI がやりがちなデザインミスを自動で直してから出力します。
- **Webサイトも、普段の文書も両方カバー**: HTML/CSS の画面づくりや UI モックアップ画像に加えて、Markdown の仕様書・マニュアル、プレゼン構成案（Marp・スライド）まで、用途に合わせてルールを切り替えてくれます。
- **既存サイトや文書の「ダメ出し＆改善」もできる**: すでに作った画面や文章を渡せば、勝手に全部書き換えるのではなく「どこを直すべきか」の診断レポートを先に出してくれます。
- **AI の「根拠のない大丈夫」を防ぐ**: 色の見やすさ（コントラスト比）などは同梱のチェッカーで自動検査し、コードだけでは確認できない部分は「未検証」と正直に教えてくれます。

## 一番ラクな導入方法

難しい設定は不要です。お使いの AI エージェント（Claude Code やスキル対応エージェント等）のチャットに、以下をそのまま投げるだけで OK です。

> 導入は AI のチャットに **`https://github.com/ferran0000/UI-Skills これ追加して`** と投げちゃってください。

導入後は、普段どおり「お問い合わせフォームを作って」「この手順書を読みやすく整えて」「この HTML の UI をレビューして」と話しかけるだけでスキルが働きます。

---

## 開発者・上級者向けの詳細情報

### 手動で配置する場合

リポジトリをクローンするか ZIP を解凍し、スキルディレクトリへ配置してください。

```bash
git clone https://github.com/ferran0000/UI-Skills.git
cp -r UI-Skills .claude/skills/ui-ux-design
```

### 構成

スキル本体は次の2ファイルだけです。

```text
.
├── SKILL.md                  # スキル本体（ルール・評価方法・実行フロー）
└── scripts/
    └── ui_ux_checker.py      # 機械判定チェッカー（Python 3.9+ 標準ライブラリのみ）
```

加えて、ライセンス（`LICENSE`）を同梱しています。

### 機械判定チェッカーの使い方

```bash
# HTML / CSS / Markdown を検査
python3 scripts/ui_ux_checker.py path/to/target.html

# JSON 形式で出力
python3 scripts/ui_ux_checker.py path/to/target.html --json

# Markdown を仕様書として検査（段落の長さの基準が変わる）
python3 scripts/ui_ux_checker.py path/to/spec.md --doc-type spec

# JPEG / PNG の画像を検査（指定した2色のコントラスト、または領域のコントラスト）
python3 scripts/ui_ux_checker.py path/to/mockup.png --sample-pair 10,10:20,20 --contrast-box 0,0,200,100
```

## ライセンス

[MIT License](LICENSE)
