# Module: Visual Hierarchy, Layout & Accessibility (`mod-visual-a11y`)

対象: Webサイト、LP、Webアプリ全般（HTML / CSS / UIコンポーネント）

## 1. 視覚的階層・余白・サーフェス（WCAG 2.2 / Material Design 3 準拠）
- **VIS-01 色覚多様性に配慮した階層設計（SC 1.4.1）**: 情報の優先順位や状態（エラー・成功など）は、**サイズ・ウェイト（400/500 vs 600/700）・余白・テキストラベル・アイコン・形状**の組み合わせで成立させ、色はそれらを補強するレイヤーとして重ねる。
- **VIS-02 近接の法則の数値化**: 関連要素間（グループ内）の余白を狭くし、別グループ間の余白は**グループ内の2倍以上**にする（例: グループ内 `var(--space-2)` 8px / グループ間 `var(--space-4)` 16px〜`var(--space-6)` 24px）。入力ラベルは対象フィールドの直上に密着させる。
- **VIS-03 サーフェスと区切りの使い分け**: 要素のグルーピングと階層分離は、**1. 余白 → 2. トーン差のあるサーフェスカラー（`bg-page` / `bg-surface` / `bg-subtle`） → 3. 距離感に応じた控えめなシャドウ → 4. モーダル下のスクリム** の順に使い分ける。
- **VIS-04 セマンティックトークン運用**: `tokens/design-tokens.css` を組み込み、色・余白・文字サイズは CSS 変数（`var(--...)`）から参照する。`border-default` は純粋な装飾区切り線のみに使い、フォーム入力欄など意味のあるUI境界には `border-input`（3:1以上）を使う。

## 2. カラー・コントラスト・ダークモード（WCAG 2.2 AA）
- **VIS-05 コントラスト比基準（WCAG 2.2 AA）**:
  - 通常テキスト: **4.5:1 以上**
  - 大きいテキスト（**18pt≒24px以上**、または**太字700以上の14pt≒18.66px以上**）: **3.0:1 以上**
  - 非テキストUI部品（入力欄の枠線、アイコン、フォーカスリング等 / SC 1.4.11）: **3.0:1 以上**
- **VIS-06 検証済みカラーペアの適用**: `tokens/design-tokens.json` の `verified_pairs` に登録されたペアをそのまま適用する。
- **VIS-07 ダークモードの奥行き表現**: 深いスレート系サーフェス（`#0F172A` → `#1E293B` → `#334155`）と明度を抑えたオフホワイト（`#F8FAFC`）を用い、重なり合う要素ごとに明度トーンを変えて奥行きを表現する。ライト・ダーク双方でコントラスト比を検証する。

## 3. セマンティックHTML・キーボード・モーダル・モーション・レスポンシブ
- **VIS-08 フォーカス可視化と非隠蔽（SC 2.4.7 / 2.4.11・ハードガードレール）**:
  - `outline: none` の単独指定を禁止する。`:focus-visible` で `var(--focus-ring)`（3:1以上）を必ず表示する。
  - `position: sticky` のヘッダーや固定入力バーを使う場合は、`scroll-padding-top` / `scroll-padding-bottom` を設定し、フォーカスされた要素が固定要素の裏に隠れないようにする（WCAG 2.2 SC 2.4.11）。
- **VIS-09 セマンティックHTMLの黄金律（W3C ARIA APG 準拠）**:
  - **Links go places, Buttons do things**: 遷移には有効な `href` を持つ `<a href>`、操作・開閉・送信にはネイティブの `<button type="button|submit">` を使う。
  - `<html lang="ja">`、ページ固有の `<title>`、スキップリンク、ランドマーク（`<header>`, `<nav>`, `<main>`, `<footer>`）、連続した見出しレベルを構成する。
  - 意味を持つ `<img>` には内容を表す `alt`、純粋な装飾画像は `alt=""` とする。画像のみを含むリンクやアイコンボタンには `alt` または `aria-label` でアクセシブルネームを与える。
- **VIS-10 モーダルダイアログのフォーカス管理（W3C ARIA APG）**:
  - ネイティブ `<dialog>`（`showModal()`）または `role="dialog" aria-modal="true"` を使い、開いた際にモーダル内へフォーカスを移動・閉じ込め（フォーカストラップ）、`Esc` キーで閉じられ、閉じた後は起動元ボタンへフォーカスを復帰させる。
- **VIS-11 モーション配慮**: アニメーション実装時は `@media (prefers-reduced-motion: reduce)` で動きを抑制するフォールバックを併記する（※JSが `transitionend` に依存する箇所は短縮値や完了ハンドラの互換性に留意）。
- **VIS-12 レスポンシブ・モバイルファースト**: モバイル幅（375px）で1カラムに収まり横スクロールが起きないレイアウトにし、左右余白は最低 `var(--space-4)`（16px）を確保する。

### Good Pattern: フォーカス可視化・sticky非隠蔽・モーション配慮CSS
```css
html { scroll-padding-top: 72px; }
:where(a, button, input, select, textarea, summary, [tabindex]:not([tabindex="-1"]), [contenteditable="true"]):focus-visible {
  outline: 2px solid var(--focus-ring);
  outline-offset: 2px;
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; scroll-behavior: auto !important; }
}
```
