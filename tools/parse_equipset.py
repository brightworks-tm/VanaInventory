"""
FFXI Equipment Set .dat Parser
装備セット es0.dat ~ es9.dat を解析するツール

■ファイル構造 (1624バイト):
- ヘッダー: 24バイト (0x00-0x17)
- セット × 20: 各80バイト (0x50)

■各セット構造 (80バイト):
- オフセット 0x00-0x0F: セット名 (16バイト, null終端文字列)
- オフセット 0x10-0x4F: 装備データ (16スロット × 4バイト = 64バイト)

■各スロット (4バイト):
- バイト0: ストレージID (バッグID、0x20オフセットあり)
- バイト1: バッグ内インデックス (1-based)
- バイト2-3: アイテムID (little-endian uint16)

■ファイル対応表:
es0.dat: 装備セット 1～20
es1.dat: 装備セット 21～40
...
es9.dat: 装備セット 181～200
"""

import sys
import struct
from pathlib import Path
from typing import Dict, List, Any, Optional

# ファイル構造定数
HEADER_SIZE = 24      # ヘッダーサイズ
SET_SIZE = 80         # 各セットのサイズ
SET_COUNT = 20        # 1ファイルあたりのセット数
SLOT_COUNT = 16       # 各セットのスロット数
SLOT_SIZE = 4         # 各スロットのサイズ
SET_NAME_SIZE = 16    # セット名のサイズ
EQUIPMENT_OFFSET = 16 # セット内の装備データ開始オフセット

# ストレージID（バッグID）のマッピング
# FFXIクライアント内で使用される可能性のあるID
# 実際の値は 0x20 オフセットを含む場合あり
STORAGE_IDS = {
    0: "Inventory",
    1: "Safe",
    2: "Storage",
    3: "Temp",
    4: "Locker",
    5: "Satchel",
    6: "Sack",
    7: "Case",
    8: "Wardrobe 1",
    9: "Safe 2",
    10: "Wardrobe 2",
    11: "Wardrobe 3",
    12: "Wardrobe 4",
    13: "Wardrobe 5",
    14: "Wardrobe 6",
    15: "Wardrobe 7",
    16: "Wardrobe 8",
    17: "Recycle Bin",
    # 特殊値（実際に観測されたID）
    21: "Wardrobe 5",    # 0x15 - Wardrobe系?
    25: "Wardrobe ?",    # 0x19
    33: "Safe",          # 0x21 - 0x20 offset?
    41: "Safe 2",        # 0x29 - 0x20 offset?
}

def get_storage_name(storage_id: int) -> str:
    """ストレージIDから名前を取得"""
    # 0x20オフセットの可能性を考慮
    if storage_id in STORAGE_IDS:
        return STORAGE_IDS[storage_id]
    
    # 0x20を引いてみる
    adjusted = storage_id - 0x20
    if adjusted in STORAGE_IDS:
        return f"{STORAGE_IDS[adjusted]} (+0x20)"
    
    # 下位5ビットを取ってみる
    masked = storage_id & 0x1F
    if masked in STORAGE_IDS:
        return f"{STORAGE_IDS[masked]} (masked)"
    
    return f"Unknown({storage_id})"

# スロット定義（FFXIの装備スロット順）
EQUIPMENT_SLOTS = [
    "main",    # メイン
    "sub",     # サブ
    "range",   # 遠隔
    "ammo",    # 矢弾
    "head",    # 頭
    "body",    # 胴
    "hands",   # 両手
    "legs",    # 両脚
    "feet",    # 両足
    "neck",    # 首
    "waist",   # 腰
    "ear1",    # 左耳
    "ear2",    # 右耳
    "ring1",   # 左手指
    "ring2",   # 右手指
    "back",    # 背
]

SLOT_NAMES_JP = {
    "main": "メイン",
    "sub": "サブ",
    "range": "遠隔",
    "ammo": "矢弾",
    "head": "頭",
    "body": "胴",
    "hands": "両手",
    "legs": "両脚",
    "feet": "両足",
    "neck": "首",
    "waist": "腰",
    "ear1": "左耳",
    "ear2": "右耳",
    "ring1": "左手指",
    "ring2": "右手指",
    "back": "背",
}


def decode_set_name(raw: bytes) -> str:
    """セット名をデコード"""
    try:
        null_idx = raw.find(b'\x00')
        if null_idx >= 0:
            raw = raw[:null_idx]
        return raw.decode('shift_jis', errors='replace').strip()
    except:
        return ""


def parse_slot_data(slot_bytes: bytes) -> Dict[str, Any]:
    """スロットデータを解析
    
    構造:
    - バイト0: ストレージID
    - バイト1: バッグ内インデックス
    - バイト2-3: アイテムID (little-endian)
    """
    if len(slot_bytes) < 4:
        return {"storage_id": 0, "index": 0, "item_id": 0, "empty": True}
    
    storage_id = slot_bytes[0]
    bag_index = slot_bytes[1]
    item_id = struct.unpack('<H', slot_bytes[2:4])[0]
    
    is_empty = (storage_id == 0 and item_id == 0)
    
    return {
        "storage_id": storage_id,
        "storage_name": get_storage_name(storage_id),
        "bag_index": bag_index,
        "item_id": item_id,
        "raw": slot_bytes.hex(),
        "empty": is_empty
    }


def parse_equipment_set(set_data: bytes, set_index: int) -> Dict[str, Any]:
    """単一の装備セットを解析"""
    result = {
        "index": set_index,
        "name": "",
        "slots": {},
    }
    
    if len(set_data) < SET_SIZE:
        result["error"] = f"データサイズ不足: {len(set_data)} bytes"
        return result
    
    # セット名 (オフセット 0、16バイト)
    name_raw = set_data[0:SET_NAME_SIZE]
    result["name"] = decode_set_name(name_raw)
    
    # 装備スロット (オフセット 16から64バイト)
    for i, slot_key in enumerate(EQUIPMENT_SLOTS):
        slot_start = EQUIPMENT_OFFSET + (i * SLOT_SIZE)
        slot_end = slot_start + SLOT_SIZE
        slot_bytes = set_data[slot_start:slot_end]
        result["slots"][slot_key] = parse_slot_data(slot_bytes)
    
    return result


def parse_equipset_file(filepath: Path, file_index: int = 0, item_dict: Dict[int, str] = None) -> Dict[str, Any]:
    """装備セットファイルを解析"""
    if not filepath.exists():
        return {"error": f"File not found: {filepath}"}
    
    data = filepath.read_bytes()
    
    result = {
        "filename": filepath.name,
        "file_size": len(data),
        "file_index": file_index,
        "set_range_start": file_index * SET_COUNT + 1,
        "set_range_end": (file_index + 1) * SET_COUNT,
        "sets": [],
        "header": data[:HEADER_SIZE].hex() if len(data) >= HEADER_SIZE else data.hex(),
    }
    
    # 各セットを解析
    for set_idx in range(SET_COUNT):
        set_start = HEADER_SIZE + (set_idx * SET_SIZE)
        set_end = set_start + SET_SIZE
        
        if set_end <= len(data):
            set_data = data[set_start:set_end]
            set_info = parse_equipment_set(set_data, set_idx + 1)
            set_info["global_index"] = file_index * SET_COUNT + set_idx + 1
            
            # アイテム名を追加
            if item_dict:
                for slot_key, slot_data in set_info.get("slots", {}).items():
                    item_id = slot_data.get("item_id", 0)
                    if item_id > 0:
                        slot_data["item_name"] = item_dict.get(item_id, f"Unknown Item ({item_id})")
            
            result["sets"].append(set_info)
    
    return result


def parse_all_equipset_files(folder: Path, item_dict: Dict[int, str] = None) -> List[Dict[str, Any]]:
    """フォルダ内の全es*.datを解析"""
    results = []
    
    for i in range(10):
        filename = f"es{i}.dat"
        filepath = folder / filename
        
        if filepath.exists():
            result = parse_equipset_file(filepath, i, item_dict)
            results.append(result)
        else:
            results.append({
                "filename": filename,
                "file_index": i,
                "set_range_start": i * SET_COUNT + 1,
                "set_range_end": (i + 1) * SET_COUNT,
                "exists": False
            })
    
    return results


def load_character_equipsets(char_folder: Path, item_dict: Dict[int, str] = None) -> List[Dict[str, Any]]:
    """キャラクターフォルダから全装備セットをロード（UI向け）"""
    return parse_all_equipset_files(char_folder, item_dict)



def print_detailed_analysis(results: List[Dict[str, Any]], show_empty: bool = False) -> None:
    """詳細な解析結果を表示"""
    print("=" * 80)
    print("FFXI Equipment Set Analysis - 装備セット解析")
    print("=" * 80)
    
    for file_result in results:
        print(f"\n{'=' * 70}")
        print(f"File: {file_result.get('filename', 'N/A')}")
        print(f"Set Range: {file_result.get('set_range_start', '?')} ～ {file_result.get('set_range_end', '?')}")
        print(f"{'=' * 70}")
        
        if file_result.get("exists") == False:
            print("  (ファイルが存在しません)")
            continue
        
        if "error" in file_result:
            print(f"  Error: {file_result['error']}")
            continue
        
        print(f"  File Size: {file_result.get('file_size', 0):,} bytes")
        
        sets = file_result.get("sets", [])
        
        for eq_set in sets:
            has_items = any(
                not slot.get("empty", True) 
                for slot in eq_set.get("slots", {}).values()
            )
            
            if not has_items and not show_empty:
                continue
            
            set_name = eq_set.get('name', '(unnamed)')
            if not set_name:
                set_name = "(unnamed)"
            print(f"\n  --- Set #{eq_set.get('global_index', eq_set.get('index', '?'))}: {set_name} ---")
            
            slots = eq_set.get("slots", {})
            for slot_key in EQUIPMENT_SLOTS:
                slot_info = slots.get(slot_key, {})
                
                if slot_info.get("empty", True) and not show_empty:
                    continue
                
                slot_name = SLOT_NAMES_JP.get(slot_key, slot_key)
                item_id = slot_info.get("item_id", 0)
                item_name = slot_info.get("item_name", "")
                storage_name = slot_info.get("storage_name", "?")
                bag_index = slot_info.get("bag_index", 0)
                
                if slot_info.get("empty", True):
                    print(f"    {slot_name:8s}: (空)")
                else:
                    name_display = f" [{item_name}]" if item_name else ""
                    print(f"    {slot_name:8s}: ID={item_id:5d}{name_display}")
                    print(f"              Storage={storage_name}, Idx={bag_index}")


def load_item_dictionary(db_path: Path) -> Dict[int, str]:
    """アイテム辞書をロード"""
    if not db_path.exists():
        return {}
    
    try:
        import sqlite3
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, name_ja FROM items")
        mapping = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()
        return mapping
    except Exception as e:
        print(f"Warning: Could not load item dictionary: {e}")
        return {}


def export_to_json(results: List[Dict[str, Any]], output_path: Path) -> None:
    """JSON形式でエクスポート"""
    import json
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"Exported to {output_path}")


def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='FFXI Equipment Set Parser')
    parser.add_argument('path', help='Path to es*.dat file or USER folder')
    parser.add_argument('--all', '-a', action='store_true', help='Show empty sets/slots')
    parser.add_argument('--json', '-j', type=str, help='Export to JSON file')
    parser.add_argument('--db', type=str, help='Path to items.db for item names')
    
    args = parser.parse_args()
    
    target = Path(args.path)
    
    # アイテム辞書をロード
    item_dict = {}
    if args.db:
        item_dict = load_item_dictionary(Path(args.db))
    else:
        # デフォルトパスを試す
        default_db = Path(__file__).parent.parent / "data" / "items.db"
        if default_db.exists():
            item_dict = load_item_dictionary(default_db)
    
    if target.is_file():
        file_index = 0
        if target.stem.startswith("es") and target.stem[2:].isdigit():
            file_index = int(target.stem[2:])
        
        result = parse_equipset_file(target, file_index, item_dict)
        results = [result]
    elif target.is_dir():
        results = parse_all_equipset_files(target, item_dict)
    else:
        print(f"Error: {target} is not a valid file or directory")
        sys.exit(1)
    
    print_detailed_analysis(results, show_empty=args.all)
    
    if args.json:
        export_to_json(results, Path(args.json))


if __name__ == "__main__":
    main()
