import sqlite3
import os
import cv2
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.conn.execute("PRAGMA foreign_keys = 1")
        self.create_tables()

    def query(self, sql, params=()):
        return self.conn.cursor().execute(sql, params)

    def commit(self):
        self.conn.commit()

    def create_tables(self):
        # (This method remains unchanged)
        cursor = self.conn.cursor()
        cursor.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS sietches (name TEXT PRIMARY KEY)')
        cursor.execute('''CREATE TABLE IF NOT EXISTS locations (id INTEGER PRIMARY KEY, sietch_name TEXT, location_id TEXT, pin_x INTEGER, pin_y INTEGER, FOREIGN KEY(sietch_name) REFERENCES sietches(name) ON DELETE CASCADE, UNIQUE(sietch_name, location_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS objects (id INTEGER PRIMARY KEY, location_fk INTEGER, object_id TEXT, FOREIGN KEY(location_fk) REFERENCES locations(id) ON DELETE CASCADE, UNIQUE(location_fk, object_id))''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS history (id INTEGER PRIMARY KEY, object_fk INTEGER, timestamp INTEGER, health_percent REAL, screenshot_path TEXT, FOREIGN KEY(object_fk) REFERENCES objects(id) ON DELETE CASCADE)''')
        self.conn.commit()

    def get_config(self, key):
        row = self.query("SELECT value FROM config WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_config(self, key, value):
        self.query("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value)); self.commit()

    def add_sietch(self, name):
        try:
            self.query("INSERT INTO sietches (name) VALUES (?)", (name,)); self.commit(); return True, "Success"
        except sqlite3.IntegrityError: return False, "Sietch name already exists."

    def rename_sietch(self, old_name, new_name):
        try:
            self.query("UPDATE sietches SET name=? WHERE name=?", (new_name, old_name)); self.commit(); return True, "Success"
        except sqlite3.IntegrityError: return False, "New sietch name already exists."

    def delete_sietch(self, name):
        self.query("DELETE FROM sietches WHERE name=?", (name,)); self.commit()

    def get_sietches(self):
        return [s[0] for s in self.query("SELECT name FROM sietches ORDER BY name").fetchall()]

    def add_location(self, sietch_name, location_id, pin_x=None, pin_y=None):
        self.query("INSERT OR IGNORE INTO locations (sietch_name, location_id, pin_x, pin_y) VALUES (?, ?, ?, ?)", (sietch_name, location_id, pin_x, pin_y)); self.commit()

    def get_locations_for_sietch(self, sietch_name):
        return [l[0] for l in self.query("SELECT location_id FROM locations WHERE sietch_name=? ORDER BY location_id", (sietch_name,)).fetchall()]

    def get_all_pinned_locations(self):
        return self.query("SELECT id, location_id, pin_x, pin_y, sietch_name FROM locations WHERE pin_x IS NOT NULL").fetchall()

    def get_unpinned_locations(self, sietch_name):
        return self.query("SELECT id, location_id FROM locations WHERE sietch_name=? AND pin_x IS NULL", (sietch_name,)).fetchall()

    def update_pin_location(self, loc_pk, x, y):
        self.query("UPDATE locations SET pin_x=?, pin_y=? WHERE id=?", (x, y, loc_pk)); self.commit()

    def get_location_name(self, loc_pk):
        row = self.query("SELECT location_id FROM locations WHERE id=?", (loc_pk,)).fetchone()
        return row[0] if row else ""

    def rename_location(self, loc_pk, new_id):
        try:
            self.query("UPDATE locations SET location_id=? WHERE id=?", (new_id, loc_pk)); self.commit(); return True, "Success"
        except sqlite3.IntegrityError: return False, "A location with this ID already exists in this Sietch."

    def delete_location(self, loc_pk):
        # Get all screenshot paths for all objects under this location
        sql = """SELECT h.screenshot_path FROM history h
                 JOIN objects o ON h.object_fk = o.id
                 WHERE o.location_fk = ?"""
        paths = self.query(sql, (loc_pk,)).fetchall()
        for path_tuple in paths:
            try:
                if path_tuple[0] and os.path.exists(path_tuple[0]):
                    os.remove(path_tuple[0])
            except Exception as e:
                print(f"Error deleting screenshot file: {e}")

        # Now delete the location. The CASCADE constraint will handle deleting
        # associated objects and their history records from the DB.
        self.query("DELETE FROM locations WHERE id=?", (loc_pk,)); self.commit()

    def get_location_pk_by_name(self, sietch_name, location_id):
        row = self.query("SELECT id FROM locations WHERE sietch_name=? AND location_id=?", (sietch_name, location_id)).fetchone()
        return row[0] if row else None

    def get_object_pk_by_name(self, sietch_name, location_id, object_id):
        loc_pk = self.get_location_pk_by_name(sietch_name, location_id)
        if not loc_pk: return None
        row = self.query("SELECT id FROM objects WHERE location_fk=? AND object_id=?", (loc_pk, object_id)).fetchone()
        return row[0] if row else None

    def rename_object(self, obj_pk, new_id):
        try:
            self.query("UPDATE objects SET object_id=? WHERE id=?", (new_id, obj_pk)); self.commit()
            return True, "Success"
        except sqlite3.IntegrityError:
            return False, "An object with this ID already exists at this location."

    def delete_object(self, obj_pk):
        # Get screenshot paths for this specific object
        paths = self.query("SELECT screenshot_path FROM history WHERE object_fk=?", (obj_pk,)).fetchall()
        for path_tuple in paths:
            try:
                if path_tuple[0] and os.path.exists(path_tuple[0]):
                    os.remove(path_tuple[0])
            except Exception as e:
                print(f"Error deleting screenshot file: {e}")
        # Now delete the object, history will be cascaded.
        self.query("DELETE FROM objects WHERE id=?", (obj_pk,)); self.commit()

    def save_data_point(self, data, image_folder):
        try:
            loc_fk_row = self.query("SELECT id FROM locations WHERE sietch_name=? AND location_id=?", (data["sietch"], data["location_id"])).fetchone()
            if not loc_fk_row: return False, f"Location '{data['location_id']}' not found."
            loc_fk = loc_fk_row[0]
            self.query("INSERT OR IGNORE INTO objects (location_fk, object_id) VALUES (?, ?)", (loc_fk, data["object_id"]))
            obj_fk = self.query("SELECT id FROM objects WHERE location_fk=? AND object_id=?", (loc_fk, data["object_id"])).fetchone()[0]
            ts = data["timestamp"]; filename = f"capture_{ts.strftime('%Y%m%d_%H%M%S')}.png"; path = os.path.join(image_folder, filename)
            cv2.imwrite(path, data["roi_image"])
            self.query("INSERT INTO history (object_fk, timestamp, health_percent, screenshot_path) VALUES (?, ?, ?, ?)", (obj_fk, int(ts.timestamp()), data["health"], path)); self.commit()
            return True, "Success"
        except Exception as e: return False, str(e)

    def get_all_objects_with_sietch_and_location(self):
        sql = """
            SELECT s.name, l.location_id, o.object_id
            FROM objects o
            JOIN locations l ON o.location_fk = l.id
            JOIN sietches s ON l.sietch_name = s.name
            ORDER BY s.name, l.location_id, o.object_id
        """
        return self.query(sql).fetchall()

    def get_history_for_object(self, sietch, location, object_id):
        sql = """
            SELECT h.id, h.timestamp, h.health_percent, h.screenshot_path
            FROM history h
            JOIN objects o ON h.object_fk = o.id
            JOIN locations l ON o.location_fk = l.id
            WHERE l.sietch_name = ? AND l.location_id = ? AND o.object_id = ?
            ORDER BY h.timestamp ASC
        """
        history_data = []
        for row in self.query(sql, (sietch, location, object_id)).fetchall():
            history_data.append({
                "id": row[0],
                "timestamp": datetime.fromtimestamp(row[1]),
                "health": float(row[2]),
                "image_path": row[3]
            })
        return history_data

    def delete_history_point(self, history_id):
        path_tuple = self.query("SELECT screenshot_path FROM history WHERE id=?", (history_id,)).fetchone()
        if path_tuple and path_tuple[0] and os.path.exists(path_tuple[0]):
            try:
                os.remove(path_tuple[0])
            except Exception as e:
                print(f"Error deleting screenshot file: {e}")
        self.query("DELETE FROM history WHERE id = ?", (history_id,)); self.commit()

    def update_history_health(self, history_id, new_health):
        self.query("UPDATE history SET health_percent = ? WHERE id = ?", (new_health, history_id)); self.commit()

    def close(self):
        if self.conn: self.conn.close()