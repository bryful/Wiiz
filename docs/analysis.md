# Wiiz — Wizardry FC ROM解析

公開対象は [github.md](github.md) を参照してください。

2026-10-21に生成済みの解析HTMLと関連データを`output/`から`reference/`へ移動しました。
閲覧の入口は`reference/index.html`、音声は`reference/audio/index.html`です。
以下の生成コマンドの既定出力先は引き続き`output/`です。`reference/`の生成データはローカル専用で、公開しません。

## C++ネイティブ版の試作

Windows／AndroidでXbox・Switch Proのゲームパッド入力に対応。キーコンフィグなしの固定配置、接続・再接続の自動認識。配置と検証状況は [docs/gamepad.md](gamepad.md)。

SDL3＋CMakeのWindows向けアプリで、ROMフォルダからゲームを選択できます。
既存binjnesコアによる原作画面・音声、指定の10入力、同じROMへのリセット、バッテリーセーブに対応。
Visual Studio／VS Codeで管理できます。ROMは同梱しません。現在は原作挙動を確認する基準版です。
表示崩れを起こした描画パッチは撤回済みです。Ⅰ・Ⅱ・Ⅲは原作の描画処理を保って全体を1/2/4/8倍にでき、音楽と方向キーリピートは等速です。
初期値4倍、QのSpeed項目から変更できます。対応する3作品で利用できます。詳細は [docs/turbo.md](turbo.md)。
通常セーブはROM名のSAV（初期値）またはJSONをQで選択。両形式とも読込時にチェックサムを補完し、旧ハッシュ名のファイルも保持して引き継ぎます。
5枠のステート保存はF1〜F5、読込はShift＋F1〜F5、Qメニューからも操作できます。
保存先とJSON編集方法は [docs/save-data.md](save-data.md)。
ReturnでもA、BackspaceでもB、SpaceでもStart、TabでもSelectを押せます。メーカー表示のスキップもQで設定できます。詳細は [docs/settings.md](settings.md)。
Qメニューで次レベルに必要な経験値の補充・Gold加算、属性変更、酒場の善悪混合パーティー、全スペル習得、MP9固定、作成時の最大ボーナス、ロミルワ・ラツマピック・マポーフィック常時有効、MキーでMP不要の地図表示、現在位置・方角の常時表示に対応。詳細は [docs/difficulty.md](difficulty.md)。

タイトル画面のQ → Roster orderで20人を一覧表示。上下で選び、X/Returnでつかみ、上下で移動してX/Returnで確定できます。交換前の自動バックアップとパーティー参照の更新を行います。[操作説明](roster-order.md)。

CRT表示はOFF／弱／標準（初期値は弱）。Qメニューを用途別に整理し、Display / speedから調整できます。詳細は [docs/crt.md](crt.md)。
Ⅰ・Ⅱ・Ⅲのデュマピック・キャンプのマロールは探索済みマップ表示に対応。操作と対応範囲は [docs/spell-map.md](spell-map.md)。
パラメータ変更ROMもプログラム構造で識別し、ファイル名に依存せず起動できます。調査結果・検証状況は [docs/rom-identification.md](rom-identification.md)。
ビルド・操作・未対応範囲は [docs/native-app.md](native-app.md) を参照してください。

ROMの画像・文字列・パラメータを抽出し、ゲーム処理を新規実装するための調査用プロジェクトです。

## Wiz1 BGMプレイヤー

既存エミュレーターJSNES 2.1.0のCPU・PPU・MMC1・APUを利用し、ROMから検出した13曲のBGMを再生できます。

```powershell
node tools/build_audio.mjs
```

`reference/audio/index.html` をブラウザーで開き、曲を選んで「再生」を押してください。外部通信なしで再生できます。WAVの試聴用抜粋と、ROM参照位置・音声検証結果を含む `catalog.json` も生成します。詳細と未検証範囲は [docs/audio.md](audio.md) を参照してください。

SEは `node tools/probe_se.mjs` で13種類を生成し、`reference/audio/se/index.html` から試聴できます。各SEの使用場面とBGMとの同時再生は未確認です。

## Wiz1・Wiz2・Wiz3の共通入口

`.nes` フォルダの3作品を解析し、`output/index.html` に結果を生成します。保存済みの結果は`reference/index.html`から閲覧できます。

```powershell
python -m pip install --target output/deps -r requirements-analysis.txt
python tools/analyze_roms.py --verify
```

| ROM | Mapper | モンスター種 | 確定・不確定のPNG数 |
|---|---|---|---|
| wiz1.nes | 1 / MMC1 | 101 | 202 |
| WIZ2.NES | 4 / MMC3 | 78 | 156 |
| WIZ3.NES | 4 / MMC3 | 90 | 180 |

Wiz2・Wiz3の画像形式はWiz1と異なるため別途解読し、全ケースを各ROMの描画処理と照合しています。
Wiz2のDoppelganger確定画像は通常描画では空、Wiz3の2種は一部の色が直前の状態に依存します。画像一覧にも注記しています。
詳しくは [docs/wiz2-wiz3-graphics.md](wiz2-wiz3-graphics.md) を参照してください。

## 日本語モンスター図鑑

各作品の既存の画像一覧を図鑑へ拡張しました。日本語・英語・IDで検索でき、経験値・最大HP・ACで並び替えできます。
全269種の日本語名、HP・出現数ダイス、AC、攻撃回数とダメージダイス、呪文レベル、経験値を共通JSONへ出力しています。
日本語名と能力値の読み込みをROM処理の英語・日本語モード計538ケースと照合しました。

詳細とフィールド位置、特殊値の扱いは [docs/monster-catalog.md](monster-catalog.md) に記録しています。

## ダンジョンマップ

3作品・22階層（各20×20）の壁、扉、隠し扉、ダークゾーン、玄室、イベント参照を抽出しました。
共通入口`reference/index.html`から各作品のダンジョンビューアへ進めます。階段・座標移動の行き先を表示し、移動先マスへ切り替えられます。

```powershell
python tools/analyze_roms.py --verify
node tests/check_dungeon_ui.cjs
```

全8,800マスをROMの読込処理と照合しています。未分類イベントと、ゲーム中に変化する条件分岐は未解析のまま明示しています。
詳細は [docs/dungeons.md](dungeons.md) に記録しています。

## 画像抽出

Python 3のみで実行でき、追加ライブラリは不要です。

```powershell
python tools/extract_chr.py .nes/wiz1.nes
```

`reference/chr/index.html` をブラウザで開くと全タイルを閲覧できます。
画像上にマウスを置くとバンク内タイル番号、全体タイル番号、ROMファイルオフセットが表示されます。

- `bank_00.png` ～ `bank_31.png`: 各4 KiBの画像バンク。16×16個のタイルを格納した128×128画像。
- `bank_00.chr` ～ `bank_31.chr`: 対応する生CHRデータ。
- `manifest.json`: ROMハッシュ、領域サイズ、各バンクのファイル位置。

ROMと`output/`の生成物はGit対象外です。`reference/`の解析HTML・画像・JSON・音声もローカル専用です。

## このROMで確認した構成

| 項目 | 値 |
|---|---|
| ファイルサイズ | 262,288 bytes |
| ヘッダ | iNES / Mapper 1（MMC1） |
| PRG | 128 KiB / ファイル位置 `0x000010` |
| CHR | 128 KiB / ファイル位置 `0x020010` |
| CHRタイル数 | 8,192 |
| CHRバンク | 4 KiB × 32 |
| CHR終了後の末尾データ | 128 bytes（用途未調査） |

1タイルは8×8ピクセル、16 bytes。先頭8 bytesが各行の下位ビット面、後半8 bytesが上位ビット面です。
各行のbit 7が左端で、2面を合成して色インデックス0～3を得ます。
ファイル位置は `0x020010 + バンク番号 × 0x1000 + タイル番号 × 16` です。
CPUアドレスやPPUアドレスとは区別します。

### 現時点の成果と制限

全CHR領域をデコードしてPNG化しました。bank 00では背景・壁などと思われる断片、bank 08では人物・モンスターと思われる断片を目視確認しています。用途の確定はまだ行っていません。

PNGは色インデックスを黒・暗灰・明灰・白へ割り当てた確認用画像です。
実際の色はPPUパレット、完成画像はタイル配置情報と組み合わせる必要があります。
この抽出だけではモンスター1体単位の完成画像やゲーム画面は復元されません。

モンスターの配置データとパレットは下記の直接抽出で特定できました。

## モンスター画像の直接抽出

```powershell
python tools/extract_monsters.py .nes/wiz1.nes
```

追加ライブラリ不要で、101種 × 不確定・確定の2状態 = **202枚の透過PNG**を出力します。
`reference/monsters/index.html` をブラウザで開くと、名前・IDで検索し、2状態を並べて比較できます。

- `000_unknown.png` ～ `100_identified.png`: 個別の透過PNG。
- `atlas.png`: 新規ゲーム実装向けの1枚にまとめた画像。
- `monsters.json`: 名前、画像ファイル、atlasの矩形、元の画面座標、スプライト配置、パレット、ROM位置。

共有を除く配置データは114パターンでした。画像はインデックス0の画素を透過にし、色付き部分の外接矩形で切り出しています。
英語名はROMのモンスターレコードから取得し、未対応の文字コードは `{25}` のように残します。元の文字コード列もJSONへ保存しています。
特定済みのSHA256のROMだけを対象とし、別版には固定オフセットを適用しません。

### ROMの処理との照合

```powershell
python tools/verify_monsters.py .nes/wiz1.nes --report output/monsters/verification.json
```

この検証には `requirements-analysis.txt` のpy65が必要です。
ROM内の `PRG bank 3 / CPU $8000` の描画処理を全202ケースで実行し、直接抽出したOAM配置、パレット、CHRバンク、OAM終端位置がすべて一致しました。
個別PNGとatlasの203ファイルについてPNGのCRC、寸法、アルファ画素が存在することも確認しました。

これは配置データの解読を検証するもので、実機のアナログ色や戦闘全体の動作を保証するものではありません。
データ形式とアドレスの詳細は [docs/monster-graphics.md](monster-graphics.md) に記録しています。

## 実行時の画像データ解析

```powershell
python -m pip install --target output/deps -r requirements-analysis.txt
python tools/trace_graphics.py .nes/wiz1.nes --frames 360 --press 200:START:2 --output output/trace_start
python -m unittest discover -s tests
```

`reference/trace_start/index.html` で復元画像を閲覧できます。`--press` は「1始まりのフレーム:ボタン:押すフレーム数」で、複数指定できます。
ボタンは A / B / SELECT / START / UP / DOWN / LEFT / RIGHT です。

CPU実行にはpy65 1.2.0を使用し、解析用にMMC1、CPUバス、PPUレジスタ・メモリ、コントローラ入力を実装しました。
60フレームごとに以下を保存します。

- `background.png`: ネームテーブル・属性テーブル・パレットから再構成した背景。
- `pattern.bin`: その時点でPPUに見える8 KiBのCHR。
- `nametables.bin` / `palette.bin` / `oam.bin`: 各メモリのダンプ。
- `state.json`: レジスタ、MMC1状態、パレット。内部frameは0始まり、フォルダ名は1始まり。
- `tiles.json`: 各画面タイルの位置、パレット番号、CHRバンク、元ROMオフセット。
- 出力フォルダ直下の `mapper_events.json`: MMC1の変更履歴と書き込み処理時のPC。

### 実機ROMで確認できたこと

無入力でASCIIロゴとタイトル画面を復元。200フレーム目にSTARTを2フレーム押した実行で、日本語の城メニューまで到達しました。
タイトルではCHR0=31 / CHR1=2、城メニューではCHR0=31 / CHR1=4で、背景はPPUCTRLのbit 4によって後半のCHR領域を参照しています。
これは観測した状態であり、全バンクの用途分類ではありません。

解析用の近似実行です。APU、正確な走査線タイミング、スプライトゼロ判定、DMAの停止時間は実装していません。
背景PNGにはスプライト・スクロール・走査線効果を描画していません。RGB値も確認用の変換です。
実際の戦闘画面への到達はまだ未検証ですが、上記の直接抽出でモンスター画像を復元しています。

### EmotionalEngine-NESの参照

https://github.com/ymduu/EmotionalEngine-NES

参照コミット: `29f518908479c5ead672024ae502db0257c22509`（MIT）。調査用の取得ソースは2026-10-20に削除しました。ビルド・実行には使用していません。再調査する場合は上記の出典とコミットから取得できます。
`Ppu.cpp` のビット面・属性テーブルの扱い、`System.cpp` のバス・パレットミラー処理、`cassette.cpp` のROM読込構成を確認しました。ソースコードの転用は行っていません。

この時点の参考実装にはMMC1処理がなく、`constants.h` のROM格納上限もPRG 32 KiB / CHR 8 KiBです。
対象ROMはPRG・CHRとも128 KiBのため、そのまま組み込むのではなく、解析用の実行基盤を別途作成しています。

## 参考資料

- https://taotao54321.github.io/appsouko/work/Game/Wiz1_NES/
- https://taotao54321.github.io/appsouko/work/Game/Wiz1_NES/prog_rom.txt

参考資料は米国NES版が対象です。日本FC版とアドレス・内容が一致する前提では使用せず、このROMで検証します。

## 歩ける探索プロトタイプ（Wiz1）

`reference/explorer/index.html` から全10階層の迷宮を探索できます。前進・旋回、扉・隠し扉、階段・転移、暗闇、探索マップと保存に対応しています。キャラクター作成・6人編成・所持品・装備管理を追加し、パーティも一緒に保存できます。戦闘・街は未実装です。

```powershell
python tools/build_explorer.py
node tests/check_explorer.cjs
node tests/check_explorer_ui.cjs
node tests/check_party.cjs
node tests/check_party_ui.cjs
```

矢印キー/WASDで移動・旋回、Spaceで扉、Fで探索、Enterで階段。描画と一部の操作ルールは試作仕様です。[docs/explorer.md](explorer.md) に対応範囲・保存・検証内容を記録しています。

作成時の能力値とHPは試作の固定値です。装備の値はROMから読み、74種類の装備計算を既存Pythonカーネルと比較しました。キャラクター管理と旧保存形式の扱いは [docs/party.md](party.md) を参照してください。

## アイテム・呪文の抽出

3作品の349アイテム・153呪文を共通JSONと検索ページに出力します。全体解析コマンドで生成され、`reference/index.html`から各作品の「アイテム・呪文」を開けます。

```powershell
python tools/analyze_roms.py --verify
node tests/check_item_spell_ui.cjs
```

価格・装備制限・ダメージ・AC・呪文名とレベルを抽出。配置・検証範囲は [docs/items_spells.md](items_spells.md) に記録しています。

装備済み1品の加算、AC呪文、基本回復、SPの一部効果を、CPUに依存しない `tools/game_rules.py` に実装しました。原作ルーチンとの追加照合5,590ケースが一致しています。検索ページにもSPの説明・AC呪文の対象・回復量を表示します。詳しくは [docs/game_rules.md](game_rules.md) を参照してください。

`tools/item_use_rules.py` には使用後の変化、SPの職業条件、実装済みSPの確認後の連続処理を追加しました。通常使用とSPで比較条件・フラグ更新が異なります。全乱数バイトを含む原作コードとの追加照合273,864ケースが一致し、最大HP増加SPのCarryの経路も確認しました。詳細・残る範囲は [docs/item_use.md](item_use.md) を参照してください。

`tools/status_rules.py` に状態表示・治療・蘇生、`tools/game_rng.py` に乱数の状態更新と作品別の範囲変換を追加しました。毒と状態コードの区別、蘇生時の生命力低下・失敗処理の作品差を反映し、追加251,594ケースが原作コードと一致しています。検索ページから治療・蘇生条件を確認できます。[docs/status_rules.md](status_rules.md) に詳細を記録しています。

`tools/affliction_rules.py` にカティノ・マニフォ・モンティノの抵抗判定と付与処理を追加しました。抵抗値FFの扱い、レベル計算、乱数消費の作品差を含め、追加612,511ケースが一致しています。全269種のモンスターデータにも抵抗値・カティノ補正フラグを追加しました。[docs/afflictions.md](afflictions.md) を参照してください。

## Android版の開発

Android Studioで `android/` を開きます。必要なSDK・JDK、ビルド方法と未対応範囲は [docs/android.md](android.md) を参照してください。

原作のターボファイル（共通8KBイメージ）に対応。原作メニューから作品間のキャラクター転送・データ保存/復元を行えます。[操作と保存先](turbofile.md)。
