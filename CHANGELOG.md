# Changelog

## [0.9.0] - 2025-12-30

### Added
- **Search All（全キャラクター検索）機能**
  - ヘッダーの「Search All:」欄からアイテム名を入力してEnterで、全キャラクターを横断検索
  - 検索結果はキャラクター × 保管場所 × アイテム単位で集計表示
  - アイテム名は日本語/英語の両方を表示

- **右クリックコンテキストメニュー**
  - インベントリ内のアイテムを右クリックで以下のメニューを表示:
    - 🔍 Search All（全キャラで検索）
    - 📋 アイテム名をコピー
    - 📋 IDをコピー
    - 🌐 FFXIAH
    - 📖 BG-Wiki
    - 📚 FF11用語辞典 (Google検索)

---

## [0.8.0] - 2025-12-22

### Added
- **ゲーム内装備セット統合 (Equipset Integration)**
  - GearSet Builder に「ゲーム内セット」タブを追加し、FFXIの `es*.dat` ファイルから装備セットを直接読み込む機能を実装
  - FFXI `USER` フォルダの自動検出とキャラクターフォルダの選択機能
  - キャラクターフォルダIDに対する「名前変更（表示名設定）」機能を実装（`names.ini` による永続化）
- **UI・利便性の向上**
  - 所持品リストおよびアイテム詳細に、アイテムの現在位置（所持品、金庫等）を表示（日本語表示に対応）
  - GearSet Builder のレイアウト調整（アイテム情報欄を20行に拡大、リストを約10行に固定）

---

## [0.7.0] - 2025-12-19

### Added
- **GearSet Builder の Lua プレビュー機能を大幅改善**
  - GearSwap 標準に近いスロット名（left_ear, right_ring 等）へのマッピング
  - 出力順序を一般的な GearSwap 構成（Main -> Sub -> Range -> Ammo...）に最適化
  - 引用符の使い分け（アイテム名: ダブル、オーグメント: シングル）を適用
  - 不要なエスケープ文字の削除

---

## [0.6.0] - 2025-12-13

### Changed
- README を `ui_inventory.py` の機能のみに刷新
- CHANGELOG を現行機能に即した内容へ整理

---

## [0.5.0] - 2025-12-10

### Changed
- ストレージ名と順序を Windower 実データに合わせて短縮表示  
  （上段: Inventory / Safe / Safe2 / Storage / Locker / Satchel / Sack / Case、下段: Wardrobe 1-8）
- テーブル列を Slot / Item Name / Category / Count / Description に再構成
- 武器は `skill`、防具は `slots` を優先判定し、グリップ/釣り具/楽器系/遠隔・矢弾を正しく表示
- ジョブ表示を配列・辞書・ビットマスクすべてに対応

---

## [0.4.0] - 2025-12-08

### Added
- 3カラム＋下部詳細パネルレイアウト（ステータス、装備グリッド、インベントリリスト）
- アイテム詳細の常時表示（説明文、アイテムLv、装備可能ジョブ、オーグメント）
- VanaExport アドオンで `res.item_descriptions` を取得

### Changed
- 装備グリッドを FFXI 準拠の 4×4 配置に変更
- RUN の日本語略称を「剣」に修正

---

## [0.3.0] - 2025-12-08

### Added
- **VanaExport** Windower アドオン（`//vex all` / `//vex equip`）
- **LiveDataLoader** (`live_data.py`) で JSON を読み込み、items.db で補完
- **GearSet Builder** (`ui_gearset.py`)：16 スロット装備グリッド、GearSwap Lua 出力

---

## [0.2.0] - 2025-12-06

### Added
- 「せいとん」ソート（FFXI 準拠: クリスタル→薬品→武器→防具→素材）
- 2段タブ（メインストレージ / ワードローブ）
- 重複除去チェックボックス
- items.db に skill / slots カラム追加

---

## [0.1.0] - 2025-12-06

### Added
- 初回リリース
- GUI (`ui_inventory.py`) で VanaExport JSON を閲覧
- アイテム名辞書による名前解決（オプション）
