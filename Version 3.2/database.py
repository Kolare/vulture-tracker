import sqlite3
import os
import cv2

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
        """
        Creates or verifies the necessary tables for the application.
        This has been updated to support new features like object images, base HP,
        and storing health as text to accommodate the 'wrecked' status.
        """
        cursor = self.conn.cursor()
        # Config table for app-wide settings like map path
        cursor.execute('CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)')

        # Sietch, Location, and Object hierarchy
        cursor.execute('CREATE TABLE IF NOT EXISTS sietches (name TEXT PRIMARY KEY)')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY,
                sietch_name TEXT NOT NULL,
                location_id TEXT NOT NULL,
                pin_x INTEGER,
                pin_y INTEGER,
                FOREIGN KEY(sietch_name) REFERENCES sietches(name) ON DELETE CASCADE,
                UNIQUE(sietch_name, location_id)
            )''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS objects (
                id INTEGER PRIMARY KEY,
                location_fk INTEGER NOT NULL,
                object_id TEXT NOT NULL,
                object_image_path TEXT,
                base_hp INTEGER,
                FOREIGN KEY(location_fk) REFERENCES locations(id) ON DELETE CASCADE,
                UNIQUE(location_fk, object_id)
            )''')

        # History table to track health over time for each object
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY,
                object_fk INTEGER NOT NULL,
                timestamp INTEGER NOT NULL,
                health_percent TEXT,
                screenshot_path TEXT,
                FOREIGN KEY(object_fk) REFERENCES objects(id) ON DELETE CASCADE
            )''')
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

    def get_sietches_with_location_counts(self):
        """
        Returns a list of tuples with (sietch_name, location_count),
        sorted by count descending, then name ascending.
        """
        sql = """
            SELECT
                s.name,
                COUNT(l.id)
            FROM
                sietches s
            LEFT JOIN
                locations l ON s.name = l.sietch_name
            GROUP BY
                s.name
            ORDER BY
                COUNT(l.id) DESC,
                s.name ASC
        """
        return self.query(sql).fetchall()

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
        self.query("DELETE FROM locations WHERE id=?", (loc_pk,)); self.commit()

    def save_data_point(self, sietch, location_id, object_id, analysis_result):
        """
        Saves a new health reading to the database.
        This is now streamlined to accept the result from the analyzer directly.
        """
        try:
            # Get the foreign key for the location
            loc_fk_row = self.query("SELECT id FROM locations WHERE sietch_name=? AND location_id=?", (sietch, location_id)).fetchone()
            if not loc_fk_row:
                return False, f"Location '{location_id}' not found in Sietch '{sietch}'."
            loc_fk = loc_fk_row[0]

            # Ensure the object exists, then get its foreign key
            self.query("INSERT OR IGNORE INTO objects (location_fk, object_id) VALUES (?, ?)", (loc_fk, object_id))
            obj_fk = self.query("SELECT id FROM objects WHERE location_fk=? AND object_id=?", (loc_fk, object_id)).fetchone()[0]

            # Extract data from the analysis result dictionary
            timestamp = analysis_result['timestamp']
            health_percent = analysis_result['health_percent']
            crop_filepath = analysis_result.get('crop_filepath', None) # Use .get for safety

            # Insert the new history record
            self.query("INSERT INTO history (object_fk, timestamp, health_percent, screenshot_path) VALUES (?, ?, ?, ?)",
                       (obj_fk, int(timestamp.timestamp()), str(health_percent), crop_filepath))
            self.commit()
            return True, "Success"
        except Exception as e:
            import traceback
            return False, f"Database error: {e}\n{traceback.format_exc()}"

    def get_objects_for_location(self, loc_pk):
        """Returns a list of objects for a given location primary key."""
        return self.query("SELECT id, object_id, object_image_path, base_hp FROM objects WHERE location_fk=? ORDER BY object_id", (loc_pk,)).fetchall()

    def get_history_for_object(self, obj_pk):
        """Returns the full history for a given object primary key, sorted by time."""
        return self.query("SELECT id, timestamp, health_percent, screenshot_path FROM history WHERE object_fk=? ORDER BY timestamp DESC", (obj_pk,)).fetchall()

    def delete_object(self, obj_pk):
        """Deletes an object and its associated history, including screenshot files."""
        # First, get all screenshot paths to delete the files
        paths_to_delete = [row[0] for row in self.query("SELECT screenshot_path FROM history WHERE object_fk=?", (obj_pk,)).fetchall() if row[0]]
        for path in paths_to_delete:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as e:
                    print(f"Error deleting file {path}: {e}")

        # Now, delete the object record from the database, which will cascade to history
        self.query("DELETE FROM objects WHERE id=?", (obj_pk,)); self.commit()
        return True, "Success"

    def delete_history_point(self, hist_pk):
        """Deletes a single history data point, including its screenshot file."""
        path_to_delete = self.query("SELECT screenshot_path FROM history WHERE id=?", (hist_pk,)).fetchone()
        if path_to_delete and path_to_delete[0] and os.path.exists(path_to_delete[0]):
            try:
                os.remove(path_to_delete[0])
            except OSError as e:
                print(f"Error deleting file {path_to_delete[0]}: {e}")

        self.query("DELETE FROM history WHERE id=?", (hist_pk,)); self.commit()
        return True, "Success"

    def update_history_health(self, hist_pk, new_health_percent):
        """Manually updates the health percentage of a specific history record."""
        self.query("UPDATE history SET health_percent=? WHERE id=?", (str(new_health_percent), hist_pk)); self.commit()
        return True, "Success"

    def add_manual_history_point(self, obj_pk, timestamp, health_percent, screenshot_path=None):
        """Adds a manual data point to an object's history."""
        self.query("INSERT INTO history (object_fk, timestamp, health_percent, screenshot_path) VALUES (?, ?, ?, ?)",
                   (obj_pk, int(timestamp.timestamp()), str(health_percent), screenshot_path))
        self.commit()
        return True, "Success"

    def set_object_image(self, obj_pk, image_path):
        """Sets or updates the user-provided image for an object."""
        self.query("UPDATE objects SET object_image_path=? WHERE id=?", (image_path, obj_pk)); self.commit()

    def set_object_base_hp(self, obj_pk, base_hp):
        """Sets or updates the base HP for an object."""
        self.query("UPDATE objects SET base_hp=? WHERE id=?", (base_hp, obj_pk)); self.commit()

    def rename_object(self, obj_pk, new_name):
        """Renames an object, checking for uniqueness within its location."""
        try:
            self.query("UPDATE objects SET object_id=? WHERE id=?", (new_name, obj_pk))
            self.commit()
            return True, "Success"
        except sqlite3.IntegrityError:
            return False, "An object with this name already exists at this location."

    def get_priority_watch_list(self, limit=10):
        """
        Calculates and returns a list of objects with the shortest time to decay.
        This is the core logic for the "Priority Watch List".
        """
        # This query gets all objects that have at least two history entries,
        # which is the minimum required to calculate a decay rate.
        # It retrieves the object's identifiers and its two most recent health readings.
        sql = """
            SELECT
                o.id,
                l.sietch_name,
                l.location_id,
                o.object_id,
                h1.timestamp,
                h1.health_percent,
                h2.timestamp,
                h2.health_percent
            FROM objects o
            JOIN locations l ON o.location_fk = l.id
            JOIN (
                SELECT *, ROW_NUMBER() OVER(PARTITION BY object_fk ORDER BY timestamp DESC) as rn
                FROM history
                WHERE health_percent != 'wrecked'
            ) h1 ON o.id = h1.object_fk
            JOIN (
                SELECT *, ROW_NUMBER() OVER(PARTITION BY object_fk ORDER BY timestamp DESC) as rn
                FROM history
                WHERE health_percent != 'wrecked'
            ) h2 ON o.id = h2.object_fk
            WHERE h1.rn = 1 AND h2.rn = 2
        """
        cursor = self.query(sql)

        decay_rates = []
        for row in cursor.fetchall():
            obj_pk, sietch, loc, obj, t1, h1, t2, h2 = row

            try:
                h1, h2 = float(h1), float(h2)
            except (ValueError, TypeError):
                continue # Skip if health is not a number (e.g., manual entry error)

            time_diff_seconds = t1 - t2
            health_diff = h2 - h1 # Health at t2 should be higher than at t1

            # Avoid division by zero and ensure decay is positive
            if time_diff_seconds <= 0 or health_diff <= 0:
                continue

            decay_per_second = health_diff / time_diff_seconds

            # Project time to reach 0 from the latest health reading (h1)
            seconds_to_zero = h1 / decay_per_second

            # The "urgency" is the timestamp when it's predicted to hit zero
            estimated_wreck_time = t1 + seconds_to_zero

            decay_rates.append({
                'sietch': sietch,
                'location': loc,
                'object': obj,
                'current_health': h1,
                'estimated_wreck_time': estimated_wreck_time
            })

        # Sort by the estimated wreck time (most urgent first) and take the top `limit`
        decay_rates.sort(key=lambda x: x['estimated_wreck_time'])
        return decay_rates[:limit]

    def get_location_status(self, loc_pk):
        """
        Gets the timestamp of the most recent update and the lowest current health
        for any object at a specific location. Used for the color-coded status dots.
        """
        sql = """
            WITH LatestHistory AS (
                SELECT
                    h.object_fk,
                    h.timestamp,
                    h.health_percent,
                    ROW_NUMBER() OVER(PARTITION BY h.object_fk ORDER BY h.timestamp DESC) as rn
                FROM history h
                JOIN objects o ON h.object_fk = o.id
                WHERE o.location_fk = ?
            )
            SELECT
                MAX(lh.timestamp),
                MIN(CASE WHEN lh.health_percent = 'wrecked' THEN 0 ELSE CAST(lh.health_percent AS REAL) END)
            FROM LatestHistory lh
            WHERE lh.rn = 1
        """
        return self.query(sql, (loc_pk,)).fetchone()

    def close(self):
        if self.conn: self.conn.close()