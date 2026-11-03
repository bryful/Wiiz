# ネイティブ版の既存コア選定

2026-10-20の調査。C++アプリから既存Cコアを呼び出す構成を採用しました。

| 候補 | 確認事項 | 今回の判断 |
|---|---|---|
| EmotionalEngine-NES（調査用コピーは削除済み） | MIT。Windows/C++ライブラリ。cassette.cppはPRG/CHR直接読込とミラーを実装 | 対象のMMC1/MMC3対応を確認できず保留。独自に追加しない |
| JSNES 2.1.0 | Apache-2.0。既存のWiz1音声検証で採用済み | 解析・比較用として継続。C++製品にJS実行系を追加する構成は今回は見送り |
| marcellocordeiro/nes-emulator | MIT、revision 3451b021947eb067eeb67abb8b544538a713630f。C++23、MMC1/MMC3、SDL3 | core/nes-core/CMakeLists.txtの音声がtodo扱い。音声・リセット検証まで同じコアで進めたいので今回は保留 |
| binji/binjnes | MIT、C11、CPU/PPU/APU、Mapper 1/4、リセット信号とバッテリーRAM API、MSVC向け実装 | 必要コアを静的ライブラリとして採用。RAM書込の任意コールバックのみ追加 |

出典：
- https://github.com/binji/binjnes/tree/e2f5871a28ff189daa82b70be9324a42e2aaf9fd
- https://github.com/marcellocordeiro/nes-emulator/tree/3451b021947eb067eeb67abb8b544538a713630f
- https://github.com/bfirsh/jsnes
- EmotionalEngine-NESのLICENSE、Include/Nes.h、Programs/src/cassette.cppを調査時に確認。ローカルコピーは削除済み。出典と参照コミットは[README](../README.md#emotionalengine-nesの参照)に記録。

## 組み込む範囲

binjnesのemulator.c、cartdb.c、common.cと必要ヘッダだけを使用。
Sokolフロントエンド、巻き戻し、テストROM、サブモジュールは含めず、外部実行時依存を増やしていません。
採用ファイルのハッシュはthird_party/binjnes/PROVENANCE.jsonへ記録。
MIT表示とパレット出典（palgen-persune / MIT-0）を残し、CMake installでも同梱します。

独自コードはC/C++間の接続、SDL入出力、ROM一覧・ハッシュ識別、ユーザー保存・UIだけです。
Wiz1の高速描画パッチは表示崩れのため撤回しました。現在は実行時のROMコピーも変更せず、
元の転送・スプライト消去を含む通常描画を使用します。経緯と検証は[fast-drawing.md](fast-drawing.md)。
Wiz1のヘッダの未指定PRG-RAMサイズを8KiBとして補完し、コアのaudio_buffer.dataを破棄時に解放します。
どちらも接続層の処理です。等速音楽の分離にはemulator.c/hに任意のRAM書込コールバックを追加しました。
コールバック未設定時は従来の動作です。上流・採用後のハッシュと差分をPROVENANCE.jsonとwiiz-ram-observer.patchに記録しています。
全体高速化の仕様と検証は[turbo.md](turbo.md)。

## リセット

emulator_set_reset(true)、emulator_set_reset(false)によるコアのリセット要求を使用します。
ROMやコアを再作成せず、RAMを巻き戻しません。検証ではCPU RAMとPRG RAMに識別値を入れ、
リセット要求の前後で保持されること、CPUが現在のROMのリセットベクタへ到達することを確認します。
その後はROM自身がRAMを書き換えるため、起動後のRAMの不変を要求しません。
この検証だけでは、全リセット技や実機の電気的なタイミングまでの一致は主張しません。

## 対象ROMでの結果と限界

- 既知の3ハッシュのみ許可。Wiz1はMapper 1、Wiz2/3はMapper 4で起動を確認。
- 720フレーム/作品、非単色映像、音声サンプル生成、リセット、セーブの往復を確認。
- Release版のコア検査はこのPCで720フレーム約1秒（描画・音声機器出力・実時間待機を除く）。
  端末全体の性能保証やAndroidの性能評価ではありません。
- Wiz1はXによるタイトル→日本語の城→初期戦士の編成→迷宮・壁表示を画面確認。
- Wiz2/3の迷宮、戦闘・扉・全場面のリセット技・実機との映像/音声の完全一致は未検証。
- C11コアとSDL3は移植候補として適合しますが、Android NDKでのビルド・実機動作は未確認。

現在のアプリは原作ROMを動かす基準版です。解析済み処理を使う独自UI・拡張へ進む場合も、
正確さの必要な部分はこの既存コアとの照合を優先します。
