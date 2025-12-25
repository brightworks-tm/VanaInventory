"""
GearSet Builder UI - 装備セット構築画面
Phase 2: GearSwap Lua生成に向けた装備セット管理
"""

import sys
import configparser
from pathlib import Path
from typing import Dict, Any, List, Optional, TYPE_CHECKING, Union
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFrame,
    QSplitter,
    QGroupBox,
    QScrollArea,
    QComboBox,
    QMessageBox,
    QFileDialog,
    QTextEdit,
    QTabWidget,
    QInputDialog,
)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QFont, QFontMetrics, QDrag, QDragEnterEvent, QDropEvent

# LiveItem型のインポート
from live_data import LiveItem, LiveDataLoader

# ゲーム内装備セットパーサーのインポート
import tools.parse_equipset as parse_equipset

# FFXIの装備スロット定義（画面配置順）
# 左列: Main, Head, Body, Back
# 中左列: Sub, Neck, Hands, Waist
# 中右列: Range, Ear1, Ring1, Legs
# 右列: Ammo, Ear2, Ring2, Feet

class CharacterNameMapper:
    """キャラフォルダIDと表示名のマッピングを管理(names.ini)"""
    def __init__(self, ini_path: Path):
        self.ini_path = ini_path
        self.config = configparser.ConfigParser()
        self.section = "DisplayNames"
        self.load()

    def load(self):
        if self.ini_path.exists():
            try:
                self.config.read(self.ini_path, encoding="utf-8")
            except Exception as e:
                print(f"Warning: Failed to load {self.ini_path}: {e}")
        
        if self.section not in self.config:
            self.config[self.section] = {}

    def get_name(self, folder_id: str) -> str:
        return self.config[self.section].get(folder_id, folder_id)

    def set_name(self, folder_id: str, display_name: str):
        self.config[self.section][folder_id] = display_name
        self.save()

    def save(self):
        try:
            with open(self.ini_path, "w", encoding="utf-8") as f:
                self.config.write(f)
        except Exception as e:
            print(f"Warning: Failed to save {self.ini_path}: {e}")

EQUIPMENT_SLOTS = [
    ("main", "メイン"),
    ("sub", "サブ"),
    ("range", "レンジ"),
    ("ammo", "矢弾"),
    ("head", "頭"),
    ("neck", "首"),
    ("ear1", "耳1"),
    ("ear2", "耳2"),
    ("body", "胴"),
    ("hands", "両手"),
    ("ring1", "指1"),
    ("ring2", "指2"),
    ("back", "背"),
    ("waist", "腰"),
    ("legs", "両脚"),
    ("feet", "両足"),
]

# GearSwap Lua出力用のスロット名マッピング
LUA_SLOT_MAP = {
    "main": "main",
    "sub": "sub",
    "range": "range",
    "ammo": "ammo",
    "head": "head",
    "body": "body",
    "hands": "hands",
    "legs": "legs",
    "feet": "feet",
    "neck": "neck",
    "waist": "waist",
    "ear1": "left_ear",
    "ear2": "right_ear",
    "ring1": "left_ring",
    "ring2": "right_ring",
    "back": "back",
}

# GearSwap Lua出力用の標準的な並び順
LUA_SLOT_ORDER = [
    "main", "sub", "range", "ammo",
    "head", "body", "hands", "legs", "feet",
    "neck", "waist", "ear1", "ear2", "ring1", "ring2", "back"
]

# スロット名からslots値へのマッピング（DBのslotsカラム用）
SLOT_TO_DB_VALUE = {
    "main": 1,      # Main
    "sub": 2,       # Sub/Shield
    "range": 4,     # Range
    "ammo": 8,      # Ammo
    "head": 16,
    "neck": 512,
    "ear1": 6144,   # Ear (両耳共通)
    "ear2": 6144,
    "body": 32,
    "hands": 64,
    "ring1": 24576, # Ring (両指共通)
    "ring2": 24576,
    "back": 32768,
    "waist": 1024,
    "legs": 128,
    "feet": 256,
}

# せいとんソート用にinventoryモジュールをインポート
from inventory import InventoryParser, get_seiton_priority

# ジョブ名（Windowerのres.jobsに準拠）
JOB_NAMES = {
    1: "戦", 2: "モ", 3: "白", 4: "黒", 5: "赤", 6: "シ",
    7: "ナ", 8: "暗", 9: "獣", 10: "吟", 11: "狩", 12: "侍",
    13: "忍", 14: "竜", 15: "召", 16: "青", 17: "コ", 18: "か",
    19: "踊", 20: "学", 21: "風", 22: "剣",
}

# 武器スキルID -> 名称
WEAPON_TYPES = {
    1: "格闘", 2: "短剣", 3: "片手剣", 4: "両手剣", 5: "片手斧", 6: "両手斧",
    7: "両手鎌", 8: "両手槍", 9: "片手刀", 10: "両手刀", 11: "片手棍", 12: "両手棍",
    25: "弓術", 26: "射撃", 27: "投てき",
    41: "楽器", 42: "楽器", 45: "楽器",  # 弦/管/風水鈴をまとめて表示
    48: "釣り具",
}

# 防具スロットビット -> 名称（代表部位のみ）
ARMOR_SLOT_TYPES = {
    1: "メイン", 2: "盾", 4: "遠隔", 8: "矢弾",
    16: "頭", 32: "胴", 64: "両手", 128: "両脚", 256: "両足",
    512: "首", 1024: "腰",
    2048: "耳", 4096: "耳", 6144: "耳",
    8192: "指輪", 16384: "指輪", 24576: "指輪",
    32768: "背",
}


class EquipmentSlotWidget(QFrame):
    """個別の装備スロットウィジェット"""
    
    def __init__(self, slot_key: str, slot_name: str):
        super().__init__()
        self.slot_key = slot_key
        self.slot_name = slot_name
        self.equipped_item: Optional[Dict[str, Any]] = None
        self.clicked_signal = None  # クリック時のコールバック
        
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setLineWidth(1)
        self.setAcceptDrops(True)
        self.setMinimumHeight(50)
        self.setMaximumHeight(60)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(0)
        
        # スロット名ラベル
        self.slot_label = QLabel(slot_name)
        self.slot_label.setFont(QFont("Arial", 8))
        self.slot_label.setStyleSheet("color: #666;")
        layout.addWidget(self.slot_label)
        
        # 装備名ラベル
        self.item_label = QLabel("---")
        self.item_label.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        self.item_label.setWordWrap(True)
        layout.addWidget(self.item_label)
        
        self.update_style()
    
    def set_item(self, item: Optional[Any]):
        """装備をセット（DictまたはLiveItem対応）"""
        self.equipped_item = item
        if item:
            # LiveItemかDictかを判定
            if hasattr(item, 'name'):
                # LiveItem - 日本語名を使用
                name = item.name
            else:
                # Dict
                name = item.get("name", "Unknown")
            self.item_label.setText(name)
        else:
            self.item_label.setText("---")
        self.update_style()
    
    def clear_item(self):
        """装備をクリア"""
        self.set_item(None)
    
    def update_style(self):
        """スタイルを更新"""
        if self.equipped_item:
            self.setStyleSheet("""
                EquipmentSlotWidget {
                    background-color: #e8f4e8;
                    border: 2px solid #4CAF50;
                    border-radius: 4px;
                }
            """)
        else:
            self.setStyleSheet("""
                EquipmentSlotWidget {
                    background-color: #f5f5f5;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                }
                EquipmentSlotWidget:hover {
                    background-color: #e8e8e8;
                    border: 1px dashed #999;
                }
            """)
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """ドラッグされたアイテムが入ってきた"""
        if event.mimeData().hasText():
            event.acceptProposedAction()
    
    def dropEvent(self, event: QDropEvent):
        """アイテムがドロップされた"""
        # TODO: ドロップされたアイテムデータをパースしてセット
        text = event.mimeData().text()
        # 簡易実装: テキストからアイテム情報を復元
        # 実際はJSONなどでシリアライズされたデータを使う
        self.item_label.setText(text)
        event.acceptProposedAction()
    
    def mousePressEvent(self, event):
        """クリック処理"""
        if event.button() == Qt.MouseButton.LeftButton:
            # 左クリック: スロットに紐づく処理（アイテム情報表示やフィルタ切替）
            if self.clicked_signal:
                self.clicked_signal(self)
        elif event.button() == Qt.MouseButton.RightButton:
            # 右クリック: 装備解除
            self.clear_item()
        super().mousePressEvent(event)


# ImportEquipsetDialogはUIに統合されたため削除


class GearSetPanel(QWidget):
    """装備セット全体のパネル（16スロット）"""
    
    def __init__(self, parent_window: Optional['GearSetBuilderWindow'] = None):
        super().__init__()
        self.parent_window = parent_window
        self.slots: Dict[str, EquipmentSlotWidget] = {}
        # ジョブごとに装備セットを保持する: {job_id (None=全ジョブ共通): {set_name: slots}}
        self.gear_sets_by_job: Dict[Optional[int], Dict[str, Dict[str, Any]]] = {}
        self.current_job_id: Optional[int] = None
        self.current_set_name: str = ""  # 現在編集中のセット名
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        
        # セット管理エリア
        set_mgmt_group = QGroupBox("装備セット管理")
        set_mgmt_layout = QVBoxLayout(set_mgmt_group)
        
        # セット名入力とプリセット
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("セット名:"))
        self.set_name_edit = QLineEdit()
        self.set_name_edit.setPlaceholderText("例: TP_Set, WS_Torcleaver, Idle")
        self.set_name_edit.textChanged.connect(self.on_set_name_changed)
        name_layout.addWidget(self.set_name_edit, 1)
        
        # プリセット選択
        self.preset_combo = QComboBox()
        self.preset_combo.addItems([
            "-- プリセット --",
            "TP", "Idle", "DT", "Precast", "Midcast",
            "WS_Resolution", "WS_Dimidiation", "WS_Savage",
            "FastCast", "Cure", "Enhancing", "Nuke"
        ])
        self.preset_combo.currentTextChanged.connect(self.apply_preset_name)
        name_layout.addWidget(self.preset_combo)
        set_mgmt_layout.addLayout(name_layout)
        
        # セットリスト
        list_layout = QHBoxLayout()
        self.set_list_widget = QListWidget()
        self.set_list_widget.setMaximumHeight(100)
        self.set_list_widget.itemClicked.connect(self.load_set_from_list)
        list_layout.addWidget(self.set_list_widget)
        
        # セット操作ボタン
        set_btn_layout = QVBoxLayout()
        self.save_set_btn = QPushButton("保存")
        self.save_set_btn.clicked.connect(self.save_current_set)
        set_btn_layout.addWidget(self.save_set_btn)
        
        self.delete_set_btn = QPushButton("削除")
        self.delete_set_btn.clicked.connect(self.delete_current_set)
        set_btn_layout.addWidget(self.delete_set_btn)
        
        self.new_set_btn = QPushButton("新規")
        self.new_set_btn.clicked.connect(self.new_set)
        set_btn_layout.addWidget(self.new_set_btn)

        set_btn_layout.addStretch()
        list_layout.addLayout(set_btn_layout)
        
        set_mgmt_layout.addLayout(list_layout)
        main_layout.addWidget(set_mgmt_group)
        
        # 装備スロットグリッド（FFXI風配置）
        # 列0: Main, Head, Body, Back, Legs
        # 列1: Sub, Neck, Hands, Waist, Feet
        # 列2: Range, Ear1, Ring1
        # 列3: Ammo, Ear2, Ring2
        slots_group = QGroupBox("装備スロット")
        grid = QGridLayout(slots_group)
        grid.setSpacing(4)
        
        # 列0: 左列
        col0_slots = [
            ("main", 0), ("head", 1), ("body", 2), ("back", 3)
        ]
        for slot_key, row in col0_slots:
            slot_name = dict(EQUIPMENT_SLOTS).get(slot_key, slot_key)
            widget = EquipmentSlotWidget(slot_key, slot_name)
            self.slots[slot_key] = widget
            grid.addWidget(widget, row, 0)
        
        # 列1: 中左列
        col1_slots = [
            ("sub", 0), ("neck", 1), ("hands", 2), ("waist", 3)
        ]
        for slot_key, row in col1_slots:
            slot_name = dict(EQUIPMENT_SLOTS).get(slot_key, slot_key)
            widget = EquipmentSlotWidget(slot_key, slot_name)
            self.slots[slot_key] = widget
            grid.addWidget(widget, row, 1)
        
        # 列2: 中右列
        col2_slots = [
            ("range", 0), ("ear1", 1), ("ring1", 2), ("legs", 3)
        ]
        for slot_key, row in col2_slots:
            slot_name = dict(EQUIPMENT_SLOTS).get(slot_key, slot_key)
            widget = EquipmentSlotWidget(slot_key, slot_name)
            self.slots[slot_key] = widget
            grid.addWidget(widget, row, 2)
        
        # 列3: 右列
        col3_slots = [
            ("ammo", 0), ("ear2", 1), ("ring2", 2), ("feet", 3)
        ]
        for slot_key, row in col3_slots:
            slot_name = dict(EQUIPMENT_SLOTS).get(slot_key, slot_key)
            widget = EquipmentSlotWidget(slot_key, slot_name)
            self.slots[slot_key] = widget
            grid.addWidget(widget, row, 3)
        
        main_layout.addWidget(slots_group)
        
        # Lua出力ボタン
        export_layout = QHBoxLayout()
        
        self.clear_btn = QPushButton("クリア")
        self.clear_btn.clicked.connect(self.clear_all)
        export_layout.addWidget(self.clear_btn)
        
        export_layout.addStretch()
        
        self.copy_btn = QPushButton("コピー")
        self.copy_btn.setToolTip("Luaコードをクリップボードにコピー")
        self.copy_btn.clicked.connect(self.copy_lua_to_clipboard)
        export_layout.addWidget(self.copy_btn)
        
        self.export_btn = QPushButton("Lua保存")
        self.export_btn.setToolTip("GearSwap形式のLuaファイルとして保存")
        self.export_btn.clicked.connect(self.export_to_lua_file)
        export_layout.addWidget(self.export_btn)
        
        main_layout.addLayout(export_layout)
        
        # Lua プレビュー
        preview_group = QGroupBox("Lua コード プレビュー")
        preview_layout = QVBoxLayout(preview_group)
        self.lua_preview = QTextEdit()
        self.lua_preview.setReadOnly(True)
        self.lua_preview.setFont(QFont("Consolas", 10))
        self.lua_preview.setMaximumHeight(200)
        preview_layout.addWidget(self.lua_preview)
        main_layout.addWidget(preview_group)
        
        main_layout.addStretch()
    
    def set_equipment(self, slot_key: str, item: Dict[str, Any]):
        """指定スロットに装備をセット"""
        if slot_key in self.slots:
            self.slots[slot_key].set_item(item)
            self.update_lua_preview()
    
    def clear_all(self):
        """全スロットをクリア"""
        for slot in self.slots.values():
            slot.clear_item()
        self.lua_preview.clear()
    
    def get_equipped_items(self) -> Dict[str, Dict[str, Any]]:
        """現在の装備セットを取得"""
        result = {}
        for key, slot in self.slots.items():
            if slot.equipped_item:
                result[key] = slot.equipped_item
        return result

    def set_job(self, job_id: Optional[int]):
        """編集中のジョブを設定し、セットリストを切り替える"""
        self.current_job_id = job_id
        self.current_set_name = ""
        self.clear_all()
        self._update_set_list()

    def _get_active_sets(self) -> Dict[str, Dict[str, Any]]:
        """現在選択中ジョブのセット辞書を取得（なければ作成）"""
        return self.gear_sets_by_job.setdefault(self.current_job_id, {})
    
    def generate_lua_code(self, mode: str = "single") -> str:
        """Luaコードを生成
        
        Args:
            mode: 'single' = 単一セット, 'gearswap' = GearSwap完全版
        """
        set_name = self.set_name_edit.text().strip() or "NewSet"
        equipped = self.get_equipped_items()

        active_sets = self._get_active_sets()

        if not equipped and not active_sets:
            return "-- No equipment selected"
        
        if mode == "gearswap":
            return self._generate_gearswap_template()
        else:
            return self._generate_single_set(set_name, equipped)
    
    def _generate_single_set(self, set_name: str, equipped: Dict[str, Any]) -> str:
        """単一セットのLuaコードを生成"""
        if not equipped:
            return "-- No equipment selected"
            
        lines = [f"sets['{set_name}'] = {{"]
        
        # 定義された順序に従って出力
        for slot_key in LUA_SLOT_ORDER:
            if slot_key not in equipped:
                continue
            
            item = equipped[slot_key]
            lua_slot = LUA_SLOT_MAP.get(slot_key, slot_key)
            item_name, augments = self._get_item_lua_info(item)
            
            if augments:
                # オーグメント付き
                lines.append(f"    {lua_slot}={{name=\"{item_name}\", augments={{{augments}}}}},")
            else:
                # 通常
                lines.append(f"    {lua_slot}=\"{item_name}\",")
        
        lines.append("}")
        return "\n".join(lines)
    
    def _get_item_lua_info(self, item: Any) -> tuple:
        """アイテムからLua出力用の情報を取得
        
        Returns:
            (item_name, augments_str)
        """
        # LiveItemかDictかを判定
        if hasattr(item, 'name'):
            # LiveItem - 日本語名を使用
            item_name = item.name
            augments = item.augments if hasattr(item, 'augments') else None
        else:
            # Dict
            item_name = item.get("name", "Unknown")
            augments = item.get("augments")
        
        # 特殊文字のエスケープ（ダブルクォートのみ）
        item_name = item_name.replace('"', '\\"')
        
        # オーグメント文字列を生成
        aug_str = ""
        if augments and len(augments) > 0:
            aug_parts = []
            for aug in augments:
                # GearSwapで一般的なシングルクォート形式を使用
                aug_parts.append(f"'{aug}'")
            # 最後にカンマを含めるのがGearSwap流
            aug_str = ",".join(aug_parts) + ","
        
        return item_name, aug_str
    
    def _generate_gearswap_template(self) -> str:
        """GearSwap完全版テンプレートを生成"""
        from datetime import datetime
        lines = [
            "---------------------------------------------------",
            "-- GearSwap Lua - Generated by VanaInventory",
            f"-- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "---------------------------------------------------",
            "",
            "function get_sets()",
            "    sets = {}",
            ""
        ]
        # 全ジョブの保存済みセットを出力
        for job_id, sets in self.gear_sets_by_job.items():
            job_label = JOB_NAMES.get(job_id, "All") if job_id else "All"
            lines.append(f"    -- Job: {job_label}")
            for set_name, set_data in sets.items():
                lines.append(f"    -- {set_name}")
                lines.append(f"    sets['{set_name}'] = {{")
                # 定義された順位に従って出力
                for slot_key in LUA_SLOT_ORDER:
                    if slot_key not in set_data:
                        continue
                    
                    item = set_data[slot_key]
                    lua_slot = LUA_SLOT_MAP.get(slot_key, slot_key)
                    item_name, augments = self._get_item_lua_info(item)
                    
                    if augments:
                        lines.append(f"        {lua_slot}={{name=\"{item_name}\", augments={{{augments}}}}},")
                    else:
                        lines.append(f"        {lua_slot}=\"{item_name}\",")
                lines.append("    }")
                lines.append("")
        
        # 現在のセット（未保存の場合はアクティブジョブに紐付け）
        set_name = self.set_name_edit.text().strip() or "NewSet"
        equipped = self.get_equipped_items()
        active_sets = self._get_active_sets()
        if equipped and set_name not in active_sets:
            lines.append(f"    sets['{set_name}'] = {{")
            # 定義された順位に従って出力
            for slot_key in LUA_SLOT_ORDER:
                if slot_key not in equipped:
                    continue
                    
                item = equipped[slot_key]
                lua_slot = LUA_SLOT_MAP.get(slot_key, slot_key)
                item_name, augments = self._get_item_lua_info(item)
                
                if augments:
                    lines.append(f"        {lua_slot}={{name=\"{item_name}\", augments={{{augments}}}}},")
                else:
                    lines.append(f"        {lua_slot}=\"{item_name}\",")
            lines.append("    }")
            lines.append("")
        
        lines.extend([
            "    return sets",
            "end",
            "",
            "-- Precast",
            "function precast(spell)",
            "    -- FastCast装備などを設定",
            "    -- if spell.action_type == 'Magic' then",
            "    --     equip(sets.FastCast)",
            "    -- end",
            "end",
            "",
            "-- Midcast",
            "function midcast(spell)",
            "    -- 詠唱完了時の装備を設定",
            "end",
            "",
            "-- Aftercast",
            "function aftercast(spell)",
            "    -- 待機装備に戻す",
            "    -- equip(sets.Idle)",
            "end",
        ])
        
        return "\n".join(lines)
    
    def update_lua_preview(self):
        """Luaプレビューを更新"""
        lua_code = self.generate_lua_code()
        self.lua_preview.setText(lua_code)
    
    def copy_lua_to_clipboard(self):
        """LuaコードをクリップボードにコピーConsider"""
        lua_code = self.generate_lua_code(mode="single")
        
        if "No equipment" in lua_code:
            QMessageBox.warning(self, "警告", "装備が選択されていません")
            return
        
        clipboard = QApplication.clipboard()
        clipboard.setText(lua_code)
        QMessageBox.information(self, "完了", "Luaコードをクリップボードにコピーしました")
    
    def export_to_lua_file(self):
        """GearSwap形式でLuaファイルに保存"""
        if not self.gear_sets_by_job and not self.get_equipped_items():
            QMessageBox.warning(self, "警告", "保存する装備セットがありません")
            return
        
        # デフォルトファイル名
        default_name = "GearSwap_" + (self.set_name_edit.text().strip() or "NewSet") + ".lua"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "GearSwap Luaファイルを保存",
            str(Path.home() / "Documents" / default_name),
            "Lua Files (*.lua);;All Files (*)"
        )
        
        if not file_path:
            return
        
        try:
            lua_code = self.generate_lua_code(mode="gearswap")
            Path(file_path).write_text(lua_code, encoding="utf-8")
            QMessageBox.information(self, "完了", f"Luaファイルを保存しました:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"ファイル保存に失敗しました:\n{e}")
    
    def save_current_set(self):
        """現在の装備セットを保存"""
        set_name = self.set_name_edit.text().strip()
        if not set_name:
            QMessageBox.warning(self, "警告", "セット名を入力してください")
            return
        
        equipped = self.get_equipped_items()
        if not equipped:
            QMessageBox.warning(self, "警告", "装備が選択されていません")
            return

        active_sets = self._get_active_sets()
        active_sets[set_name] = equipped.copy()
        self.current_set_name = set_name
        self._update_set_list()
        self.update_lua_preview()
        QMessageBox.information(self, "完了", f"セット '{set_name}' を保存しました")
    
    def delete_current_set(self):
        """現在のセットを削除"""
        set_name = self.set_name_edit.text().strip()
        active_sets = self._get_active_sets()
        if not set_name or set_name not in active_sets:
            QMessageBox.warning(self, "警告", "削除するセットを選択してください")
            return
        
        reply = QMessageBox.question(
            self, "確認", 
            f"セット '{set_name}' を削除しますか?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.set_name_edit.clear()
            self._update_set_list()
    
    def import_ingame_set(self, eq_set: Optional[Dict[str, Any]] = None):
        """パースされた装備セットをインポート"""
        if not eq_set:
            return
            
        # インポート実行
        self.clear_all()
        self.set_name_edit.setText(eq_set.get("name") or f"Imported_Set_{eq_set.get('global_index')}")
        
        # アイテムのマッチングロジック
        self._apply_parsed_set(eq_set)
        
    def _apply_parsed_set(self, eq_set: Dict[str, Any]):
        """パースされた装備セットを画面に反映"""
        if not self.parent_window:
            return
            
        inventory_items = self.parent_window.inventory_items
        slots = eq_set.get("slots", {})
        
        # ストレージ名のマッピング (parse_equipset -> VanaExport)
        storage_map = {
            "Inventory": "Inventory",
            "Wardrobe 1": "Wardrobe",
            "Wardrobe 2": "Wardrobe 2",
            "Wardrobe 3": "Wardrobe 3",
            "Wardrobe 4": "Wardrobe 4",
            "Wardrobe 5": "Wardrobe 5",
            "Wardrobe 6": "Wardrobe 6",
            "Wardrobe 7": "Wardrobe 7",
            "Wardrobe 8": "Wardrobe 8",
            "Safe": "Safe",
            "Safe 2": "Safe 2",
            "Storage": "Storage",
            "Locker": "Locker",
            "Satchel": "Satchel",
            "Sack": "Sack",
            "Case": "Case",
        }
        
        for slot_key, slot_data in slots.items():
            if slot_data.get("empty", True):
                continue
                
            item_id = slot_data.get("item_id")
            bag_index = slot_data.get("bag_index")
            storage_name_raw = slot_data.get("storage_name", "")
            
            # ( +0x20 ) などを除去
            storage_name = storage_name_raw.split(" (")[0]
            mapped_storage = storage_map.get(storage_name, storage_name)
            
            # 在庫からマッチするアイテムを探す
            matched_item = None
            
            # 1. ID + Storage + Index で厳密にマッチング
            for item in inventory_items:
                i_id = item.id if hasattr(item, 'id') else item.get("id")
                i_storage = item.storage if hasattr(item, 'storage') else item.get("storage")
                i_slot = item.slot if hasattr(item, 'slot') else item.get("slot")
                
                # VanaExportの 'slot' は0ベース（要確認）、parse_equipsetの 'bag_index' は1ベース
                # 実装を確認したところ、VanaExport側も0ベースか1ベースか環境によって怪しいが、
                # ここでは bag_index - 1 または bag_index で比較を試みる
                
                if i_id == item_id and i_storage == mapped_storage:
                    # インデックスの不一致は一旦許容する（エクスポート時期によるズレを考慮）
                    # ただし、同じIDが複数ある場合はインデックスを重視
                    if i_slot == bag_index or i_slot == (bag_index - 1):
                        matched_item = item
                        break
            
            # 2. 見つからない場合、IDだけでマッチング（予備）
            if not matched_item:
                for item in inventory_items:
                    i_id = item.id if hasattr(item, 'id') else item.get("id")
                    if i_id == item_id:
                        matched_item = item
                        break
            
            if matched_item:
                # 画面のスロットにセット
                # ui_gearset.py の EQUIPMENT_SLOTS のキーと一致するか確認
                # parse_equipset.EQUIPMENT_SLOTS と ui_gearset.EQUIPMENT_SLOTS はほぼ一致しているが
                # ear1/2 と ring1/2, sub/sub など微妙な違いがある可能性があるため、変換
                ui_slot_key = slot_key
                # ear1 -> ear1, ring1 -> ring1 なのでそのままいけるはず
                
                self.set_equipment(ui_slot_key, matched_item)
            else:
                # アイテムが見つからない場合（所持品にない等）
                item_name = slot_data.get("item_name") or f"ID:{item_id}"
                print(f"Warning: Item not found in inventory: {item_name} (Storage:{mapped_storage}, Index:{bag_index})")

    def new_set(self):
        """新規セットを作成"""
        self.clear_all()
        self.set_name_edit.clear()
        self.current_set_name = ""
    
    def load_set_from_list(self, item: QListWidgetItem):
        """リストからセットを読み込み"""
        set_name = item.text()
        active_sets = self._get_active_sets()
        if set_name in active_sets:
            self.set_name_edit.setText(set_name)
            self.clear_all()
            for slot_key, slot_item in active_sets[set_name].items():
                if slot_key in self.slots:
                    self.slots[slot_key].set_item(slot_item)
            self.current_set_name = set_name
            self.update_lua_preview()
    
    def _update_set_list(self):
        """セットリストを更新"""
        self.set_list_widget.clear()
        active_sets = self._get_active_sets()
        for set_name in sorted(active_sets.keys()):
            self.set_list_widget.addItem(set_name)
    
    def apply_preset_name(self, text: str):
        """プリセット名を適用"""
        if text and text != "-- プリセット --":
            self.set_name_edit.setText(text)
            self.preset_combo.setCurrentIndex(0)
    
    def on_set_name_changed(self):
        """セット名変更時"""
        self.update_lua_preview()


class GearSetBuilderWindow(QMainWindow):
    """装備セットビルダーのメインウィンドウ"""
    
    def __init__(self, inventory_items: List[Union[Dict[str, Any], LiveItem]] = None, 
                 parser: 'InventoryParser' = None,
                 live_loader: 'LiveDataLoader' = None,
                 current_job_id: Optional[int] = None,
                 char_name: str = None):
        super().__init__()
        self.setWindowTitle("GearSet Builder")
        self.resize(1000, 700)
        
        self.parser = parser
        self.live_loader = live_loader
        self.char_name = char_name
        self.is_live_mode = live_loader is not None and parser is None
        self.current_job_id = current_job_id
        self.active_slot_filter: Optional[str] = None  # スロットクリック由来のフィルタ（コンボとは独立）
        
        # せいとん順でソート
        if inventory_items:
            if self.is_live_mode:
                # ライブモード: LiveItemをそのままソート
                self.inventory_items = self.sort_live_items(inventory_items)
            elif parser:
                self.inventory_items = self.sort_by_seiton(inventory_items)
            else:
                self.inventory_items = inventory_items
        else:
            self.inventory_items = []
        
        # キャラ名マッパーの初期化
        db_root = Path(__file__).parent / "data"
        db_root.mkdir(parents=True, exist_ok=True)
        self.name_mapper = CharacterNameMapper(db_root / "names.ini")
        
        self.setup_ui()
    
    def sort_live_items(self, items: List[LiveItem]) -> List[LiveItem]:
        """LiveItemをせいとん順でソート"""
        def get_sort_key(item: LiveItem):
            return get_seiton_priority(
                item.id, 
                item.category, 
                item.item_type, 
                item.skill, 
                item.slots
            )
        return sorted(items, key=get_sort_key)
    
    def sort_by_seiton(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """FFXIのせいとん順でソート"""
        def get_sort_key(item):
            item_id = item.get("id", 0)
            category, item_type = self.parser.get_item_category(item_id)
            skill = self.parser.get_item_skill(item_id)
            slots = self.parser.get_item_slots(item_id)
            return get_seiton_priority(item_id, category, item_type, skill, slots)
        
        return sorted(items, key=get_sort_key)
    
    def setup_ui(self):
        info_font = QFont("Consolas", 10)
        fm = QFontMetrics(info_font)
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        
        # 左パネル: 装備リスト + アイテム情報 (Tab化)
        left_panel = QWidget()
        left_main_layout = QVBoxLayout(left_panel)
        left_main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.left_tabs = QTabWidget()
        
        # --- Tab 1: 所持品リスト ---
        self.inventory_tab = QWidget()
        inv_layout = QVBoxLayout(self.inventory_tab)
        
        inv_layout.addWidget(QLabel("装備一覧 (ダブルクリックで追加)"))
        
        # フィルタ
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("ジョブ:"))
        self.job_filter = QComboBox()
        self.job_filter.addItem("すべて", None)
        for job_id in sorted(JOB_NAMES.keys()):
            self.job_filter.addItem(JOB_NAMES[job_id], job_id)
        self.job_filter.currentIndexChanged.connect(self.on_job_changed)
        filter_layout.addWidget(self.job_filter)

        self.slot_click_clear_btn = QPushButton("スロット解除")
        self.slot_click_clear_btn.setToolTip("スロットクリックによる一時フィルタを解除")
        self.slot_click_clear_btn.clicked.connect(self.clear_slot_click_filter)
        filter_layout.addWidget(self.slot_click_clear_btn)
        
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("検索...")
        self.search_edit.textChanged.connect(self.filter_equipment_list)
        filter_layout.addWidget(self.search_edit)
        
        inv_layout.addLayout(filter_layout)
        self.slot_filter_status = QLabel("表示部位: スロット未選択（すべて）")
        inv_layout.addWidget(self.slot_filter_status)
        
        # 装備リスト
        self.equipment_list = QListWidget()
        self.equipment_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.equipment_list.itemClicked.connect(self.on_item_clicked)
        # 行数目安：10行程度に調整
        self.equipment_list.setFixedHeight(fm.lineSpacing() * 10 + 10)
        inv_layout.addWidget(self.equipment_list, 2)
        
        self.left_tabs.addTab(self.inventory_tab, "所持品リスト")
        
        # --- Tab 2: ゲーム内装備セット ---
        self.ingame_sets_tab = QWidget()
        ingame_layout = QVBoxLayout(self.ingame_sets_tab)
        
        # USERフォルダ選択・キャラ選択
        path_layout = QHBoxLayout()
        self.user_path_edit = QLineEdit()
        # ユーザー指定のデフォルトパス
        import os
        default_user_path = r"C:\Program Files (x86)\PlayOnline\SquareEnix\FINAL FANTASY XI\USER"
        if not Path(default_user_path).exists():
             default_user_path = os.path.expanduser("~") + r"\Documents\My Games\FINAL FANTASY XI\USER"
        
        self.user_path_edit.setText(default_user_path)
        path_layout.addWidget(QLabel("USERパス:"))
        path_layout.addWidget(self.user_path_edit, 1)
        self.browse_user_btn = QPushButton("...")
        self.browse_user_btn.setFixedWidth(30)
        self.browse_user_btn.clicked.connect(self.browse_user_path)
        path_layout.addWidget(self.browse_user_btn)
        ingame_layout.addLayout(path_layout)
        
        char_layout = QHBoxLayout()
        char_layout.addWidget(QLabel("キャラフォルダ:"))
        self.char_folder_combo = QComboBox()
        self.char_folder_combo.currentIndexChanged.connect(self.on_char_folder_changed)
        char_layout.addWidget(self.char_folder_combo, 1)
        
        self.rename_char_btn = QPushButton("名前変更")
        self.rename_char_btn.setToolTip("選択中のフォルダに表示名を付けます")
        self.rename_char_btn.clicked.connect(self.on_rename_character)
        char_layout.addWidget(self.rename_char_btn)
        
        self.refresh_chars_btn = QPushButton("更新")
        self.refresh_chars_btn.clicked.connect(self.refresh_character_folders)
        char_layout.addWidget(self.refresh_chars_btn)
        ingame_layout.addLayout(char_layout)
        
        ingame_layout.addWidget(QLabel("ゲーム内セット一覧 (ダブルクリックで反映):"))
        self.ingame_set_list = QListWidget()
        self.ingame_set_list.itemDoubleClicked.connect(self.on_ingame_set_double_clicked)
        # 行数目安：10行程度に調整
        self.ingame_set_list.setFixedHeight(fm.lineSpacing() * 10 + 10)
        ingame_layout.addWidget(self.ingame_set_list)
        
        self.apply_ingame_btn = QPushButton("選択したセットを反映")
        self.apply_ingame_btn.clicked.connect(self.on_ingame_set_double_clicked)
        ingame_layout.addWidget(self.apply_ingame_btn)
        
        self.left_tabs.addTab(self.ingame_sets_tab, "ゲーム内セット")
        
        left_main_layout.addWidget(self.left_tabs, 2)
        
        # アイテム情報表示エリア (共通)
        info_group = QGroupBox("アイテム情報")
        info_layout = QVBoxLayout(info_group)
        
        self.item_info_text = QTextEdit()
        self.item_info_text.setReadOnly(True)
        self.item_info_text.setFont(info_font)
        # 行数目安：20行に増やしてスクロールなしで見えるように
        self.item_info_text.setFixedHeight(fm.lineSpacing() * 20 + 10)
        info_layout.addWidget(self.item_info_text)
        
        left_main_layout.addWidget(info_group, 1)
        
        layout.addWidget(left_panel, 1)
        
        # 右: 装備セットパネル
        self.gearset_panel = GearSetPanel(self)
        # スロットクリック時にアイテム情報を表示
        for slot_widget in self.gearset_panel.slots.values():
            slot_widget.clicked_signal = self.on_slot_clicked
        layout.addWidget(self.gearset_panel, 1)
        
        # 初期化処理
        self.populate_equipment_list()
        self.refresh_character_folders() # キャラクタフォルダの初期読み込み

        # 初期ジョブを反映
        self.gearset_panel.set_job(self.current_job_id)
        if self.current_job_id:
            idx = self.job_filter.findData(self.current_job_id)
            if idx >= 0:
                self.job_filter.setCurrentIndex(idx)
        else:
            self.job_filter.setCurrentIndex(0)
        self.update_slot_filter_status()
    
    def populate_equipment_list(self):
        """装備リストを表示（装備品のみ）"""
        self.equipment_list.clear()
        # 表示時に改めて「せいとん」順でソート
        if self.is_live_mode:
            items = self.sort_live_items(self.inventory_items)
        elif self.parser:
            items = self.sort_by_seiton(self.inventory_items)
        else:
            items = self.inventory_items

        for item in items:
            # 装備品（Weapon/Armor）のみ表示
            if not self._is_equipment_item(item):
                continue
            
            # LiveItemかDictかを判定
            storage_name = ""
            if isinstance(item, LiveItem):
                display_name = item.name  # 日本語名
                storage_name = item.storage
            else:
                display_name = item.get("name", "Unknown")
                storage_name = item.get("storage", "")
            
            # ストレージ名があれば追加
            if storage_name:
                storage_display = self._get_storage_display_name(storage_name)
                display_name = f"{display_name} ({storage_display})"
            
            list_item = QListWidgetItem(display_name)
            list_item.setData(Qt.ItemDataRole.UserRole, item)
            self.equipment_list.addItem(list_item)
    
    def browse_user_path(self):
        """USERフォルダを選択"""
        selected = QFileDialog.getExistingDirectory(self, "FFXIのUSERフォルダを選択してください", self.user_path_edit.text() or str(Path.home()))
        if selected:
            self.user_path_edit.setText(selected)
            self.refresh_character_folders()

    def refresh_character_folders(self):
        """USERフォルダ直下のキャラフォルダを検索"""
        user_path = Path(self.user_path_edit.text())
        self.char_folder_combo.clear()
        
        if not user_path.exists():
            return
            
        # USER直下のフォルダを全探索
        # 各フォルダの中に es0.dat があれば候補とする
        folders = []
        for p in user_path.iterdir():
            if p.is_dir() and (p / "es0.dat").exists():
                folders.append(p)
        
        if not folders:
            return
            
        # ソートして追加
        for f in sorted(folders, key=lambda x: x.name):
            # 表示名を取得（マッピングがあればそれを使う）
            display_name = self.name_mapper.get_name(f.name)
            if display_name != f.name:
                label = f"{display_name} ({f.name})"
            else:
                label = f.name
            self.char_folder_combo.addItem(label, f)
            
        # もし char_name に基づいて自動選択できるならする
        # (キャラ名とIDの紐付けは別途必要だが、まずは最初の1つを選択)
        if self.char_folder_combo.count() > 0:
            self.char_folder_combo.setCurrentIndex(0)

    def on_char_folder_changed(self, index):
        """キャラフォルダ変更時にセット一覧を読み込む"""
        char_folder = self.char_folder_combo.itemData(index)
        self.ingame_set_list.clear()
        
        if not char_folder:
            return
            
        # アイテムDBのパス
        db_path = Path(__file__).parent / "data" / "items.db"
        item_dict = parse_equipset.load_item_dictionary(db_path)
        
        results = parse_equipset.load_character_equipsets(char_folder, item_dict)
        
        for file_result in results:
            if not file_result.get("exists", True):
                continue
                
            for eq_set in file_result.get("sets", []):
                # 空のセットはスキップ
                has_items = any(not s.get("empty", True) for s in eq_set.get("slots", {}).values())
                if not eq_set.get("name") and not has_items:
                    continue
                
                display_name = f"#{eq_set.get('global_index')}: {eq_set.get('name') or '(名称未設定)'}"
                if has_items:
                    item_count = sum(1 for s in eq_set.get("slots", {}).values() if not s.get("empty", True))
                    display_name += f" ({item_count}部位)"
                
                item = QListWidgetItem(display_name)
                item.setData(Qt.ItemDataRole.UserRole, eq_set)
                self.ingame_set_list.addItem(item)

    def on_rename_character(self):
        """キャラフォルダの表示名を変更"""
        idx = self.char_folder_combo.currentIndex()
        if idx < 0:
            return
            
        char_folder = self.char_folder_combo.itemData(idx)
        if not char_folder:
            return
            
        folder_id = char_folder.name
        current_name = self.name_mapper.get_name(folder_id)
        
        name, ok = QInputDialog.getText(
            self, 
            "キャラクター名の設定", 
            f"フォルダ '{folder_id}' の表示名を入力してください:", 
            text=current_name if current_name != folder_id else ""
        )
        
        if ok:
            self.name_mapper.set_name(folder_id, name if name.strip() else folder_id)
            # 一覧をリフレッシュ（選択状態を維持）
            self.refresh_character_folders()
            # もともとのフォルダを再選択
            new_idx = self.char_folder_combo.findData(char_folder)
            if new_idx >= 0:
                self.char_folder_combo.setCurrentIndex(new_idx)

    def on_ingame_set_double_clicked(self, item=None):
        """ゲーム内セットを反映"""
        if not item:
            item = self.ingame_set_list.currentItem()
        
        if not item:
            return
            
        eq_set = item.data(Qt.ItemDataRole.UserRole)
        if eq_set:
            self.gearset_panel.import_ingame_set(eq_set)
    
    def _is_equipment_item(self, item: Union[Dict[str, Any], LiveItem]) -> bool:
        """アイテムが装備品かどうか判定"""
        if isinstance(item, LiveItem):
            # category: "Weapon", "Armor"（文字列型）
            return item.category in ("Weapon", "Armor")
        else:
            # Dict形式の場合（item_category: 0=Weapon, 1=Armor）
            category = item.get("item_category")
            return category in (0, 1)

    def _get_item_jobs(self, item: Union[Dict[str, Any], LiveItem]):
        """ジョブ情報を取得（ビットフラグ/リスト/辞書いずれか）"""
        if isinstance(item, LiveItem):
            return item.jobs
        if isinstance(item, dict):
            if "jobs" in item:
                return item.get("jobs")
        return None

    def _item_supports_job(self, jobs_data, job_id: Optional[int]) -> bool:
        """指定ジョブで装備可能か判定"""
        if job_id is None:
            return True
        if jobs_data is None:
            return True  # 情報がなければフィルタしない
        # リスト形式
        if isinstance(jobs_data, list):
            return job_id in jobs_data
        # ビットフラグ形式
        if isinstance(jobs_data, int):
            # job_id は 1始まりのため bit は (job_id-1)
            return (jobs_data & (1 << (job_id - 1))) != 0
        # 辞書形式（Windowerのジョブキーなど）
        if isinstance(jobs_data, dict):
            values = list(jobs_data.values())
            keys = list(jobs_data.keys())
            return job_id in values or job_id in keys
        return True

    def _get_storage_display_name(self, storage_name: str) -> str:
        """ストレージ名を日本語表示に変換"""
        mapping = {
            "Inventory": "所持品", 
            "Mog Safe": "金庫", "Mog Safe 2": "金庫2",
            "Mog Locker": "ロッカー", "Mog Satchel": "サッチェル", "Mog Sack": "サック",
            "Mog Case": "ケース", 
            "Wardrobe": "モグワ1", "Wardrobe 2": "モグワ2",
            "Wardrobe 3": "モグワ3", "Wardrobe 4": "モグワ4", "Wardrobe 5": "モグワ5",
            "Wardrobe 6": "モグワ6", "Wardrobe 7": "モグワ7", "Wardrobe 8": "モグワ8"
        }
        return mapping.get(storage_name, storage_name)

    def _format_weapon_type(self, skill: Optional[int]) -> Optional[str]:
        if skill is None:
            return None
        return WEAPON_TYPES.get(skill)

    def _format_armor_slot(self, slots: Optional[int]) -> Optional[str]:
        if slots is None:
            return None
        # 優先度の高いビットを代表として採用
        priority = [
            1, 2, 4, 8, 16, 32, 64, 128, 256,
            512, 1024, 4096, 2048, 6144, 16384, 8192, 24576, 32768
        ]
        for mask in priority:
            if slots & mask:
                name = ARMOR_SLOT_TYPES.get(mask)
                if name:
                    return name
        return None

    def _format_detailed_category(self, item_data: Union[Dict[str, Any], LiveItem], item_info: Dict[str, Any]) -> str:
        """カテゴリを詳細表示（武器種/防具部位）に変換"""
        category = item_info.get("category")
        skill = item_info.get("skill")
        slots = item_info.get("slots")

        # 明示的なカテゴリ判定
        if category == "Weapon" or category == 0:
            detailed = self._format_weapon_type(skill)
            if detailed:
                return detailed
            return "武器"
        if category == "Armor" or category == 1:
            detailed = self._format_armor_slot(slots)
            if detailed:
                return detailed
            return "防具"

        # 不明の場合もスキル/スロットから推定
        detailed = self._format_weapon_type(skill)
        if detailed:
            return detailed
        detailed = self._format_armor_slot(slots)
        if detailed:
            return detailed

        # フォールバック
        if isinstance(category, str):
            return category
        if category is None:
            return "その他"
        return str(category)
    
    def _get_item_info(self, item: Union[Dict[str, Any], LiveItem]) -> Dict[str, Any]:
        """アイテムから統一した情報を取得"""
        if isinstance(item, LiveItem):
            return {
                "id": item.id,
                "name": item.name,  # 日本語名
                "category": item.category,
                "skill": getattr(item, "skill", None),
                "slots": item.slots,
                "storage": item.storage,
                "extdata": item.extdata,
                "augments": item.augments,
            }
        else:
            item_id = item.get("id", 0)
            category = item.get("item_category")
            return {
                "id": item_id,
                "name": item.get("name", "Unknown"),
                "category": category,
                "skill": self.parser.get_item_skill(item_id) if self.parser else item.get("skill"),
                "slots": self.parser.get_item_slots(item_id) if self.parser else item.get("slots"),
                "storage": item.get("storage"),
                "extdata": item.get("extdata"),
                "augments": item.get("augments"),
            }
    
    def filter_equipment_list(self):
        """装備リストをフィルタ"""
        search_text = self.search_edit.text().lower()
        slot_filter = self.active_slot_filter
        job_filter = self.job_filter.currentData()
        
        for i in range(self.equipment_list.count()):
            list_item = self.equipment_list.item(i)
            item_data = list_item.data(Qt.ItemDataRole.UserRole)
            
            # 統一インターフェースでアイテム情報を取得
            item_info = self._get_item_info(item_data)
            item_jobs = self._get_item_jobs(item_data)
            
            # 検索フィルタ
            name_match = search_text in item_info["name"].lower()
            
            # スロットフィルタ
            slot_match = True
            if slot_filter:
                item_slots = item_info["slots"]
                if item_slots:
                    # DBのslots値とフィルタのslots値を比較
                    filter_db_value = SLOT_TO_DB_VALUE.get(slot_filter, 0)
                    # ビットマスクで判定（アイテムが該当スロットに装備可能か）
                    slot_match = (item_slots & filter_db_value) != 0
                else:
                    slot_match = False

            # ジョブフィルタ
            job_match = self._item_supports_job(item_jobs, job_filter)
            
            list_item.setHidden(not (name_match and slot_match and job_match))
        self.update_slot_filter_status()
    
    def on_item_clicked(self, list_item: QListWidgetItem):
        """装備リストのアイテムをクリック時に情報を表示"""
        item_data = list_item.data(Qt.ItemDataRole.UserRole)
        if item_data:
            self.display_item_info(item_data)

    def on_job_changed(self):
        """ジョブ選択変更時: セットをジョブ別に切替えつつリストをフィルタ"""
        job_id = self.job_filter.currentData()
        self.current_job_id = job_id
        self.gearset_panel.set_job(job_id)
        self.filter_equipment_list()

    def clear_slot_click_filter(self):
        """スロットクリック由来の一時フィルタを解除"""
        self.active_slot_filter = None
        self.filter_equipment_list()

    def update_slot_filter_status(self):
        """スロット/コンボのフィルタ状態表示を更新"""
        if self.active_slot_filter:
            slot_name = dict(EQUIPMENT_SLOTS).get(self.active_slot_filter, self.active_slot_filter)
            self.slot_filter_status.setText(f"表示部位: {slot_name}")
        else:
            self.slot_filter_status.setText("表示部位: スロット未選択（すべて）")
    
    def on_slot_clicked(self, slot_widget: 'EquipmentSlotWidget'):
        """装備スロットをクリック時に情報を表示"""
        # スロットクリックによる一時フィルタ適用（コンボ廃止）
        self.active_slot_filter = slot_widget.slot_key
        self.filter_equipment_list()

        # 装備があれば情報表示
        if slot_widget.equipped_item:
            self.display_item_info(slot_widget.equipped_item)
    
    def display_item_info(self, item: Union[Dict[str, Any], LiveItem]):
        """アイテム情報を表示"""
        lines = []
        item_info = self._get_item_info(item)
        category_text = self._format_detailed_category(item, item_info)
        
        # LiveItemかDictかを判定
        if isinstance(item, LiveItem):
            # 名前
            lines.append(f"<b>{item.name}</b>")
            if item.name_en and item.name_en != item.name:
                lines.append(f"<i>{item.name_en}</i>")
            lines.append("")
            
            # レベル・iLv
            if item.level:
                level_str = f"Lv{item.level}"
                if item.item_level:
                    level_str += f"  ItemLv:{item.item_level}"
                lines.append(level_str)
            
            # カテゴリ（詳細表示）
            lines.append(f"カテゴリ: {category_text}")
            
            # ストレージ
            if item.storage:
                storage_display = self._get_storage_display_name(item.storage)
                lines.append(f"所持場所: {storage_display}")
            
            # 装備可能ジョブ
            if item.jobs:
                if isinstance(item.jobs, list):
                    job_names = [JOB_NAMES.get(j, str(j)) for j in item.jobs]
                    lines.append(f"ジョブ: {''.join(job_names)}")
                elif isinstance(item.jobs, int):
                    # ビットフラグの場合
                    job_list = []
                    for i in range(1, 23):
                        if item.jobs & (1 << i):
                            job_list.append(JOB_NAMES.get(i, str(i)))
                    lines.append(f"ジョブ: {''.join(job_list)}")
            
            lines.append("")
            
            # 説明文
            if item.description:
                # 改行を<br>に変換
                desc = item.description.replace("\n", "<br>")
                lines.append(desc)
            
            # オーグメント
            if item.augments and len(item.augments) > 0:
                lines.append("")
                lines.append("<b>オーグメント:</b>")
                for aug in item.augments:
                    lines.append(f"  • {aug}")
        else:
            # Dict形式
            lines.append(f"<b>{item.get('name', 'Unknown')}</b>")
            lines.append("")
            lines.append(f"カテゴリ: {category_text}")
            if item.get("storage"):
                storage_display = self._get_storage_display_name(item.get("storage"))
                lines.append(f"所持場所: {storage_display}")
            if item.get("description"):
                lines.append(item.get("description", ""))
            if item.get("augments"):
                lines.append("")
                lines.append("<b>オーグメント:</b>")
                for aug in item["augments"]:
                    lines.append(f"  • {aug}")
        
        self.item_info_text.setHtml("<br>".join(lines))
    
    def on_item_double_clicked(self, list_item: QListWidgetItem):
        """装備をダブルクリックで追加"""
        item_data = list_item.data(Qt.ItemDataRole.UserRole)
        if not item_data:
            return
        
        # 部位フィルタで選択されているスロットに追加
        slot_key = self.active_slot_filter
        if slot_key and slot_key in self.gearset_panel.slots:
            self.gearset_panel.set_equipment(slot_key, item_data)
        else:
            # スロット未選択時はヒントを表示
            QMessageBox.information(self, "ヒント", "右側の装備スロットをクリックして部位を選択してからダブルクリックしてください")


def main():
    """テスト用"""
    app = QApplication(sys.argv)
    
    # テストデータ
    test_items = [
        {"id": 20000, "name": "タウルスナイフ", "slot": 1},
        {"id": 20001, "name": "ブロンズソード", "slot": 2},
        {"id": 21000, "name": "ブロンズキャップ", "slot": 3},
        {"id": 21001, "name": "ブロンズハーネス", "slot": 4},
    ]
    
    window = GearSetBuilderWindow(test_items)
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
