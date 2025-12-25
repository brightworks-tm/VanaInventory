"""
Live Data Loader - WindowerアドオンVanaExportが出力したJSONを読み込む
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime


# アイテム辞書DBのデフォルトパス
DEFAULT_DB_PATH = Path(__file__).parent / "data" / "items.db"


@dataclass
class ItemInfo:
    """アイテムのDB情報"""
    category: str = "Unknown"
    item_type: int = 0
    skill: Optional[int] = None
    slots: Optional[int] = None


@dataclass
class LiveItem:
    """ライブデータのアイテム"""
    id: int
    name: str
    name_en: str
    count: int
    slot: int
    storage: str
    extdata: Optional[str] = None
    augments: Optional[List[str]] = None
    description: Optional[str] = None
    description_en: Optional[str] = None
    # 詳細情報（ライブデータから取得）
    level: Optional[int] = None
    item_level: Optional[int] = None
    jobs: Optional[Any] = None  # int (ビットフラグ) または dict (Windower形式)
    flags: Optional[int] = None
    # DB補完フィールド（ライブデータがない場合のフォールバック）
    category: str = "Unknown"
    item_type: int = 0
    skill: Optional[int] = None
    slots: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "name_en": self.name_en,
            "count": self.count,
            "slot": self.slot,
            "storage": self.storage,
            "extdata": self.extdata,
            "augments": self.augments,
            "description": self.description,
            "description_en": self.description_en,
            "category": self.category,
            "item_type": self.item_type,
            "skill": self.skill,
            "slots": self.slots,
        }


@dataclass  
class LiveEquipment:
    """現在装備中のアイテム"""
    slot_name: str  # main, sub, head, etc.
    item: LiveItem


class LiveDataLoader:
    """WindowerのVanaExportアドオンが出力したJSONを読み込むクラス"""
    
    # Windowerのデフォルトパス候補
    WINDOWER_PATHS = [
        Path("C:/Program Files (x86)/Windower4/addons/VanaExport/data"),
        Path("D:/Windower4/addons/VanaExport/data"),
        Path("E:/Windower4/addons/VanaExport/data"),
        Path.home() / "Windower4/addons/VanaExport/data",
    ]
    
    def __init__(self, windower_path: Optional[Path] = None, db_path: Optional[Path] = None):
        """
        Args:
            windower_path: Windowerのaddons/VanaExport/data/パス（None時は自動検索）
            db_path: アイテムDBのパス（None時はデフォルトパス）
        """
        self.data_path = windower_path or self._find_data_path()
        self.db_path = db_path or DEFAULT_DB_PATH
        self.current_data: Optional[Dict[str, Any]] = None
        self.last_load_time: Optional[datetime] = None
        # アイテムDB情報をキャッシュ
        self._item_db: Dict[int, ItemInfo] = {}
        self._load_item_db()
    
    def _find_data_path(self) -> Optional[Path]:
        """VanaExportのdataフォルダを自動検索"""
        for path in self.WINDOWER_PATHS:
            if path.exists():
                return path
        return None
    
    def _load_item_db(self):
        """アイテムDBを読み込んでキャッシュ"""
        if not self.db_path or not self.db_path.exists():
            print(f"Warning: Item DB not found at {self.db_path}")
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id, category, type, skill, slots FROM items")
            for item_id, category, item_type, skill, slots in cursor.fetchall():
                self._item_db[item_id] = ItemInfo(
                    category=category or "Unknown",
                    item_type=item_type or 0,
                    skill=skill,
                    slots=slots,
                )
            conn.close()
            print(f"Loaded {len(self._item_db)} items from DB")
        except Exception as e:
            print(f"Warning: Could not load item DB: {e}")
    
    def get_item_info(self, item_id: int) -> ItemInfo:
        """アイテムIDからDB情報を取得"""
        return self._item_db.get(item_id, ItemInfo())
    
    def set_data_path(self, path: str):
        """データパスを手動設定"""
        self.data_path = Path(path)
    
    def get_available_characters(self) -> List[str]:
        """エクスポート済みのキャラクター一覧を取得"""
        if not self.data_path or not self.data_path.exists():
            return []
        
        characters = []
        for json_file in self.data_path.glob("*_inventory.json"):
            char_name = json_file.stem.replace("_inventory", "")
            characters.append(char_name)
        
        return sorted(characters)
    
    def load_character_data(self, char_name: str) -> Optional[Dict[str, Any]]:
        """キャラクターのデータを読み込み"""
        if not self.data_path:
            return None
        
        json_file = self.data_path / f"{char_name}_inventory.json"
        if not json_file.exists():
            return None
        
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                self.current_data = json.load(f)
                self.last_load_time = datetime.now()
                return self.current_data
        except Exception as e:
            print(f"JSON読み込みエラー: {e}")
            return None
    
    def get_player_info(self) -> Optional[Dict[str, Any]]:
        """プレイヤー情報を取得"""
        if not self.current_data:
            return None
        return self.current_data.get("player")
    
    def _create_live_item(self, item_data: Dict[str, Any], storage: str) -> LiveItem:
        """LiveItemを作成しDB情報で補完する"""
        item_id = item_data.get("id", 0)
        db_info = self.get_item_info(item_id)
        
        # ライブデータのitem_typeがあれば優先、なければDBの値を使用
        live_item_type = item_data.get("item_type")
        final_item_type = live_item_type if live_item_type is not None else db_info.item_type
        
        skill_val = item_data.get("item_skill")
        slot_mask = item_data.get("item_slot")
        
        return LiveItem(
            id=item_id,
            name=item_data.get("name", "Unknown"),
            name_en=item_data.get("name_en", "Unknown"),
            count=item_data.get("count", 1),
            slot=item_data.get("slot", 0),
            storage=storage,
            extdata=item_data.get("extdata"),
            augments=item_data.get("augments"),
            description=item_data.get("description"),
            description_en=item_data.get("description_en"),
            # 詳細情報（ライブデータから）
            level=item_data.get("level"),
            item_level=item_data.get("item_level"),
            jobs=item_data.get("jobs"),
            flags=item_data.get("flags"),
            # DB補完フィールド（ライブデータがない場合はDBの値を使用）
            category=db_info.category if db_info.category != "Unknown" else self._map_category(item_data.get("item_category")),
            item_type=final_item_type,
            skill=skill_val if skill_val is not None else db_info.skill,
            slots=slot_mask if slot_mask is not None else db_info.slots,
        )

    def _map_category(self, cat_id: Optional[int]) -> str:
        """WindowerのカテゴリIDを文字列に変換"""
        if cat_id == 0: return "Weapon"
        if cat_id == 1: return "Armor"
        if cat_id == 2: return "General"
        return "Unknown"
    
    def get_current_equipment(self) -> Dict[str, LiveItem]:
        """現在の装備を取得"""
        if not self.current_data:
            return {}
        
        equipment_data = self.current_data.get("equipment", {})
        
        # 空の装備データがJSON配列 [] として読み込まれた場合の対処
        if isinstance(equipment_data, list):
            equipment_data = {}
            
        result = {}
        
        for slot_name, item_data in equipment_data.items():
            result[slot_name] = self._create_live_item(item_data, "Equipped")
        
        return result
    
    def get_all_items(self, include_equipped: bool = True) -> List[LiveItem]:
        """全アイテムを取得"""
        if not self.current_data:
            return []
        
        items = []
        storages = self.current_data.get("storages", {})
        
        for storage_name, storage_data in storages.items():
            for item_data in storage_data.get("items", []):
                items.append(self._create_live_item(item_data, storage_name))
        
        return items
    
    def get_equipment_items(self) -> List[LiveItem]:
        """全ストレージからアイテムを取得（装備セットビルダー用）"""
        if not self.current_data:
            return []
        
        items = []
        storages = self.current_data.get("storages", {})
        
        for storage_name, storage_data in storages.items():
            for item_data in storage_data.get("items", []):
                items.append(self._create_live_item(item_data, storage_name))
        
        return items
    
    def get_items_for_slot(self, slot_value: int) -> List[LiveItem]:
        """特定の装備部位に装備可能なアイテムを取得
        
        Args:
            slot_value: 装備部位のビット値（例: 1=main, 2=sub, 4=range, 8=ammo, 16=head, etc.）
        
        Returns:
            その部位に装備可能なアイテムのリスト
        """
        all_items = self.get_equipment_items()
        result = []
        
        for item in all_items:
            if item.slots is not None and (item.slots & slot_value):
                result.append(item)
        
        return result
    
    def get_export_time(self) -> Optional[str]:
        """エクスポート時刻を取得"""
        if not self.current_data:
            return None
        return self.current_data.get("export_time")
    
    def is_data_fresh(self, max_age_seconds: int = 300) -> bool:
        """データが新鮮か（デフォルト5分以内）"""
        if not self.last_load_time:
            return False
        
        age = (datetime.now() - self.last_load_time).total_seconds()
        return age < max_age_seconds


def main():
    """テスト用"""
    loader = LiveDataLoader()
    
    print(f"Data path: {loader.data_path}")
    
    characters = loader.get_available_characters()
    print(f"Available characters: {characters}")
    
    if characters:
        char = characters[0]
        data = loader.load_character_data(char)
        if data:
            print(f"\nPlayer: {loader.get_player_info()}")
            print(f"Export time: {loader.get_export_time()}")
            
            equipment = loader.get_current_equipment()
            print(f"\nCurrent equipment ({len(equipment)} slots):")
            for slot, item in equipment.items():
                print(f"  {slot}: {item.name}")
            
            all_items = loader.get_all_items()
            print(f"\nTotal items: {len(all_items)}")


if __name__ == "__main__":
    main()
