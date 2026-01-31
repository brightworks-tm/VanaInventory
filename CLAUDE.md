# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

VanaInventory は、FFXI (Final Fantasy XI) の所持品・装備を閲覧する PyQt6 製 GUI アプリケーションです。Windower アドオン「VanaExport」が出力した JSON データを読み込み、複数キャラクターの所持品を横断検索できます。

## 開発環境セットアップ

```powershell
pip install -r requirements.txt
```

必要環境:
- Python 3.10 以上
- PyQt6

## 起動方法

```powershell
# GUI アプリの起動
python ui_inventory.py

# または VBS スクリプト（コンソール非表示）
VanaInventory.vbs
```

### デバッグ実行

```powershell
# コンソール出力を確認したい場合は直接実行
python ui_inventory.py
```

## アーキテクチャ

### 主要コンポーネント

```
ui_inventory.py     メインウィンドウ（キャラ選択、ストレージタブ、Search All）
  └─ ui_gearset.py  GearSet Builder（装備セット構築、Luaプレビュー）

live_data.py        VanaExport JSON ローダー（LiveDataLoader, LiveItem）
inventory.py        dat ファイル直接パーサー（InventoryParser）

windower_addon/
  └─ VanaExport.lua  Windower アドオン（//vex all でJSON出力）

tools/
  ├─ generate_item_db.py   items.lua から items.db を生成
  └─ parse_equipset.py     ゲーム内装備セット（es*.dat）パーサー

data/
  └─ items.db              アイテム名辞書 SQLite DB
```

### データフロー

1. FFXI内で `//vex all` を実行 → `VanaExport/data/{キャラ名}_inventory.json` 出力
2. `LiveDataLoader` が JSON を読み込み、`items.db` で情報を補完
3. `ui_inventory.py` が PyQt6 でGUI表示

### 重要な型定義

- `LiveItem` (live_data.py): アイテム情報のデータクラス
  - `id`, `name`, `name_en`, `count`, `slot`, `storage` 等のフィールドを持つ
  - DB から補完される `category`, `item_type`, `skill`, `slots` も含む
- `LiveDataLoader` (live_data.py): JSON読み込みとDB補完を行うローダー
  - `load_character(name)`: キャラクター名から JSON を読み込み
  - `list_characters()`: 利用可能なキャラクターリストを返す
- `GearSetBuilderWindow` (ui_gearset.py): 装備セットビルダーウィンドウ
  - ドラッグ＆ドロップで装備セット構築
  - GearSwap Lua 形式でエクスポート可能
- `InventoryParser` (inventory.py): dat ファイル直接パーサー（現在は Search All のみで使用）

### PyQt6 UI 構造

- メインウィンドウ (`ui_inventory.py`):
  - 左ペイン: キャラクター選択リスト
  - 中央: 2段タブ構成のストレージビュー（上段: メインストレージ、下段: Wardrobe 1-8）
  - 右ペイン: アイテム詳細表示（説明文、装備可能ジョブ、オーグメント等）
  - ヘッダー: Search All 検索欄、再読込ボタン、装備セットボタン
- GearSet Builder (`ui_gearset.py`):
  - 左: 所持品リスト（ドラッグ元）
  - 中央: 16スロット装備グリッド（ドロップ先）
  - 右上: 装備セット一覧
  - 右下: Lua プレビュー＆コピー

## 開発ルール

### コーディング規約

- PyQt6 のシグナル/スロット接続は `.connect()` を使用
- アイテム表示は常に日本語名を優先し、英語名は補足として併記
- DB アクセスは例外処理を行い、DB がなくても動作するようにする（アイテム名が表示されないだけ）

### 参照用・資料フォルダ

`参照用・資料フォルダ/` は**参考資料専用**です:
- 読み取り専用として扱う
- import や依存関係を作らない
- このフォルダがなくてもアプリは動作する必要がある

### items.db 更新

アイテムDB を更新するには:

```powershell
# 1. Windower の items.lua を tools/ フォルダに配置
# 2. 以下のコマンドで items.db を生成
python tools/generate_item_db.py

# または入力ファイルを明示的に指定
python tools/generate_item_db.py --input tools/items.lua
```

生成された `data/items.db` は約23,000件のアイテムデータを含む SQLite データベースです。

### データベーススキーマ

```sql
-- items テーブル
CREATE TABLE items (
    id INTEGER PRIMARY KEY,      -- アイテムID
    name_ja TEXT,                -- 日本語名
    name_en TEXT,                -- 英語名
    category TEXT,               -- カテゴリ (Weapon/Armor/General/etc.)
    type INTEGER,                -- タイプ (武器: スキルID, 防具: スロットビット)
    skill INTEGER,               -- 武器スキル (武器のみ)
    slots INTEGER                -- 装備スロット (防具のみ)
);
```

### 装備セットファイル

GearSet Builder は以下のファイル形式を使用:
- ゲーム内装備セット: FFXI の `USER/{キャラID}/es*.dat` ファイル（バイナリ）
- 名前マッピング: `names.ini` でキャラクターフォルダIDと表示名を管理
- エクスポート形式: GearSwap Lua コード（テキスト）

## FFXIゲーム内での使用

### VanaExport アドオン設置

1. `windower_addon/VanaExport.lua` を `Windower/addons/VanaExport/` に配置
2. `Windower/addons/VanaExport/data/` フォルダを作成
3. ゲーム内でロード＆エクスポート:
   ```
   //lua load VanaExport
   //vex all
   ```

### トラブルシューティング

**問題: アイテム名が表示されない**
- `data/items.db` が存在するか確認
- DB がない場合は `python tools/generate_item_db.py` で生成

**問題: キャラクターが表示されない**
- VanaExport の `data` フォルダパスが正しく設定されているか確認
- `{キャラ名}_inventory.json` が存在するか確認
- ゲーム内で `//vex all` を実行済みか確認

**問題: 装備セットが読み込めない**
- FFXI の `USER` フォルダパスが正しいか確認
- キャラクターフォルダ（16進数ID）に `es*.dat` が存在するか確認
