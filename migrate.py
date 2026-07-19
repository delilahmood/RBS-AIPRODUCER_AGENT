import sqlite3

conn = sqlite3.connect("rbs_aiproducer.db")
cursor = conn.cursor()

columns_to_add = [
    # Episodes

    ("episodes", "cover_url", "VARCHAR"),
    ("episodes", "cover_prompt_used", "TEXT"),
    ("episodes", "assembled_video_url", "VARCHAR"),    

    # Projects
    ("projects", "aspect_ratio", "VARCHAR DEFAULT '16:9'"),
    ("projects", "world_style_prompt", "TEXT"),
    ("projects", "character_style_prompt", "TEXT"),

    # Character Assets
    ("character_assets", "generation_batch", "INTEGER DEFAULT 1"),
    ("character_assets", "is_selected", "BOOLEAN DEFAULT 0"),

    # Scenes
    ("scenes", "location_id", "INTEGER"),
    ("scenes", "character_ids", "TEXT"),

    # Scene Assets
    ("scene_assets", "generation_batch", "INTEGER DEFAULT 1"),
    ("scene_assets", "is_selected", "BOOLEAN DEFAULT 0"),
]

for table, column_name, column_type in columns_to_add:
    try:
        cursor.execute(
            f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}"
        )
        print(f"✅ Added column: {table}.{column_name}")

    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e):
            print(f"⏭️ Already exists, skipping: {table}.{column_name}")
        elif "no such table" in str(e):
            print(
                f"⚠️ Table does not exist yet (will be auto-created on next app startup): {table}"
            )
        else:
            raise

conn.commit()
conn.close()

print("\n✅ Migration done.")