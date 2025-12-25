import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QListWidget,
    QListWidgetItem,
    QTabWidget,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QLineEdit,
    QHeaderView,
    QSplitter,
    QCheckBox,
    QPushButton,
    QStackedWidget,
    QMessageBox,
    QFileDialog,
    QComboBox,
    QStatusBar,
    QFrame,
    QScrollArea,
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor

from inventory import get_seiton_priority  # get_seiton_priorityのみ必要
from ui_gearset import GearSetBuilderWindow
from live_data import LiveDataLoader, LiveItem

# 武器スキルID
WEAPON_TYPES = {
    1: "格闘", 2: "短剣", 3: "片手剣", 4: "両手剣", 5: "片手斧", 6: "両手斧",
    7: "両手鎌", 8: "両手槍", 9: "片手刀", 10: "両手刀", 11: "片手棍", 12: "両手棍",
    25: "弓術", 26: "射撃", 27: "投てき",
    41: "楽器", 42: "楽器", 45: "楽器",
    48: "釣り具",
}

# 防具スロット（ビットマスク）
ARMOR_TYPES = {
    1: "メイン", 2: "盾", 4: "遠隔", 8: "矢弾",
    16: "頭", 32: "胴", 64: "両手", 128: "両脚", 256: "両足",
    512: "首", 1024: "腰",
    2048: "耳", 4096: "耳", 6144: "耳",  # 6144 = 2048+4096 (左右)
    8192: "指", 16384: "指", 24576: "指",  # 24576 = 8192+16384 (左右)
    32768: "背",
}

# その他アイテムタイプ（VanaExportの定義不明時は一旦既存のものを参考に）
GENERAL_TYPES = {
    32: "一般アイテム", 33: "使用可能アイテム", 34: "クリスタル", 35: "カード",
    36: "呪具", 37: "人形", 38: "花器", 39: "一般家具",
}

# ジョブのビットフラグ
JOB_NAMES = {
    1: "戦", 2: "モ", 3: "白", 4: "黒", 5: "赤", 6: "シ",
    7: "ナ", 8: "暗", 9: "獣", 10: "吟", 11: "狩", 12: "侍",
    13: "忍", 14: "竜", 15: "召", 16: "青", 17: "コ", 18: "か",
    19: "踊", 20: "学", 21: "風", 22: "剣",
}

def format_item_type(item_type: Optional[int], category: str = "Unknown") -> str:
    """アイテムタイプを文字列に変換
    武器: skill (スキルID)
    防具: slots (ビットマスク)
    """
    if item_type is None:
        return ""
    
    if category == "Weapon":
        return WEAPON_TYPES.get(item_type, f"Wep:{item_type}")
    elif category == "Armor":
        # 完全一致をチェック
        if item_type in ARMOR_TYPES:
            return ARMOR_TYPES[item_type]
        # ビットマスクでマッチング（複数スロットに対応）
        # 優先順位の高い順にチェック（大きい値から）
        matches = []
        remaining_bits = item_type
        for mask, name in sorted(ARMOR_TYPES.items(), reverse=True):
            if remaining_bits & mask:
                matches.append(name)
                remaining_bits &= ~mask  # マッチしたビットをクリア
        if matches:
            # 複数の場合は「・」で結合（例: 「頭・胴」）
            return "・".join(matches)
        return f"Arm:{item_type}"

    # その他（既知の一般種別のみ表示、未知は空）
    return GENERAL_TYPES.get(item_type, "")

def format_jobs(jobs) -> str:
    """ジョブビットフラグ、辞書、または配列を文字列に変換（例: "戦赤シ"）"""
    if jobs is None:
        return ""
    
    windower_to_jp = {
        "WAR": "戦", "MNK": "モ", "WHM": "白", "BLM": "黒", "RDM": "赤", "THF": "シ",
        "PLD": "ナ", "DRK": "暗", "BST": "獣", "BRD": "吟", "RNG": "狩", "SAM": "侍",
        "NIN": "忍", "DRG": "竜", "SMN": "召", "BLU": "青", "COR": "コ", "PUP": "か",
        "DNC": "踊", "SCH": "学", "GEO": "風", "RUN": "剣",
    }
    
    job_id_to_jp = {
        1: "戦", 2: "モ", 3: "白", 4: "黒", 5: "赤", 6: "シ",
        7: "ナ", 8: "暗", 9: "獣", 10: "吟", 11: "狩", 12: "侍",
        13: "忍", 14: "竜", 15: "召", 16: "青", 17: "コ", 18: "か",
        19: "踊", 20: "学", 21: "風", 22: "剣",
    }
    
    job_order = ["戦", "モ", "白", "黒", "赤", "シ", "ナ", "暗", "獣", "吟", "狩",
                 "侍", "忍", "竜", "召", "青", "コ", "か", "踊", "学", "風", "剣"]
    
    job_list = []
    
    if isinstance(jobs, list):
        for job_item in jobs:
            if isinstance(job_item, int):
                if job_item in job_id_to_jp:
                    job_list.append(job_id_to_jp[job_item])
            elif isinstance(job_item, str):
                job_key = job_item.upper()
                if job_key in windower_to_jp:
                    job_list.append(windower_to_jp[job_key])
    elif isinstance(jobs, dict):
        for job_key, enabled in jobs.items():
            if enabled and str(job_key).upper() in windower_to_jp:
                job_list.append(windower_to_jp[str(job_key).upper()])
    elif isinstance(jobs, int):
        if jobs != 0:
            for bit, job_name in JOB_NAMES.items():
                if jobs & (1 << (bit - 1)):
                    job_list.append(job_name)
    
    if job_list:
        job_list_sorted = sorted(job_list, key=lambda x: job_order.index(x) if x in job_order else 999)
        return "".join(job_list_sorted)
    
    return ""


# =========================
# FFXI風UI
# =========================

FFXI_STYLE = """
    QMainWindow, QWidget#MainContent {
        background-color: #000028;
    }
    QWidget {
        color: #ffffff;
        font-family: "Meiryo", "Arial";
        font-size: 12px;
    }
    QFrame#Panel {
        background-color: rgba(0, 0, 40, 200);
        border: 1px solid #4444aa;
        border-radius: 4px;
    }
    QGroupBox {
        border: 1px solid #4444aa;
        border-radius: 4px;
        margin-top: 8px;
        padding-top: 10px;
        font-weight: bold;
        color: #aaaaff;
    }
    QGroupBox::title {
        subcontrol-origin: margin;
        subcontrol-position: top left;
        padding: 0 3px;
        left: 10px;
        background-color: #000028;
    }
    QLabel#StatusLabel {
        color: #ccccff;
        font-weight: bold;
    }
    QLabel#StatusValue {
        color: #ffffff;
        font-weight: bold;
    }
    QLabel#StatusValueBoost {
        color: #00ff00;
        font-weight: bold;
    }
    QLabel#ItemName {
        color: #ffffff;
        font-weight: bold;
    }
    QPushButton {
        background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #333377, stop:1 #111155);
        border: 1px solid #5555aa;
        border-radius: 3px;
        padding: 4px 8px;
        color: white;
    }
    QPushButton:hover {
        background-color: #444488;
        border: 1px solid #7777cc;
    }
    QPushButton:pressed {
        background-color: #111144;
    }
    QTableWidget {
        background-color: rgba(0, 0, 30, 220);
        gridline-color: #333366;
        color: white;
        border: 1px solid #4444aa;
        selection-background-color: #444488;
        selection-color: #ffffff;
    }
    QHeaderView::section {
        background-color: #111144;
        color: #aaaaff;
        border: 1px solid #333366;
        padding: 2px;
    }
    QLineEdit, QComboBox {
        background-color: #000044;
        border: 1px solid #4444aa;
        color: white;
        padding: 2px;
        border-radius: 2px;
    }
    QComboBox QAbstractItemView {
        background-color: #000033;
        color: white;
        border: 1px solid #4444aa;
        selection-background-color: #444488;
        selection-color: white;
    }
    QScrollBar:vertical {
        border: none;
        background: #000022;
        width: 10px;
        margin: 0px;
    }
    QScrollBar::handle:vertical {
        background: #333366;
        min-height: 20px;
        border-radius: 5px;
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
"""


class StatusPanel(QFrame):
    """左側のステータスパネル"""

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self.setFixedWidth(220)
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(4)

        self.name_label = QLabel("Unknown")
        self.name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #aaaaff;")
        layout.addWidget(self.name_label)

        self.job_label = QLabel("??? / ???")
        self.job_label.setStyleSheet("font-size: 12px; color: #ffffff;")
        layout.addWidget(self.job_label)

        self.ilv_label = QLabel("ILv: ???")
        self.ilv_label.setStyleSheet("color: #ffff00;")
        layout.addWidget(self.ilv_label)

        layout.addSpacing(10)

        self.hp_label = self._create_resource_label("HP", "??? / ???")
        layout.addLayout(self.hp_label)
        self.mp_label = self._create_resource_label("MP", "??? / ???")
        layout.addLayout(self.mp_label)
        self.tp_label = self._create_resource_label("TP", "0")
        layout.addLayout(self.tp_label)

        layout.addSpacing(10)

        stats_widget = QWidget()
        stats_layout = QGridLayout(stats_widget)
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(2)

        self.stats_labels = {}
        stats_keys = ["STR", "DEX", "VIT", "AGI", "INT", "MND", "CHR"]

        for i, key in enumerate(stats_keys):
            lbl_name = QLabel(key)
            lbl_name.setStyleSheet("color: #aaaaff;")
            stats_layout.addWidget(lbl_name, i, 0)

            lbl_val = QLabel("???")
            lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.stats_labels[key] = lbl_val
            stats_layout.addWidget(lbl_val, i, 1)

            lbl_boost = QLabel("")
            lbl_boost.setStyleSheet("color: #00ff00;")
            lbl_boost.setAlignment(Qt.AlignmentFlag.AlignRight)
            stats_layout.addWidget(lbl_boost, i, 2)

        layout.addWidget(stats_widget)

        layout.addSpacing(10)

        att_layout = QHBoxLayout()
        att_layout.addWidget(QLabel("攻撃力"))
        self.attack_label = QLabel("???")
        self.attack_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        att_layout.addWidget(self.attack_label)
        layout.addLayout(att_layout)

        def_layout = QHBoxLayout()
        def_layout.addWidget(QLabel("防御力"))
        self.defense_label = QLabel("???")
        self.defense_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        def_layout.addWidget(self.defense_label)
        layout.addLayout(def_layout)

        layout.addStretch()

    def _create_resource_label(self, name, value):
        layout = QHBoxLayout()
        lbl_name = QLabel(name)
        lbl_name.setStyleSheet("color: #aaaaff; font-weight: bold;")
        layout.addWidget(lbl_name)

        lbl_val = QLabel(value)
        lbl_val.setStyleSheet("color: #ffffff; font-weight: bold;")
        lbl_val.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(lbl_val)

        setattr(self, f"{name.lower()}_val_label", lbl_val)
        return layout

    def update_info(self, player_info: Dict[str, Any]):
        if not player_info:
            return

        self.name_label.setText(player_info.get("name", "Unknown"))

        main = player_info.get("main_job", "???")
        main_lv = player_info.get("main_job_level", "??")
        sub = player_info.get("sub_job", "???")
        sub_lv = player_info.get("sub_job_level", "??")
        self.job_label.setText(f"{main} Lv{main_lv} / {sub} Lv{sub_lv}")

        self.hp_val_label.setText(f"{player_info.get('hp', '???')} / {player_info.get('max_hp', '???')}")
        self.mp_val_label.setText(f"{player_info.get('mp', '???')} / {player_info.get('max_mp', '???')}")
        self.tp_val_label.setText(str(player_info.get("tp", 0)))

        stats = player_info.get("stats", {})
        for key, label in self.stats_labels.items():
            val = stats.get(key.lower(), "???")
            label.setText(str(val))

        self.attack_label.setText(str(player_info.get("attack", "???")))
        self.defense_label.setText(str(player_info.get("defense", "???")))


class EquipmentSlotWidget(QFrame):
    """装備スロット表示"""

    def __init__(self, slot_key, slot_name):
        super().__init__()
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setStyleSheet(
            """
            EquipmentSlotWidget {
                background-color: rgba(0, 0, 0, 50);
                border: 1px solid #4444aa;
                border-radius: 4px;
            }
            EquipmentSlotWidget:hover {
                border: 1px solid #8888ff;
                background-color: rgba(50, 50, 100, 50);
            }
        """
        )
        self.setFixedSize(90, 90)
        self.slot_key = slot_key

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        self.name_label = QLabel(slot_name)
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("color: #8888cc; font-size: 10px;")
        layout.addWidget(self.name_label)

        self.item_label = QLabel("")
        self.item_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.item_label.setWordWrap(True)
        self.item_label.setStyleSheet("color: #ffffff; font-size: 11px; font-weight: bold;")
        layout.addWidget(self.item_label)

    def set_item(self, item: Optional[LiveItem]):
        if item:
            self.item_label.setText(item.name_en or item.name)
        else:
            self.item_label.setText("")


class EquipmentGridPanel(QFrame):
    """中央の装備グリッド（4x4）"""

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        title = QLabel("Equipment")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #aaaaff;")
        layout.addWidget(title)

        grid_layout = QGridLayout()
        grid_layout.setSpacing(6)

        self.slots = {}

        layout_map = [
            ["main", "sub", "range", "ammo"],
            ["head", "neck", "ear1", "ear2"],
            ["body", "hands", "ring1", "ring2"],
            ["back", "waist", "legs", "feet"],
        ]

        display_names = {
            "main": "Main",
            "sub": "Sub",
            "range": "Range",
            "ammo": "Ammo",
            "head": "Head",
            "neck": "Neck",
            "ear1": "Ear1",
            "ear2": "Ear2",
            "body": "Body",
            "hands": "Hands",
            "ring1": "Ring1",
            "ring2": "Ring2",
            "back": "Back",
            "waist": "Waist",
            "legs": "Legs",
            "feet": "Feet",
        }

        for row, cols in enumerate(layout_map):
            for col, key in enumerate(cols):
                slot_widget = EquipmentSlotWidget(key, display_names[key])
                grid_layout.addWidget(slot_widget, row, col)
                self.slots[key] = slot_widget

        layout.addLayout(grid_layout)
        layout.addStretch()

    def update_equipment(self, equipment: Dict[str, LiveItem]):
        for key, widget in self.slots.items():
            widget.set_item(equipment.get(key))


class ItemDetailPanel(QFrame):
    """下部のアイテム詳細パネル"""

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self.setFixedHeight(180)
        self.setup_ui()

    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        icon_label = QLabel("Icon")
        icon_label.setFixedSize(64, 64)
        icon_label.setStyleSheet(
            "border: 1px solid #666; background-color: #000; color: #666; qproperty-alignment: AlignCenter;"
        )
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()

        self.name_label = QLabel("No Item Selected")
        self.name_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        text_layout.addWidget(self.name_label)

        self.meta_label = QLabel("")
        self.meta_label.setStyleSheet("color: #aaaaff;")
        text_layout.addWidget(self.meta_label)

        self.desc_scroll = QScrollArea()
        self.desc_scroll.setWidgetResizable(True)
        self.desc_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.desc_scroll.setStyleSheet("background: transparent;")

        self.desc_label = QLabel("")
        self.desc_label.setWordWrap(True)
        self.desc_label.setStyleSheet("color: #ffffff; padding: 5px;")
        self.desc_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.desc_scroll.setWidget(self.desc_label)
        text_layout.addWidget(self.desc_scroll)

        layout.addLayout(text_layout)

    def set_item(self, item: Optional[LiveItem]):
        if not item:
            self.name_label.setText("No Item Selected")
            self.meta_label.setText("")
            self.desc_label.setText("")
            return

        name = item.name_en or item.name
        self.name_label.setText(name)

        meta_parts = [f"ID: {item.id}", item.category]

        if item.category == "Weapon":
            type_str = format_item_type(item.skill, item.category)
        elif item.category == "Armor":
            type_str = format_item_type(item.slots, item.category)
        else:
            type_str = format_item_type(item.item_type, item.category)
        if type_str:
            meta_parts.append(type_str)

        if item.level:
            meta_parts.append(f"Lv{item.level}")
        if item.item_level:
            meta_parts.append(f"<ItemLevel:{item.item_level}>")

        jobs_str = format_jobs(item.jobs)
        if jobs_str:
            meta_parts.append(f"~{jobs_str}")

        if item.storage:
            meta_parts.append(item.storage)

        self.meta_label.setText(" | ".join(meta_parts))

        desc = ""
        if item.description:
            desc += item.description + "\n"
        elif item.description_en:
            desc += item.description_en + "\n"

        if item.augments:
            desc += "\n[Augments]\n"
            for aug in item.augments:
                desc += f" {aug}\n"

        self.desc_label.setText(desc)


class InventoryListPanel(QFrame):
    """右側のインベントリリスト"""

    def __init__(self, parent_window):
        super().__init__()
        self.setObjectName("Panel")
        self.parent_window = parent_window
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        filter_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search...")
        self.search_edit.textChanged.connect(self.parent_window.apply_filters)
        filter_layout.addWidget(self.search_edit)

        self.category_combo = QComboBox()
        self.category_combo.addItems(["All", "Weapon", "Armor", "Item", "Crystal", "Furnishing", "Plant"])
        self.category_combo.currentTextChanged.connect(self.parent_window.apply_filters)
        filter_layout.addWidget(self.category_combo)

        layout.addLayout(filter_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Item Name", "Location"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)

        layout.addWidget(self.table)

        self.count_label = QLabel("0 items")
        self.count_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.count_label.setStyleSheet("color: #aaaaff;")
        layout.addWidget(self.count_label)

    def on_selection_changed(self):
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            self.parent_window.detail_panel.set_item(item)


class LiveInventoryWindow(QMainWindow):
    """ライブデータ専用インベントリビューア (FFXI Style)"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VanaInventory Live (FFXI Style)")
        self.resize(1280, 800)

        self.loader = LiveDataLoader()
        self.current_char: Optional[str] = None
        self.all_items: List[LiveItem] = []

        self.setup_ui()
        self.check_data_path()

    def setup_ui(self):
        self.setStyleSheet(FFXI_STYLE)

        central = QWidget()
        central.setObjectName("MainContent")
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Character:"))
        self.char_combo = QComboBox()
        self.char_combo.setMinimumWidth(150)
        self.char_combo.currentTextChanged.connect(self.on_character_changed)
        toolbar.addWidget(self.char_combo)

        self.reload_btn = QPushButton("Refresh")
        self.reload_btn.clicked.connect(self.reload_data)
        toolbar.addWidget(self.reload_btn)

        toolbar.addStretch()

        self.gearset_btn = QPushButton("GearSet Builder")
        self.gearset_btn.clicked.connect(self.open_gearset_builder)
        toolbar.addWidget(self.gearset_btn)

        main_layout.addLayout(toolbar)

        content_splitter = QSplitter(Qt.Orientation.Vertical)

        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        self.status_panel = StatusPanel()
        top_layout.addWidget(self.status_panel)

        self.grid_panel = EquipmentGridPanel()
        top_layout.addWidget(self.grid_panel, 1)

        self.list_panel = InventoryListPanel(self)
        top_layout.addWidget(self.list_panel)

        content_splitter.addWidget(top_widget)

        self.detail_panel = ItemDetailPanel()
        content_splitter.addWidget(self.detail_panel)

        content_splitter.setSizes([600, 200])
        main_layout.addWidget(content_splitter)

        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

    def check_data_path(self):
        if self.loader.data_path and self.loader.data_path.exists():
            self.refresh_characters()
            return

        default_paths = [
            Path("C:/tool/windower/addons/VanaExport/data"),
            Path("D:/windower/addons/VanaExport/data"),
            Path("E:/windower/addons/VanaExport/data"),
            Path("C:/Program Files (x86)/Windower4/addons/VanaExport/data"),
        ]
        for path in default_paths:
            if path.exists():
                self.loader.set_data_path(str(path))
                self.refresh_characters()
                return

        self.set_data_path(show_message=False)

    def set_data_path(self, show_message: bool = False):
        current_path = str(self.loader.data_path) if self.loader.data_path else ""
        folder = QFileDialog.getExistingDirectory(
            self,
            "VanaExportデータフォルダを選択",
            current_path if current_path else str(Path.home()),
        )
        if not folder:
            self.statusbar.showMessage("Data path not found. Please set VanaExport data path.")
            return

        self.loader.set_data_path(folder)
        self.refresh_characters()
        if show_message:
            QMessageBox.information(self, "データパス設定", f"データパスを設定しました:\n{folder}")

    def refresh_characters(self):
        self.char_combo.clear()
        chars = self.loader.get_available_characters()
        if chars:
            self.char_combo.addItems(chars)

    def on_character_changed(self, char_name: str):
        if not char_name:
            return

        self.current_char = char_name
        data = self.loader.load_character_data(char_name)

        if data:
            player = self.loader.get_player_info()
            self.status_panel.update_info(player)

            equipment = self.loader.get_current_equipment()
            self.grid_panel.update_equipment(equipment)

            self.all_items = self.loader.get_all_items()
            self.apply_filters()

            self.statusbar.showMessage(f"Loaded {char_name}")

    def apply_filters(self):
        search_text = self.list_panel.search_edit.text().lower()
        category_filter = self.list_panel.category_combo.currentText()

        filtered_items = []
        for item in self.all_items:
            name = (item.name_en or item.name).lower()
            if search_text and search_text not in name:
                continue
            if category_filter != "All" and item.category != category_filter:
                continue
            filtered_items.append(item)

        filtered_items.sort(key=lambda x: get_seiton_priority(x.id, x.category, x.item_type, x.skill, x.slots))

        table = self.list_panel.table
        table.setRowCount(0)
        table.setRowCount(len(filtered_items))

        for i, item in enumerate(filtered_items):
            name_item = QTableWidgetItem(item.name_en or item.name)
            name_item.setData(Qt.ItemDataRole.UserRole, item)
            table.setItem(i, 0, name_item)

            loc_item = QTableWidgetItem(item.storage)
            if item.storage == "Equipped":
                loc_item.setForeground(QColor("#00ff00"))
            elif "Wardrobe" in item.storage:
                loc_item.setForeground(QColor("#aaaaff"))
            table.setItem(i, 1, loc_item)

        self.list_panel.count_label.setText(f"{len(filtered_items)} items")

    def reload_data(self):
        self.refresh_characters()
        if self.current_char:
            self.on_character_changed(self.current_char)

    def open_gearset_builder(self):
        if not self.current_char:
            return

        if getattr(self, "gearset_window", None) is not None and self.gearset_window.isVisible():
            self.gearset_window.showNormal()
            self.gearset_window.raise_()
            self.gearset_window.activateWindow()
            return

        items = self.loader.get_equipment_items()
        items.sort(key=lambda x: get_seiton_priority(x.id, x.category, x.item_type, x.skill, x.slots))

        self.gearset_window = GearSetBuilderWindow(items, parser=None, live_loader=self.loader)
        self.gearset_window.setWindowTitle(f"GearSet Builder - {self.current_char}")

        equipment = self.loader.get_current_equipment()
        for slot_name, item in equipment.items():
            self.gearset_window.gearset_panel.set_equipment(slot_name, item)

        self.gearset_window.show()


class InventoryWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VanaInventory Viewer")
        self.resize(1200, 800)
        
        self.loader = LiveDataLoader()
        self.current_char_name: Optional[str] = None
        
        # ストレージ名のマッピング（Windowerアドオン名 -> UI表示名）
        # スクリーンショットの順序に合わせて短縮形を使用
        self.STORAGE_NAME_MAPPING = {
            "Inventory": "Inventory",
            "Safe": "Safe",
            "Storage": "Storage",
            "Locker": "Locker",
            "Satchel": "Satchel",
            "Sack": "Sack",
            "Case": "Case",
            "Safe 2": "Safe2",
            "Wardrobe": "Wardrobe 1",
            "Wardrobe 2": "Wardrobe 2",
            "Wardrobe 3": "Wardrobe 3",
            "Wardrobe 4": "Wardrobe 4",
            "Wardrobe 5": "Wardrobe 5",
            "Wardrobe 6": "Wardrobe 6",
            "Wardrobe 7": "Wardrobe 7",
            "Wardrobe 8": "Wardrobe 8",
        }
        
        # 表示順序（スクリーンショットの順序に合わせる）
        # 上段: Inventory → Safe → Safe2 → Storage → Locker → Satchel → Sack → Case
        # 下段: Wardrobe 1-8（WR1-8として表示）
        self.STORAGE_DISPLAY_ORDER = [
            "Inventory",
            "Safe",
            "Safe2",
            "Storage",
            "Locker",
            "Satchel",
            "Sack",
            "Case",
            "Wardrobe 1",
            "Wardrobe 2",
            "Wardrobe 3",
            "Wardrobe 4",
            "Wardrobe 5",
            "Wardrobe 6",
            "Wardrobe 7",
            "Wardrobe 8",
        ]
        
        self.setup_ui()
        self.check_data_path()
        self.load_characters()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # Splitter for Character List vs Content
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # Left Side: Character List
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.addWidget(QLabel("Characters"))
        
        self.char_list = QListWidget()
        self.char_list.currentItemChanged.connect(self.on_character_selected)
        left_layout.addWidget(self.char_list)
        
        splitter.addWidget(left_panel)

        # Right Side: Inventory Content
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Header area with search
        header_layout = QHBoxLayout()
        self.char_info_label = QLabel("Select a character")
        self.char_info_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header_layout.addWidget(self.char_info_label)
        
        header_layout.addStretch()

        # せいとんボタン（FFXIルールでソート）
        self.seiton_button = QPushButton("せいとん")
        self.seiton_button.setToolTip("FFXIの「せいとん」順に並べ替え\n"
                                       "(クリスタル→薬品→武器→防具→素材)\n"
                                       "武器: 格闘→短剣→片手剣→両手剣→片手斧→両手斧→\n"
                                       "両手槍→両手鎌→片手刀→両手刀→片手棍→両手棍→\n"
                                       "投てき→弓術→射撃→楽器→風水鈴→釣り具→獣餌→グリップ\n"
                                       "防具: 盾→頭→胴→両手→両脚→両足→首→腰→背→耳→指輪")
        self.seiton_button.clicked.connect(self.on_seiton_clicked)
        header_layout.addWidget(self.seiton_button)
        
        # ソート状態を管理
        self.seiton_mode = False
        
        # 装備のみ表示（Weapon/Armor）
        self.equipment_only_checkbox = QCheckBox("装備のみ")
        self.equipment_only_checkbox.setChecked(False)
        self.equipment_only_checkbox.stateChanged.connect(self.on_filter_toggled)
        header_layout.addWidget(self.equipment_only_checkbox)
        
        # GearSetBuilder起動ボタン
        self.gearset_button = QPushButton("装備セット")
        self.gearset_button.setToolTip("装備セットビルダーを開く")
        self.gearset_button.clicked.connect(self.open_gearset_builder)
        header_layout.addWidget(self.gearset_button)
        
        # 再読込ボタン
        self.reload_button = QPushButton("再読込")
        self.reload_button.setToolTip("VanaExportデータを再読み込み\n(Windower addon: //vex all)")
        self.reload_button.clicked.connect(self.reload_data)
        header_layout.addWidget(self.reload_button)
        
        header_layout.addWidget(QLabel("Search:"))
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Item name or ID...")
        self.search_box.textChanged.connect(self.on_search_changed)
        header_layout.addWidget(self.search_box)
        
        right_layout.addLayout(header_layout)

        # Storage Tabs - 2段構成
        # 上段: メインストレージ（Inventory～Recycle Bin）
        # 下段: ワードローブ（Mog Wardrobe 1-8）
        
        # 共有コンテンツエリア
        self.content_stack = QStackedWidget()
        
        # 上段タブバー
        self.upper_tabs = QTabBar()
        self.upper_tabs.setExpanding(False)
        self.upper_tabs.currentChanged.connect(self.on_upper_tab_changed)
        self.upper_tabs.tabBarClicked.connect(self.on_upper_tab_clicked)
        
        # 下段タブバー（ワードローブ用）
        self.lower_tabs = QTabBar()
        self.lower_tabs.setExpanding(False)
        self.lower_tabs.currentChanged.connect(self.on_lower_tab_changed)
        self.lower_tabs.tabBarClicked.connect(self.on_lower_tab_clicked)
        
        # タブバーのスタイル
        self.tab_style_active = """
            QTabBar::tab {
                padding: 6px 12px;
                margin-right: 2px;
                background: #e0e0e0;
                border: 1px solid #c0c0c0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom: 1px solid #ffffff;
            }
            QTabBar::tab:hover {
                background: #f0f0f0;
            }
        """
        # 非アクティブ時はselectedスタイルを通常と同じに
        self.tab_style_inactive = """
            QTabBar::tab {
                padding: 6px 12px;
                margin-right: 2px;
                background: #e0e0e0;
                border: 1px solid #c0c0c0;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #e0e0e0;
                border: 1px solid #c0c0c0;
            }
            QTabBar::tab:hover {
                background: #f0f0f0;
            }
        """
        self.upper_tabs.setStyleSheet(self.tab_style_active)
        self.lower_tabs.setStyleSheet(self.tab_style_inactive)
        
        # タブとコンテンツのマッピング
        self.tab_content_mapping = {}  # (row, index) -> stack_index
        self.active_tab_row = 0  # 0=上段, 1=下段
        
        # ワードローブのラベル（下段に配置するもの）
        self.wardrobe_labels = {
            "Wardrobe 1", "Wardrobe 2", "Wardrobe 3", "Wardrobe 4",
            "Wardrobe 5", "Wardrobe 6", "Wardrobe 7", "Wardrobe 8"
        }
        
        # ワードローブの短縮表示名
        self.wardrobe_short_names = {
            "Wardrobe 1": "WR1",
            "Wardrobe 2": "WR2", 
            "Wardrobe 3": "WR3",
            "Wardrobe 4": "WR4",
            "Wardrobe 5": "WR5",
            "Wardrobe 6": "WR6",
            "Wardrobe 7": "WR7",
            "Wardrobe 8": "WR8",
        }
        
        right_layout.addWidget(self.upper_tabs)
        right_layout.addWidget(self.lower_tabs)
        right_layout.addWidget(self.content_stack)

        splitter.addWidget(right_panel)
        splitter.setSizes([250, 950])

    def check_data_path(self):
        """データパスを確認して設定"""
        if self.loader.data_path and self.loader.data_path.exists():
            return
        
        # デフォルトパスを試す
        default_paths = [
            Path("C:/tool/windower/addons/VanaExport/data"),
            Path("D:/windower/addons/VanaExport/data"),
            Path("E:/windower/addons/VanaExport/data"),
            Path("C:/Program Files (x86)/Windower4/addons/VanaExport/data"),
        ]
        
        for path in default_paths:
            if path.exists():
                self.loader.set_data_path(str(path))
                return
        
        # パスが見つからない場合は設定ダイアログを表示
        self.set_data_path(show_message=True)

    def set_data_path(self, show_message: bool = False):
        """データパスを設定"""
        current_path = str(self.loader.data_path) if self.loader.data_path else ""
        
        folder = QFileDialog.getExistingDirectory(
            self,
            "VanaExportデータフォルダを選択",
            current_path if current_path else str(Path.home()),
        )
        
        if folder:
            self.loader.set_data_path(folder)
            self.load_characters()
            if show_message:
                QMessageBox.information(
                    self,
                    "データパス設定",
                    f"データパスを設定しました:\n{folder}"
                )

    def reload_data(self):
        """データを再読み込み"""
        if self.current_char_name:
            self.load_inventory(self.current_char_name)

    def load_characters(self):
        """キャラクターリストを読み込み"""
        self.char_list.clear()
        
        if not self.loader.data_path or not self.loader.data_path.exists():
            return

        characters = self.loader.get_available_characters()
        
        for char_name in sorted(characters):
            item = QListWidgetItem(char_name)
            item.setData(Qt.ItemDataRole.UserRole, char_name)
            self.char_list.addItem(item)

    def on_character_selected(self, current: QListWidgetItem, previous: QListWidgetItem):
        if not current:
            return
            
        char_name = current.data(Qt.ItemDataRole.UserRole)
        self.current_char_name = char_name
        self.char_info_label.setText(f"Character: {char_name}")
        self.load_inventory(char_name)

    def _live_item_to_dict(self, live_item: LiveItem, index: int = 0) -> Dict[str, Any]:
        """LiveItemをUIが期待する辞書形式に変換"""
        # Weapon/Armorの場合、説明文を種類・LV・ジョブ・ItemLvに置き換え
        description = live_item.description or ""
        if live_item.category in ("Weapon", "Armor"):
            parts = []
            # 種類
            # 武器の場合はskill、防具の場合はslotsを使用
            if live_item.category == "Weapon":
                item_type_str = format_item_type(live_item.skill, live_item.category)
                # skillで判別できない場合はslotsをフォールバック（遠隔/矢弾、グリップなど）
                if (not item_type_str or item_type_str.startswith("Wep:")) and live_item.slots:
                    # グリップ（2H武器用）の可能性: slot=2 で判別
                    if live_item.slots == 2:
                        item_type_str = "グリップ"
                    else:
                        item_type_str = format_item_type(live_item.slots, "Armor")
            else:  # Armor
                item_type_str = format_item_type(live_item.slots, live_item.category)
            if item_type_str:
                parts.append(item_type_str)
            # LV
            if live_item.level:
                parts.append(f"Lv{live_item.level}～")
            # 装備可能ジョブ
            jobs_str = format_jobs(live_item.jobs)
            if jobs_str:
                parts.append(jobs_str)
            # ItemLv
            if live_item.item_level:
                parts.append(f"ItemLv:{live_item.item_level}")
            description = "　".join(parts) if parts else ""
        
        return {
            "id": live_item.id,
            "name": live_item.name,
            "hex_id": f"0x{live_item.id:04X}",
            "slot": live_item.slot,
            "index": index,
            "category": live_item.category,
            "item_type": live_item.item_type,
            "skill": live_item.skill,
            "slots": live_item.slots,
            "count": live_item.count,
            "description": description,
        }

    def _group_items_by_storage(self, items: List[LiveItem]) -> Dict[str, Dict[str, Any]]:
        """LiveItemのリストをストレージ別にグループ化"""
        storages: Dict[str, List[LiveItem]] = {}
        
        for item in items:
            storage_key = item.storage
            if storage_key not in storages:
                storages[storage_key] = []
            storages[storage_key].append(item)
        
        # 辞書形式に変換（UIが期待する形式）
        result = {}
        for storage_key, item_list in storages.items():
            # Windowerアドオン名をUI表示名に変換
            display_name = self.STORAGE_NAME_MAPPING.get(storage_key, storage_key)
            
            # LiveItemを辞書に変換
            items_dict = []
            for idx, item in enumerate(item_list):
                items_dict.append(self._live_item_to_dict(item, idx))
            
            result[display_name] = {
                "items": items_dict,
                "max_slots": 80,  # デフォルト値（必要に応じてJSONから取得可能）
            }
        
        return result

    def load_inventory(self, char_name: str):
        # タブとコンテンツをクリア
        while self.upper_tabs.count() > 0:
            self.upper_tabs.removeTab(0)
        while self.lower_tabs.count() > 0:
            self.lower_tabs.removeTab(0)
        while self.content_stack.count() > 0:
            widget = self.content_stack.widget(0)
            self.content_stack.removeWidget(widget)
            widget.deleteLater()
        self.tab_content_mapping.clear()
        
        # LiveDataLoaderでデータを読み込み
        data = self.loader.load_character_data(char_name)
        if not data:
            QMessageBox.warning(
                self,
                "データ読み込みエラー",
                f"キャラクター '{char_name}' のデータを読み込めませんでした。\n"
                f"ゲーム内で //vex all を実行してください。"
            )
            return
        
        # 全アイテムを取得してストレージ別にグループ化
        all_items = self.loader.get_all_items()
        storages = self._group_items_by_storage(all_items)

        # 定義順にタブを追加（STORAGE_DISPLAY_ORDERの順序を維持）
        active_storages = []
        
        # 順序通りに追加
        for label in self.STORAGE_DISPLAY_ORDER:
            if label in storages:
                active_storages.append((label, storages[label]))
        
        # マッピング外のものがあれば後ろに追加
        for label, content in storages.items():
            if label not in self.STORAGE_DISPLAY_ORDER:
                active_storages.append((label, content))

        upper_index = 0
        lower_index = 0
        
        for label, content in active_storages:
            filtered_items = self.filter_items(content["items"])
            stack_index = self.add_storage_content(label, filtered_items)
            
            # ワードローブかどうかでタブを振り分け
            if label in self.wardrobe_labels:
                # 短縮名を使用
                short_name = self.wardrobe_short_names.get(label, label)
                self.lower_tabs.addTab(f"{short_name} ({len(filtered_items)})")
                self.tab_content_mapping[(1, lower_index)] = stack_index
                lower_index += 1
            else:
                self.upper_tabs.addTab(f"{label} ({len(filtered_items)})")
                self.tab_content_mapping[(0, upper_index)] = stack_index
                upper_index += 1

        # 初期選択（上段の最初のタブ）
        if self.upper_tabs.count() > 0:
            self.active_tab_row = 0
            self.upper_tabs.setCurrentIndex(0)
            self.on_upper_tab_changed(0)
        elif self.lower_tabs.count() > 0:
            self.active_tab_row = 1
            self.lower_tabs.setCurrentIndex(0)
            self.on_lower_tab_changed(0)

        # フィルタや検索を反映
        self.on_search_changed(self.search_box.text())

    def filter_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """フィルタオプションを適用"""
        result = items
        
        # スロット範囲フィルタ（常に有効）
        result = [item for item in result if 1 <= item.get("slot", -1) <= 80]
        
        # 重複除去（同じスロット番号のアイテムは最初の1つだけ残す、常に有効）
        seen_slots = set()
        unique_items = []
        for item in result:
            slot = item.get("slot", -1)
            if slot > 0:
                if slot not in seen_slots:
                    seen_slots.add(slot)
                    unique_items.append(item)
            else:
                # スロットが無効なものはそのまま追加
                unique_items.append(item)
        result = unique_items
        
        # 装備のみフィルタ
        if self.equipment_only_checkbox.isChecked():
            equipment_items = []
            for item in result:
                category = item.get("category", "Unknown")
                if category in ("Weapon", "Armor"):
                    equipment_items.append(item)
            result = equipment_items
        
        # せいとんモードの場合、FFXIルールでソート
        if self.seiton_mode:
            result = self.sort_by_seiton(result)
        
        return result

    def sort_by_seiton(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """FFXIのせいとん順でソート"""
        def get_sort_key(item):
            item_id = item.get("id", 0)
            category = item.get("category", "Unknown")
            item_type = item.get("item_type", 0)
            skill = item.get("skill")
            slots = item.get("slots")
            return get_seiton_priority(item_id, category, item_type, skill, slots)
        
        return sorted(items, key=get_sort_key)

    def on_seiton_clicked(self):
        """せいとんボタンがクリックされた"""
        self.seiton_mode = not self.seiton_mode
        if self.seiton_mode:
            self.seiton_button.setText("せいとん ✓")
            self.seiton_button.setStyleSheet("background-color: #90EE90;")
        else:
            self.seiton_button.setText("せいとん")
            self.seiton_button.setStyleSheet("")
        
        # 現在のタブ位置を保存
        current_row = self.active_tab_row
        if current_row == 0:
            current_tab_index = self.upper_tabs.currentIndex()
        else:
            current_tab_index = self.lower_tabs.currentIndex()
        
        # 現在のキャラを再描画
        if self.current_char_name:
            self.load_inventory(self.current_char_name)
            # タブ位置を復元
            if current_row == 0 and current_tab_index >= 0 and current_tab_index < self.upper_tabs.count():
                self.upper_tabs.setCurrentIndex(current_tab_index)
                self.on_upper_tab_changed(current_tab_index)
            elif current_row == 1 and current_tab_index >= 0 and current_tab_index < self.lower_tabs.count():
                self.lower_tabs.setCurrentIndex(current_tab_index)
                self.on_lower_tab_changed(current_tab_index)

    def on_upper_tab_clicked(self, index: int):
        """明示的なクリック時にも上段の切替を確実に処理"""
        if index < 0:
            return
        if self.upper_tabs.currentIndex() != index:
            self.upper_tabs.setCurrentIndex(index)
        self.on_upper_tab_changed(index)

    def on_upper_tab_changed(self, index: int):
        """上段タブが選択された"""
        if index < 0:
            return
        self.active_tab_row = 0
        # スタイル切り替え: 上段をアクティブに、下段を非アクティブに
        self.upper_tabs.setStyleSheet(self.tab_style_active)
        self.lower_tabs.setStyleSheet(self.tab_style_inactive)
        # コンテンツを切り替え
        stack_index = self.tab_content_mapping.get((0, index), -1)
        if stack_index >= 0:
            self.content_stack.setCurrentIndex(stack_index)
    
    def on_lower_tab_clicked(self, index: int):
        """明示的なクリック時にも下段の切替を確実に処理"""
        if index < 0:
            return
        if self.lower_tabs.currentIndex() != index:
            self.lower_tabs.setCurrentIndex(index)
        self.on_lower_tab_changed(index)

    def on_lower_tab_changed(self, index: int):
        """下段タブが選択された"""
        if index < 0:
            return
        self.active_tab_row = 1
        # スタイル切り替え: 下段をアクティブに、上段を非アクティブに
        self.lower_tabs.setStyleSheet(self.tab_style_active)
        self.upper_tabs.setStyleSheet(self.tab_style_inactive)
        # コンテンツを切り替え
        stack_index = self.tab_content_mapping.get((1, index), -1)
        if stack_index >= 0:
            self.content_stack.setCurrentIndex(stack_index)

    def add_storage_content(self, label: str, items: List[Dict[str, Any]]) -> int:
        """ストレージのコンテンツを追加し、stack indexを返す"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        table = QTableWidget()
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Slot", "Item Name", "Category", "Count", "Description"])
        
        # 行数設定
        table.setRowCount(len(items))
        
        for row, item in enumerate(items):
            slot_val = item['slot']
            slot_text = str(slot_val) if slot_val > 0 else "-"
            
            # カテゴリ取得（既に辞書に含まれている）
            category = item.get('category', 'Unknown')
            
            # 個数と説明を取得
            count = item.get('count', 1)
            description = item.get('description', '') or ''
            
            # 各セルを作成
            item_slot = QTableWidgetItem(slot_text)
            item_slot.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            item_name = QTableWidgetItem(item['name'])
            # ID検索用にUserRoleとしてIDを保存
            item_name.setData(Qt.ItemDataRole.UserRole, item.get('id', 0))
            
            item_category = QTableWidgetItem(category)
            item_category.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            
            item_count = QTableWidgetItem(str(count))
            item_count.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            
            item_description = QTableWidgetItem(description)
            # 説明文は長い場合があるので、改行を許可
            item_description.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

            # データセット
            table.setItem(row, 0, item_slot)
            table.setItem(row, 1, item_name)
            table.setItem(row, 2, item_category)
            table.setItem(row, 3, item_count)
            table.setItem(row, 4, item_description)

        # スタイリング
        header = table.horizontalHeader()
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch) # Description column stretches
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive) # Name column
        table.setColumnWidth(0, 50)
        table.setColumnWidth(2, 80)
        table.setColumnWidth(3, 60)
        table.setColumnWidth(1, 200)  # Item Name column width
        
        table.setSortingEnabled(True)

        layout.addWidget(table)
        
        # コンテンツスタックに追加
        stack_index = self.content_stack.count()
        self.content_stack.addWidget(tab)
        return stack_index

    def on_search_changed(self, text: str):
        # 現在のタブのテーブルをフィルタリング
        current_widget = self.content_stack.currentWidget()
        if not current_widget:
            return
            
        table = current_widget.findChild(QTableWidget)
        if not table:
            return
            
        search_term = text.lower()
        
        for row in range(table.rowCount()):
            should_show = False
            # Name (col 1), Category (col 2), Count (col 3), Description (col 4), or ID match
            name_item = table.item(row, 1)
            category_item = table.item(row, 2)
            count_item = table.item(row, 3)
            description_item = table.item(row, 4)
            
            if name_item:
                # 名前で検索
                if search_term in name_item.text().lower():
                    should_show = True
                # IDで検索（UserRoleから取得）
                elif search_term and name_item.data(Qt.ItemDataRole.UserRole):
                    item_id = str(name_item.data(Qt.ItemDataRole.UserRole))
                    if search_term in item_id:
                        should_show = True
            if category_item and search_term in category_item.text().lower():
                should_show = True
            if count_item and search_term in count_item.text():
                should_show = True
            if description_item and search_term in description_item.text().lower():
                should_show = True
                
            table.setRowHidden(row, not should_show)

    def on_filter_toggled(self):
        # 現在のタブ位置を保存
        current_row = self.active_tab_row
        if current_row == 0:
            current_tab_index = self.upper_tabs.currentIndex()
        else:
            current_tab_index = self.lower_tabs.currentIndex()
        
        # 現在のキャラを再描画
        if self.current_char_name:
            self.load_inventory(self.current_char_name)
            # タブ位置を復元
            if current_row == 0 and current_tab_index >= 0 and current_tab_index < self.upper_tabs.count():
                self.upper_tabs.setCurrentIndex(current_tab_index)
                self.on_upper_tab_changed(current_tab_index)
            elif current_row == 1 and current_tab_index >= 0 and current_tab_index < self.lower_tabs.count():
                self.lower_tabs.setCurrentIndex(current_tab_index)
                self.on_lower_tab_changed(current_tab_index)

    def open_gearset_builder(self):
        """装備セットビルダーを開く"""
        if not self.current_char_name:
            QMessageBox.warning(self, "警告", "キャラクターを選択してください")
            return

        # すでに開いている場合は再利用して前面に出す
        if getattr(self, "gearset_window", None) is not None and self.gearset_window.isVisible():
            self.gearset_window.showNormal()
            self.gearset_window.raise_()
            self.gearset_window.activateWindow()
            return
        
        # LiveDataLoaderから装備可能アイテムを取得
        equipment_items = self.loader.get_equipment_items()
        
        # GearSetBuilderを開く（ライブモード）
        self.gearset_window = GearSetBuilderWindow(
            equipment_items,
            parser=None,
            live_loader=self.loader,
            char_name=self.current_char_name
        )
        self.gearset_window.setWindowTitle(f"GearSet Builder - {self.current_char_name}")
        
        # 現在の装備をセット
        current_equipment = self.loader.get_current_equipment()
        for slot_name, item in current_equipment.items():
            self.gearset_window.gearset_panel.set_equipment(slot_name, item)
        
        self.gearset_window.show()

if __name__ == "__main__":
    argp = argparse.ArgumentParser()
    argp.add_argument("--ffxi", action="store_true", help="FFXI風UIで起動")
    args = argp.parse_args()

    app = QApplication(sys.argv)
    window = LiveInventoryWindow() if args.ffxi else InventoryWindow()
    window.show()
    sys.exit(app.exec())

