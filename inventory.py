from pathlib import Path
from typing import Dict, Any, Optional, List
import struct
import binascii
import json
import csv
import sqlite3

# アイテム辞書DBのデフォルトパス（プロジェクト内の data/items.db）
# このファイルがなくてもアプリケーションは動作します（アイテム名が表示されないだけ）
DEFAULT_DB_PATH = Path(__file__).parent / "data" / "items.db"

class InventoryParser:
    # 判明しているファイルマッピング
    # ユーザー情報と解析結果からの仮説を含む
    FILE_MAPPING = {
        "is.dat": "Inventory",
        "bs.dat": "Safe",
        "b2.dat": "Safe2",
        "cl.dat": "Storage", 
        "mb.dat": "Locker",
        "sb.dat": "Satchel",
        "sk.dat": "Sack",
        "ca.dat": "Case",
        "d.dat":  "Recycle Bin",
        "wr.dat": "Mog Wardrobe 1",
        "wr_2.dat": "Mog Wardrobe 2",
        "wr_3.dat": "Mog Wardrobe 3",
        "wr_4.dat": "Mog Wardrobe 4",
        "wr_5.dat": "Mog Wardrobe 5",
        "wr_6.dat": "Mog Wardrobe 6",
        "wr_7.dat": "Mog Wardrobe 7",
        "wr_8.dat": "Mog Wardrobe 8",
    }

    def __init__(self, user_path: Optional[str] = None, db_path: Optional[str] = None):
        self.user_path = Path(user_path) if user_path else None
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.item_dict = self._load_item_dictionary()
        self.category_dict = self._load_item_categories()

    def _load_item_dictionary(self) -> Dict[int, str]:
        """アイテム辞書DBからアイテム名を読み込む（オプション機能）"""
        if not self.db_path.exists():
            # DBがなくても動作する - アイテム名は表示されないだけ
            return {}
            
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            # デフォルトは日本語(name_ja)を使用
            cursor.execute("SELECT id, name_ja FROM items")
            mapping = {}
            for item_id, text in cursor.fetchall():
                mapping[item_id] = text
            conn.close()
            return mapping
        except Exception as e:
            print(f"Warning: Could not load item dictionary: {e}")
            return {}

    def _load_item_categories(self) -> Dict[int, tuple]:
        """アイテムのカテゴリ、タイプ、スキル、スロットを読み込む"""
        if not self.db_path.exists():
            return {}
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, type, skill, slots FROM items")
            mapping = {}
            for item_id, category, item_type, skill, slots in cursor.fetchall():
                mapping[item_id] = (category, item_type, skill, slots)
            conn.close()
            return mapping
        except Exception as e:
            print(f"Warning: Could not load item categories: {e}")
            return {}

    def get_item_name(self, item_id: int) -> str:
        return self.item_dict.get(item_id, f"Unknown Item ({item_id})")

    def get_item_category(self, item_id: int) -> tuple:
        """アイテムのカテゴリとタイプを取得"""
        info = self.category_dict.get(item_id, ("Unknown", 0, None, None))
        return (info[0], info[1])  # category, type

    def get_item_skill(self, item_id: int) -> int:
        """武器のスキルIDを取得（武器以外はNoneを返す）"""
        info = self.category_dict.get(item_id, ("Unknown", 0, None, None))
        return info[2] if len(info) > 2 else None

    def get_item_slots(self, item_id: int) -> int:
        """防具のスロット値を取得（装備部位のビットマスク）"""
        info = self.category_dict.get(item_id, ("Unknown", 0, None, None))
        return info[3] if len(info) > 3 else None

    def parse_file(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        .datファイルを読み込み、アイテムリストを返す。
        リストの要素: {'slot': int, 'id': int, 'hex_id': str, 'name': str}
        """
        if not file_path.exists():
            return []

        data = file_path.read_bytes()
        header_size = 16
        rec_size = 8
        
        items = []
        count = (len(data) - header_size) // rec_size
        
        is_sort_file = file_path.name.lower() == "is.dat"
        
        for i in range(count): 
            offset = header_size + i * rec_size
            chunk = data[offset : offset + rec_size]
            
            item_id = struct.unpack_from('<H', chunk, 0)[0]
            param1 = struct.unpack_from('<H', chunk, 2)[0]
            param2 = struct.unpack_from('<I', chunk, 4)[0]
            
            # 有効なアイテムのみ抽出
            if item_id != 0 and item_id != 0xFFFF:
                # スロットIDの判定
                # is.dat以外で、param1が80以下ならそれをスロット番号とみなす
                slot_id = param1 if param1 <= 80 else -1
                
                # is.datの場合は全て出力、それ以外は有効なスロットのみ出力（オプション）
                # ここでは解析のため全て出すが、ビューア表示時はslot_idでソートする
                
                items.append({
                    "index": i,
                    "id": item_id,
                    "hex_id": f"0x{item_id:04X}",
                    "name": self.get_item_name(item_id),
                    "param1": param1,
                    "slot": slot_id,
                    "param2": param2
                })
                    
        return items

    def scan_character(self, char_id: str) -> Dict[str, Any]:
        """指定キャラクターの全インベントリファイルをスキャンする"""
        if not self.user_path:
            return {}
            
        char_dir = self.user_path / char_id
        if not char_dir.exists():
            return {}

        result = {
            "character_id": char_id,
            "storages": {}
        }

        for fname, label in self.FILE_MAPPING.items():
            fpath = char_dir / fname
            if fpath.exists():
                items = self.parse_file(fpath)
                if items:
                    # Slot順にソート（スロットIDが無効なものは後ろへ）
                    items.sort(key=lambda x: x['slot'] if x['slot'] > 0 else 9999)
                    
                    result["storages"][label] = {
                        "filename": fname,
                        "count": len(items),
                        "items": items
                    }
                    
        return result

    def export_to_html(self, data: Dict[str, Any], output_path: str):
        """HTML形式でレポートを出力"""
        char_id = data.get("character_id", "unknown")
        
        html = [
            "<html><head>",
            "<meta charset='utf-8'>",
            "<style>",
            "body { font-family: sans-serif; background: #f0f0f0; padding: 20px; }",
            "h1 { color: #333; }",
            ".storage-box { background: white; margin-bottom: 20px; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }",
            "h2 { border-bottom: 2px solid #eee; padding-bottom: 10px; color: #555; }",
            "table { width: 100%; border-collapse: collapse; font-size: 14px; }",
            "th, td { padding: 8px; text-align: left; border-bottom: 1px solid #ddd; }",
            "th { background-color: #f8f9fa; }",
            ".slot { width: 50px; font-weight: bold; color: #666; }",
            ".id { width: 80px; color: #999; font-family: monospace; }",
            ".name { font-weight: bold; color: #2c3e50; }",
            "</style>",
            f"<title>Inventory Report: {char_id}</title>",
            "</head><body>",
            f"<h1>Character Inventory: {char_id}</h1>"
        ]
        
        # ストレージごとにテーブル作成
        # 定義順に表示したいのでFILE_MAPPINGの順序を参照
        ordered_labels = [v for k, v in self.FILE_MAPPING.items()]
        
        # 実際にデータがあるストレージのみ抽出してソート
        existing_storages = []
        for label in ordered_labels:
            if label in data["storages"]:
                existing_storages.append((label, data["storages"][label]))
        
        # マッピングにないがデータがあるもの（念のため）
        for label, content in data["storages"].items():
            if label not in ordered_labels:
                existing_storages.append((label, content))

        for label, content in existing_storages:
            items = content["items"]
            html.append(f"<div class='storage-box'>")
            html.append(f"<h2>{label} ({content['filename']}) - {len(items)} items</h2>")
            html.append("<table>")
            html.append("<tr><th>Slot</th><th>ID</th><th>Name</th><th>Raw Index</th><th>Param1</th></tr>")
            
            for item in items:
                slot_display = item['slot'] if item['slot'] > 0 else "-"
                html.append(f"<tr>")
                html.append(f"<td class='slot'>{slot_display}</td>")
                html.append(f"<td class='id'>{item['id']}</td>")
                html.append(f"<td class='name'>{item['name']}</td>")
                html.append(f"<td>{item['index']}</td>")
                html.append(f"<td>{item['param1']}</td>")
                html.append(f"</tr>")
            
            html.append("</table></div>")
            
        html.append("</body></html>")
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(html))
        print(f"Exported HTML to {output_path}")

    def export_to_csv(self, data: Dict[str, Any], output_path: str):
        """CSV形式でエクスポート"""
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["Storage", "Filename", "Slot", "ItemID", "HexID", "Name", "RecordIndex", "Param1"])
            
            for storage_name, content in data.get("storages", {}).items():
                fname = content["filename"]
                for item in content["items"]:
                    writer.writerow([
                        storage_name,
                        fname,
                        item["slot"] if item["slot"] > 0 else "",
                        item["id"],
                        item["hex_id"],
                        item["name"],
                        item["index"],
                        item["param1"]
                    ])
        print(f"Exported CSV to {output_path}")


# FFXIの「せいとん」順序定義
# クリスタル → 薬品 → 食事 → 武器 → 防具 → その他素材

# クリスタル関連のID範囲
CRYSTAL_IDS = set(range(4096, 4104))  # 基本クリスタル (炎～闇)
CRYSTAL_IDS.update(range(4238, 4246))  # HQクリスタル (猛火～宵闇)
CRYSTAL_IDS.update(range(6506, 6514))  # 特殊クリスタル (灼熱～常闘)
CLUSTER_IDS = set(range(4104, 4112))   # 塊 (炎の塊～闇の塊)

# 武器スキルのせいとん順序
WEAPON_SKILL_ORDER = {
    1: 0,    # 格闘 (Hand-to-Hand)
    2: 1,    # 短剣 (Dagger)
    3: 2,    # 片手剣 (Sword)
    4: 3,    # 両手剣 (Great Sword)
    5: 4,    # 片手斧 (Axe)
    6: 5,    # 両手斧 (Great Axe)
    8: 6,    # 両手槍 (Polearm)
    7: 7,    # 両手鎌 (Scythe)
    9: 8,    # 片手刀 (Katana)
    10: 9,   # 両手刀 (Great Katana)
    11: 10,  # 片手棍 (Club)
    12: 11,  # 両手棍 (Staff)
    27: 12,  # 投てき (Throwing)
    25: 13,  # 弓術 (Archery)
    26: 14,  # 射撃 (Marksmanship)
    41: 15,  # 楽器/弦楽器 (Stringed Instrument)
    42: 16,  # 楽器/管楽器 (Wind Instrument)
    45: 17,  # 風水鈴 (Handbell)
    48: 18,  # 釣り具 (Fishing)
}

# skill=0のアイテムを分類するためのID範囲
PET_FOOD_START = 17016
PET_FOOD_END = 17900

# 防具スロットのせいとん順序
ARMOR_SLOT_ORDER = {
    2: 0,      # 盾 (Shield)
    16: 1,     # 頭 (Head)
    32: 2,     # 胴 (Body)
    64: 3,     # 両手 (Hands)
    128: 4,    # 両脚 (Legs)
    256: 5,    # 両足 (Feet)
    512: 6,    # 首 (Neck)
    1024: 7,   # 腰 (Waist)
    32768: 8,  # 背 (Back)
    6144: 9,   # 耳 (Ear)
    24576: 10, # 指輪 (Ring)
}


def get_seiton_priority(item_id: int, category: str, item_type: int, skill: int = None, slots: int = None) -> tuple:
    """
    FFXIのせいとん順でソートするための優先度を返す
    Returns: (大カテゴリ順, 小カテゴリ順, アイテムID)
    """
    # クリスタル判定
    if item_type == 8 or item_id in CRYSTAL_IDS:
        return (0, item_id, item_id)
    
    # 塊/クラスター判定
    if item_id in CLUSTER_IDS:
        return (1, item_id, item_id)
    
    # カテゴリ別の基本優先度
    if category == "Usable":
        return (2, item_type, item_id)
    elif category == "Weapon":
        if skill is not None:
            if skill == 0:
                if PET_FOOD_START <= item_id <= PET_FOOD_END:
                    return (3, 19, item_id)
                else:
                    return (3, 20, item_id)
            else:
                skill_order = WEAPON_SKILL_ORDER.get(skill, 99)
                return (3, skill_order, item_id)
        return (3, 99, item_id)
    elif category == "Armor":
        if slots is not None:
            slot_order = ARMOR_SLOT_ORDER.get(slots, 99)
            return (4, slot_order, item_id)
        return (4, 99, item_id)
    elif category == "General":
        return (5, item_type, item_id)
    else:
        return (6, item_type, item_id)
