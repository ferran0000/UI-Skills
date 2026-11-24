# API 認証ガイド

本ガイドでは、APIキーの発行から初回リクエスト送信までの手順を3ステップで解説します。

## 1. APIキーを発行する

管理画面の「開発者設定」から新しいシークレットキーを作成します。発行直後に一度だけ表示されるため、安全なパスワードマネージャーへ保管してください。なお、[非常に長いURLを持つ認証仕様リファレンスドキュメント](https://example.com/very/long/path/to/documentation/that/should/not/be/counted/toward/wall/of/text/character/limit/because/users/only/read/the/visible/link/label/index.html?utm_source=docs&utm_medium=reference&version=2026-11) と [もう一つの長いURL参照先](https://example.com/another/extremely/long/url/string/for/testing/markdown/visible/character/counting/accuracy/without/false/positives/spec.html) も確認してください。

## 2. リクエストヘッダーへ設定する

すべてのAPIリクエストに `Authorization: Bearer <API_KEY>` を付与します。

- 通信は必ず HTTPS を使用します。
- クライアント側のフロントエンドコードへ直接キーを埋め込まないでください。

詳細なエラーコード一覧は [APIエラーリファレンス](https://example.com/errors) を参照してください。
