# VanaInventory

Windowerアドオン `VanaExport` が出力したJSONを読み込み、FFXIの所持品・装備をGUIで閲覧するツールです。

## 必要なもの

- Python 3.10以上
- PyQt6
- Windower4 + VanaExportアドオン（JSONエクスポート用）

### セットアップ

```powershell
pip install -r requirements.txt
```

### Windowerアドオン

1. `windower_addon/VanaExport.lua` を `Windower/addons/VanaExport/` に配置
2. `Windower/addons/VanaExport/data/` フォルダを作成
3. ゲーム内でロード＆エクスポート

```
//lua load VanaExport
//vex all
```

→ `data/{キャラ名}_inventory.json` が出力されます

## 起動

### 通常の起動
`VanaInventory.vbs` をダブルクリックして起動します。コンソールウィンドウを表示せずに GUI が立ち上がります。

### コマンドラインからの起動
```powershell
python ui_inventory.py
```

初回起動時、VanaExportの `data` フォルダを選択するダイアログが表示されます。

## 機能

### キャラクター選択
左ペインのリストからキャラクターを選ぶと、そのキャラクターの所持品が表示されます。

### ストレージ別タブ
- 上段: Inventory / Safe / Safe2 / Storage / Locker / Satchel / Sack / Case
- 下段: Wardrobe 1〜8

### 「せいとん」ソート
「せいとん」ボタンをクリックすると、FFXI準拠の順序（クリスタル→薬品→武器→防具→素材…）で並べ替えます。

### 「装備のみ」フィルタ
チェックを入れると、Weapon / Armor カテゴリのアイテムだけを表示します。

### Search All（全キャラクター検索）
ヘッダーの「Search All:」欄にアイテム名を入力してEnterで、全キャラクターを横断して検索します。
- キャラクター × 保管場所ごとに個数を集計
- アイテム名は日本語/英語の両方を表示

### 右クリックメニュー
インベントリ内のアイテムを右クリックすると、以下の操作が可能です:
- **Search All**: 全キャラクターからそのアイテムを検索
- **アイテム名をコピー / IDをコピー**: クリップボードにコピー
- **FFXIAH / BG-Wiki / FF11用語辞典**: ブラウザで外部サイトを開く

### 装備セットビルダー
「装備セット」ボタンで GearSet Builder を起動し、所持品から装備セットを作成できます。
- **ゲーム内セット取り込み**: FFXIの「装備セット」から直接データをインポートできます（キャラクターフォルダごとの管理・名前変更に対応）。
- **Luaプレビュー**: GearSwap形式のLuaコード（標準的なスロット名・順序に対応）を確認・コピーできます。
- **ストレージ表示**: アイテムがどのストレージ（金庫、サッチェル等）にあるか一目で確認できます。

### 再読込
「再読込」ボタンで、ゲーム側で `//vex all` した最新データを反映します。

## 利用上の注意
本ツールは個人の趣味の範囲での利用を前提として開発されています。以下の行為はご遠慮ください。

- 本ツール（修正版を含む）の転売・有償配布
- 有料ツールパッケージへの同梱
- その他、営利を目的とした利用

利用者は自己の責任において本ツールを使用するものとします。

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/brightworks_tm)