# VanaExport - Windower Addon

VanaInventory用のWindowerアドオン。実行中のFFXIからインベントリ・装備データをJSONでエクスポートします。

## インストール

1. `VanaExport.lua` を Windowerの `addons/VanaExport/` フォルダにコピー
2. `data/` フォルダを作成
3. ゲーム内で `//lua load VanaExport` でロード

```
Windower4/
└── addons/
    └── VanaExport/
        ├── VanaExport.lua
        └── data/           ← JSONファイルが出力される
```

## コマンド

| コマンド | 説明 |
|---------|------|
| `//vex all` | 全インベントリをエクスポート |
| `//vex equip` | 現在の装備のみエクスポート |
| `//vex auto` | ゾーン移動時の自動エクスポートON/OFF |
| `//vex help` | ヘルプ表示 |

## 出力ファイル

- `data/{キャラ名}_inventory.json` - 全データ
- `data/{キャラ名}_equipment.json` - 装備のみ

## JSONフォーマット

```json
{
  "version": "1.0",
  "export_time": "2024-12-07 12:34:56",
  "player": {
    "name": "Charname",
    "id": 12345678,
    "main_job": "WAR",
    "main_job_level": 99,
    "sub_job": "NIN",
    "sub_job_level": 49
  },
  "equipment": {
    "main": {
      "id": 20000,
      "name": "ナエグリング",
      "name_en": "Naegling",
      "count": 1,
      "slot": 1,
      "augments": ["Accuracy+20", "Attack+20"]
    },
    ...
  },
  "storages": {
    "Inventory": {
      "name": "Inventory",
      "bag_id": 0,
      "max_slots": 80,
      "items": [...]
    },
    "Wardrobe": {...},
    ...
  }
}
```

## VanaInventoryとの連携

VanaInventoryの `live_data.py` がこのJSONを読み込みます。

1. ゲーム内で `//vex all` を実行
2. VanaInventoryで「ライブデータ読み込み」

## 対応ストレージ

- Inventory
- Mog Safe / Safe 2
- Storage
- Locker
- Satchel / Sack / Case
- Wardrobe 1-8
