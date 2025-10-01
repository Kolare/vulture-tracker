import sqlite3
import os
import sys

def migrate():
    old_db_path = 'vulture_tracker_v3_old.db'
    new_db_path = 'vulture_tracker_v3.db'

    # Get the directory of the script to build absolute paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    old_db_path_abs = os.path.join(script_dir, old_db_path)
    new_db_path_abs = os.path.join(script_dir, new_db_path)

    if not os.path.exists(old_db_path_abs):
        print(f"Error: Old database file '{old_db_path}' not found in the script's directory.")
        print("Please place your old database file in the same folder as this script and rename it.")
        sys.exit(1)

    if not os.path.exists(new_db_path_abs):
        print(f"Error: New database file '{new_db_path}' not found in the script's directory.")
        print("Please run the main application (main.py) once to create a new database before migrating.")
        sys.exit(1)

    old_conn = sqlite3.connect(old_db_path_abs)
    old_cursor = old_conn.cursor()

    new_conn = sqlite3.connect(new_db_path_abs)
    new_cursor = new_conn.cursor()

    print("Starting data migration...")

    # 1. Migrate Sietches
    print("Migrating sietches...")
    try:
        old_cursor.execute("SELECT name FROM sietches")
        sietches = old_cursor.fetchall()
        new_cursor.executemany("INSERT OR IGNORE INTO sietches (name) VALUES (?)", sietches)
        new_conn.commit()
        print(f"  ...{len(sietches)} sietches processed.")
    except sqlite3.Error as e:
        print(f"An error occurred during sietch migration: {e}")
        new_conn.rollback() # Rollback on error
        new_conn.close()
        old_conn.close()
        sys.exit(1)

    # 2. Migrate Locations
    print("Migrating locations...")
    try:
        old_cursor.execute("SELECT sietch_name, location_id, pin_x, pin_y FROM locations")
        locations = old_cursor.fetchall()
        new_cursor.executemany("INSERT OR IGNORE INTO locations (sietch_name, location_id, pin_x, pin_y) VALUES (?, ?, ?, ?)", locations)
        new_conn.commit()
        print(f"  ...{len(locations)} locations processed.")
    except sqlite3.Error as e:
        print(f"An error occurred during location migration: {e}")
        new_conn.rollback()
        new_conn.close()
        old_conn.close()
        sys.exit(1)

    # 3. Migrate Objects and their History
    print("Migrating objects and history (this may take a moment)...")
    try:
        sql = """
            SELECT s.name, l.location_id, o.object_id
            FROM objects o
            JOIN locations l ON o.location_fk = l.id
            JOIN sietches s ON l.sietch_name = s.name
        """
        old_cursor.execute(sql)
        all_objects = old_cursor.fetchall()

        object_count = 0
        history_count = 0

        for sietch_name, location_id, object_id in all_objects:
            new_cursor.execute("SELECT id FROM locations WHERE sietch_name=? AND location_id=?", (sietch_name, location_id))
            loc_fk_row = new_cursor.fetchone()
            if not loc_fk_row:
                print(f"  - Warning: Could not find new location for {sietch_name}/{location_id}. Skipping its objects.")
                continue
            new_loc_fk = loc_fk_row[0]

            new_cursor.execute("INSERT OR IGNORE INTO objects (location_fk, object_id) VALUES (?, ?)", (new_loc_fk, object_id))
            new_cursor.execute("SELECT id FROM objects WHERE location_fk=? AND object_id=?", (new_loc_fk, object_id))
            obj_fk_row = new_cursor.fetchone()
            if not obj_fk_row:
                print(f"  - Warning: Could not create/find new object for {sietch_name}/{location_id}/{object_id}. Skipping its history.")
                continue
            new_obj_fk = obj_fk_row[0]
            object_count += 1

            old_history_sql = """
                SELECT h.timestamp, h.health_percent, h.screenshot_path
                FROM history h
                JOIN objects o ON h.object_fk = o.id
                JOIN locations l ON o.location_fk = l.id
                WHERE l.sietch_name = ? AND l.location_id = ? AND o.object_id = ?
            """
            old_cursor.execute(old_history_sql, (sietch_name, location_id, object_id))
            history_records = old_cursor.fetchall()

            new_history_records = []
            for ts, health, path in history_records:
                # Ensure the screenshot path is relative to the image folder for portability
                final_path = path
                if path and 'vulture_tracker_images_v3' in path:
                    final_path = os.path.join('vulture_tracker_images_v3', os.path.basename(path))

                new_history_records.append((new_obj_fk, ts, health, final_path))

            new_cursor.executemany("INSERT OR IGNORE INTO history (object_fk, timestamp, health_percent, screenshot_path) VALUES (?, ?, ?, ?)", new_history_records)
            history_count += len(new_history_records)

        new_conn.commit()
        print(f"  ...{object_count} objects and {history_count} history points processed.")

    except sqlite3.Error as e:
        print(f"An error occurred during object/history migration: {e}")
        new_conn.rollback()
        new_conn.close()
        old_conn.close()
        sys.exit(1)

    old_conn.close()
    new_conn.close()

    print("\nMigration complete!")
    print("All Sietches, Locations, Objects, and History have been transferred.")
    print("The configuration table was NOT copied, so please set your main map image again via the File menu.")

if __name__ == '__main__':
    # Add a confirmation before running
    print("This script will migrate data from 'vulture_tracker_v3_old.db' to 'vulture_tracker_v3.db'.")
    print("It will NOT delete any data from the old database, but it will add to the new one.")
    response = input("Are you sure you want to continue? (y/n): ")
    if response.lower() == 'y':
        migrate()
    else:
        print("Migration cancelled.")