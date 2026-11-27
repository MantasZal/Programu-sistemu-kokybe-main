
import sqlite3

from app.config import APP_DB


def calculate_temp_ph_summary(aquarium_id: int) -> str:
    conn = sqlite3.connect(APP_DB)

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT fl.temp_min, fl.temp_max, fl.ph_min, fl.ph_max
            FROM fish_in_aquarium fia
            JOIN fish_list fl ON fia.fish_id = fl.id
            WHERE fia.aquarium_id = ?
        """, (aquarium_id,))
        rows = cursor.fetchall()
    finally:
        conn.close()

    if not rows:
        return "Temp/pH: no fish"

    temp_min = max(row[0] for row in rows)
    temp_max = min(row[1] for row in rows)
    ph_min = max(row[2] for row in rows)
    ph_max = min(row[3] for row in rows)

    if temp_min > temp_max or ph_min > ph_max:
        return "Temp/pH: incompatible"

    return f"Temp/pH: {temp_min:.1f}-{temp_max:.1f} C | pH {ph_min:.1f}-{ph_max:.1f}"


def first_matching_aquarium_record(aquarium_id: int, fish_id: int) -> int | None:
    conn = sqlite3.connect(APP_DB)

    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id FROM fish_in_aquarium
            WHERE aquarium_id = ? AND fish_id = ?
            ORDER BY id ASC LIMIT 1
        """, (aquarium_id, fish_id))
        row = cursor.fetchone()
    finally:
        conn.close()

    return None if row is None else int(row[0])
