# Wiiz

** アプリを統合して一つにまとめました。今後の開発は[https://github.com/bryful/WizPlayer](https://github.com/bryful/WizPlayer)で行います。**



ファミコン版Wizardry Ⅰ・Ⅱ・ⅢをWindows／Androidで遊ぶためのアプリです。
既存のbinjnesエミュレーターコアを利用し、原作の映像・音声、速度変更、探索済みマップ、セーブ・ステート保存、ゲームパッド入力などに対応します。

## ダウンロード

**アプリのダウンロードは [Wiiz_app](https://github.com/bryful/Wiiz_app) から行ってください。**
Windows版・Android版の配布物と導入・操作方法はWiiz_appに掲載しています。このリポジトリはソースコードの公開用です。

ゲームROMは付属しません。ご自身で利用する権利のある対応ROM（`.nes`）を用意してください。
現在のバージョンは0.1.3です。対応ROMや機能ごとの検証範囲には制限があります。

## 開発・操作資料

- [Windowsビルド・操作方法](docs/native-app.md)
- [Androidビルド](docs/android.md)
- [設定](docs/settings.md)・[ゲームパッド](docs/gamepad.md)
- [アイテム編集](docs/item-editor.md)
- [セーブ](docs/save-data.md)・[ターボファイル](docs/turbofile.md)
- [探索済みマップ](docs/spell-map.md)・[補助機能](docs/difficulty.md)
- [ROM識別と検証範囲](docs/rom-identification.md)
- [解析ツールと調査資料](docs/analysis.md)

解析ツールにはローカルのROMが必要です。ROM、ROMを埋め込んだHTML、抽出画像・音声、セーブ、署名鍵、個人用IDE設定、ビルド生成物は公開対象に含めません。解析出力はローカルで生成してください。

## ライセンス

本プロジェクト独自部分は [MIT License](LICENSE) です。
第三者コード・データにはそれぞれのライセンス・権利条件が適用されます。出典・著作権表示は [third_party/README.md](third_party/README.md)、各ディレクトリのLICENSE・PROVENANCE、および関連資料に保持しています。
Wizardryおよびゲームデータの権利は各権利者に帰属します。
