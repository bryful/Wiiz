# C++ネイティブ版

Windows向けのC++20＋SDL3＋CMakeアプリです。Web公開やサーバー、Pythonの実行時依存はありません。
現在は既存binjnesコアでROM本体を動かす「原作表示・挙動の基準版」です。
解析済みのゲーム処理をC++で再構成した完成版とは区別します。
ROMや抽出画像を実行ファイルへ埋め込まず、利用者が指定したフォルダのROMを読み込みます。

## 開発・ビルド

Visual Studioの「C++によるデスクトップ開発」とCMakeツールを使用します。
Visual Studioでリポジトリのフォルダーを開き、`windows-vs`（VS 2026）または
`windows-vs2022`プリセットを選択します。VS CodeではC/C++・CMake Tools拡張から同じ設定を使います。
CMake 3.24以降。初回のSDL3取得だけネット接続が必要です。実行時通信はありません。

Developer PowerShellでの例：

```powershell
cmake --preset windows-vs
cmake --build --preset windows-release --parallel
./output/native-build/windows-vs/Release/wiiz.exe
```

取得済みSDL3を使用する場合、構成時に
`-DFETCHCONTENT_SOURCE_DIR_SDL3=C:/path/to/SDL3-3.2.28`を追加できます。
公式ZIPのSHA-256をCMakeで固定し、binjnesは固定リビジョンのソースにRAM書込コールバックだけを追加して同梱しています。

## 起動・ゲーム選択

- 起動時にROMフォルダ直下の`.nes` / `.NES`を調べ、プログラムの特徴で識別できる作品を一覧表示。
- 上下で選び、XまたはReturnで起動。未知の版は実行せず、非対応件数を表示。
- 初期フォルダは実行ファイルの隣の`roms/`。開発時、作業フォルダに`.nes/`があればそちらを使います。
- Qのメニューから「Select ROM folder」で変更。指定したパスはユーザー設定へ保存。
- `wiiz.exe --rom-dir C:/your/roms`で起動時の検索先を指定することもできます。
- 開発用にROMパスを引数へ直接渡す起動方法も残しています。

## 10入力

| 入力 | キー |
|---|---|
| 上下左右 | カーソルキー |
| ゲームA | X / Return |
| ゲームB | Z / Backspace |
| Select | A / Tab |
| Start | S / Space |
| リセット | Escape |
| アプリ設定 | Q |

ゲーム側の8入力はROMへそのまま渡します。移動・扉の操作・戦闘などは原作ROMが処理します。
Escapeは確認なしで現在のコアへリセット信号を送り、同じROMのリセットベクタへ進みます。
ROMの再読込、コアの作り直し、RAM消去、セーブの巻き戻し、ゲーム選択への移動は行いません。
その後どの画面へ進むかは、保持されたRAMを使う原作ROMの起動処理に従います。

Qでゲーム中メニュー兼アプリ設定を開きます。ゲームは一時停止し、上下とXで選択、ZかQで戻ります。
高速描画は画面崩れのため撤回し、通常描画を強制します。過去のON設定は無視されます。
原作描画を保った完成画面に、任意のCRT後処理を追加できます。Q → Display / speedから調整します。詳細は[crt.md](crt.md)。
「Exit application」で終了。「Game selection / rescan」で保存して一覧へ戻れます。
これはアプリ側の重ね表示メニューであり、ROM内のメニューを書き換えたものではありません。
Sは原作のStartのままです。ゲーム中にウィンドウの閉じる操作をした場合も、このメニューの終了項目を表示します。
フォーカスを失うと一時停止し、押しっぱなし入力と滞留音声を解除します。

## 映像・音声・保存

- 原作のPPU出力256×240を、最近傍・3倍で描画。ウィンドウ全体は縦横比を保って拡縮。
- CPU/PPU/APU/MMC1/MMC3は既存binjnes。独自のエミュレーターコアは作っていません。
- 色はbinjnesのパレットを使用。実機アナログ出力とのRGBの完全一致は保証しません。
- 音声はコアが生成した48kHz/mono/floatをSDL3へ渡します。出力機器が使えない場合は画面に明示して無音で継続。
- セーブはSDLのユーザー設定フォルダ`Wiiz/Wiiz/saves/<ROM名>.sav`へ保存（初期値）。QでJSONへ切替可能。
  Windowsでは通常`%APPDATA%/Wiiz/Wiiz/`。2秒ごとと、メニューからの終了・作品切替時に保存します。
- 一時ファイルから置換し、サイズが不正な既存セーブは読み込みを拒否して上書きしません。
- 選択形式がなければ別形式や旧ハッシュ名のセーブを読み、原本を残して移行。SAV/JSONとも原作用のチェックサムを再構成します。
- ステートは5枠。F1〜F5で保存、Shift＋F1〜F5で読込。Q → State save / loadに5枠を表示し、左右でSave/Load、Xで実行します。
  保存先・形式・互換性・検証範囲は[save-data.md](save-data.md)。
- Wiz1はiNESヘッダのPRG-RAMサイズが0（未指定）のため、対象ハッシュに限定した接続層で8KiBの情報を補完。
  初期化済みbank 0のRAMを保存対象にし、Mapperの処理は変更していません。

## 検証コマンド

```powershell
python tests/check_native.py output/native-build/windows-vs/Release/wiiz.exe
python tests/check_native_core.py output/native-build/windows-vs/Release/wiiz.exe
python tests/check_native_input.py output/native-build/windows-vs/Release/wiiz.exe
python tests/check_native_drawing.py output/native-build/windows-vs/Release/wiiz.exe
python tests/check_native_turbo.py output/native-build/windows-vs/Release/wiiz.exe
./output/native-build/windows-vs/Release/wiiz.exe --smoke .nes/wiz1.nes output/native-title.bmp
./output/native-build/windows-vs/Release/wiiz.exe --smoke-library .nes output/native-library.bmp 1
./output/native-build/windows-vs/Release/wiiz.exe --smoke .nes/wiz1.nes output/native-dungeon.bmp 4300 tests/replays/wiz1-dungeon.txt
```

`--check ROM`は従来のマップ解析との比較用です。
`--core-check ROM [一時保存フォルダ]`は720フレーム実行・映像/音声・RAM保持・リセットベクタ到達を検査します。
保存フォルダを省略した場合、ユーザーのセーブに触れません。
`--smoke ROM BMP [フレーム数] [入力スクリプト]`は既定360フレーム描画して終了します。
`--smoke-library`はゲーム選択画面から開始。どちらも通常のセーブ・フォルダ設定は使いません。
スクリプトは`400 X down` / `402 X up`のように0始まりのフレーム番号、SDLキー名、down/upを記述します。
旧smoke引数`original` / `fast`は互換性のため受け付けますが、どちらも未改変ROMの通常描画です。
検証用セーブのコピーを使う場合は、その後ろにセーブフォルダを追加できます。ユーザーの本来の保存先を指定しないでください。

2026-10-20確認：Windows / VS 2026 / MSVC 19.51 / x64 Release。
3作品で720フレーム、映像の非単色、有限の非無音サンプル、リセット時のCPU RAM・PRG RAM保持と
ROMリセットベクタ到達、8KiBセーブ保存・再読込が成功。
既存マップ解析との全8,800マスの一致、改名ROM・大文字拡張子・未知ROM・空フォルダの検査も成功。
Wiz1は入力再生でタイトル→日本語の城→酒場→初期戦士を編成→町外れ→迷宮→キャンプ解除まで画面確認。
迷宮の壁と階段メッセージを表示できました。再現用スクリプトは`tests/replays/wiz1-dungeon.txt`。
SDLイベントによる一覧の作品選択、同じ作品へのEscapeリセット、Q/Zの開閉、メニューからの終了も検証しました。
画面崩れ修正では、高速描画パッチを完全撤去し、起動・城900フレームと迷宮4,300フレームの全画素・全音声サンプルを、
未改変ROMで独立して起動した参照コアと比較して一致を確認しました。
6人パーティーの戦闘から探索画面へ戻る再現スクリプトも追加し、敵の残像なし・全員のステータス復元を画面確認。
宝箱を開くという報告と同一の操作はまだ再現できていません。

## 残っていること

Wiz2/3のダンジョンへの到達、扉操作、戦闘中のリセット技などはまだ一通り検証していません。
原作処理が動くことと、全場面が正確に再現されることは区別します。
長時間の音切れ・遅延・聴感、設定の手動ダイアログ操作、異常終了・停電時の保存耐性、Androidは未検証です。
Androidのパッケージ化と画面ボタン、日本語のアプリ側UIも今後の作業です。
解析用俯瞰マップ・既存Python検証器は引き続きリポジトリに残しています。
コア選定の根拠・出典・未対応範囲は[native-core.md](native-core.md)を参照してください。

## 全体高速化

Ⅰ・Ⅱ・Ⅲのデュマピック・キャンプのマロールには探索済みマップを表示します。
マロールの移動先は方向キー、階層はA/S、Xで決定・Zで取消。詳細は[spell-map.md](spell-map.md)。

対応するⅠ・Ⅱ・Ⅲは初期値4倍速。Q→Speed→Xで1/2/4/8倍を切り替えます。
音楽・SEは別の既存コアで等速再生し、方向キーのリピートは実時間で制御します。
パラメータ変更版も、接続先コードが一致する場合は同じ機能を使えます。詳細は[turbo.md](turbo.md)。

入力の別名とメーカー表示スキップ設定は[settings.md](settings.md)を参照してください。
