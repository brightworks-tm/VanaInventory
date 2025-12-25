"""
アイテム辞書DB生成スクリプト

Windower items.luaからアイテムデータを抽出し、
VanaInventory用の軽量DBを生成します。

このスクリプトは開発・更新時に使用します。
生成されたDBはプロジェクトに同梱して配布します。

使用例:
    python tools/generate_item_db.py --input path/to/items.lua
"""

import argparse
import sqlite3
import re
import sys
import datetime
from pathlib import Path

# 出力先
OUTPUT_DB = Path(__file__).parent.parent / "data" / "items.db"


def create_output_db(output_path: Path) -> sqlite3.Connection:
    """出力用DBを作成"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if output_path.exists():
        output_path.unlink()
    
    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE items (
            id INTEGER PRIMARY KEY,
            name_ja TEXT,
            name_en TEXT,
            category TEXT,
            type INTEGER,
            skill INTEGER,
            slots INTEGER
        )
    """)
    
    cursor.execute("""
        CREATE TABLE metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    
    conn.commit()
    return conn


def import_from_windower_lua(input_path: Path, output_conn: sqlite3.Connection):
    """WindowerのLuaファイルからインポート"""
    if not input_path.exists():
        print(f"Error: Input file not found: {input_path}")
        sys.exit(1)
    
    content = input_path.read_text(encoding='utf-8', errors='ignore')
    
    # Luaテーブルをパース（簡易版）
    # 形式: [ID]={en="English Name",ja="日本語名",category="...",type=N,skill=N,...}
    pattern = r'\[(\d+)\]\s*=\s*\{([^}]+)\}'
    matches = re.findall(pattern, content)
    
    items = []
    for item_id, props in matches:
        en_match = re.search(r'en\s*=\s*["\']([^"\']*)["\']', props)
        ja_match = re.search(r'ja\s*=\s*["\']([^"\']*)["\']', props)
        category_match = re.search(r'category\s*=\s*["\']([^"\']*)["\']', props)
        type_match = re.search(r'type\s*=\s*(\d+)', props)
        skill_match = re.search(r'skill\s*=\s*(\d+)', props)
        slots_match = re.search(r'slots\s*=\s*(\d+)', props)
        
        en_name = en_match.group(1) if en_match else ""
        ja_name = ja_match.group(1) if ja_match else en_name
        category = category_match.group(1) if category_match else ""
        item_type = int(type_match.group(1)) if type_match else 0
        skill = int(skill_match.group(1)) if skill_match else None
        slots = int(slots_match.group(1)) if slots_match else None
        
        if en_name or ja_name:
            items.append((int(item_id), ja_name, en_name, category, item_type, skill, slots))
    
    output_cursor = output_conn.cursor()
    output_cursor.executemany(
        "INSERT OR REPLACE INTO items (id, name_ja, name_en, category, type, skill, slots) VALUES (?, ?, ?, ?, ?, ?, ?)",
        items
    )
    output_conn.commit()
    
    print(f"Imported {len(items)} items from items.lua")


def add_metadata(conn: sqlite3.Connection, input_path: str):
    """メタデータを追加"""
    cursor = conn.cursor()
    cursor.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", 
                   ("source", "windower_lua"))
    cursor.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", 
                   ("source_path", str(input_path)))
    cursor.execute("INSERT INTO metadata (key, value) VALUES (?, ?)", 
                   ("generated_at", datetime.datetime.now().isoformat()))
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Generate item database for VanaInventory from items.lua")
    parser.add_argument("--input", required=True, help="Path to items.lua")
    parser.add_argument("--output", default=str(OUTPUT_DB), help="Output DB path")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    print(f"Creating output DB: {output_path}")
    output_conn = create_output_db(output_path)
    
    import_from_windower_lua(input_path, output_conn)
    
    add_metadata(output_conn, str(input_path))
    output_conn.close()
    
    print(f"Done! Output: {output_path}")


if __name__ == "__main__":
    main()
