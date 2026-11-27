
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from app.ui.aquarium_page import AquariumPage
from app.ui.aquarium_management_page import AquariumManagementPage


class TestAquariumParameters(unittest.TestCase):

    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        self.pages = [AquariumPage, AquariumManagementPage]

        self.db_patches = [
            patch("app.ui.aquarium_page.APP_DB", self.db_path),
            patch("app.ui.aquarium_management_page.APP_DB", self.db_path),
        ]

        for db_patch in self.db_patches:
            db_patch.start()
            self.addCleanup(db_patch.stop)

        self.addCleanup(os.remove, self.db_path)

        conn = sqlite3.connect(self.db_path)

        try:
            conn.executescript("""
                CREATE TABLE fish_list (
                    id INTEGER PRIMARY KEY,
                    temp_min REAL,
                    temp_max REAL,
                    ph_min REAL,
                    ph_max REAL
                );

                CREATE TABLE fish_in_aquarium (
                    id INTEGER PRIMARY KEY,
                    aquarium_id INTEGER,
                    fish_id INTEGER
                );
            """)
            conn.commit()
        finally:
            conn.close()

    def add_fish(self, fish_id, temp_min, temp_max, ph_min, ph_max):
        conn = sqlite3.connect(self.db_path)

        try:
            conn.execute(
                "INSERT INTO fish_list VALUES (?, ?, ?, ?, ?)",
                (fish_id, temp_min, temp_max, ph_min, ph_max),
            )
            conn.commit()
        finally:
            conn.close()

    def add_aquarium_record(self, record_id, aquarium_id, fish_id):
        conn = sqlite3.connect(self.db_path)

        try:
            conn.execute(
                "INSERT INTO fish_in_aquarium VALUES (?, ?, ?)",
                (record_id, aquarium_id, fish_id),
            )
            conn.commit()
        finally:
            conn.close()

    def assert_summary(self, aquarium_id, expected):
        for page in self.pages:
            with self.subTest(page=page.__name__):
                result = page._calculate_temp_ph_summary(None, aquarium_id)
                self.assertEqual(result, expected)

    def assert_matching_record(self, aquarium_id, fish_id, expected):
        for page in self.pages:
            with self.subTest(page=page.__name__):
                result = page._first_matching_aquarium_record(
                    None, aquarium_id, fish_id
                )
                self.assertEqual(result, expected)

    def test_empty_aquarium(self):
        self.assert_summary(1, "Temp/pH: no fish")

    def test_single_fish(self):
        self.add_fish(1, 22, 28, 6, 8)
        self.add_aquarium_record(1, 1, 1)

        self.assert_summary(
            1, "Temp/pH: 22.0-28.0 C | pH 6.0-8.0"
        )

    def test_compatible_fish(self):
        self.add_fish(1, 22, 28, 6, 8)
        self.add_fish(2, 24, 26, 6.5, 7.5)

        self.add_aquarium_record(1, 1, 1)
        self.add_aquarium_record(2, 1, 2)

        self.assert_summary(
            1, "Temp/pH: 24.0-26.0 C | pH 6.5-7.5"
        )

    def test_incompatible_temperature(self):
        self.add_fish(1, 10, 15, 6, 8)
        self.add_fish(2, 22, 28, 6, 8)

        self.add_aquarium_record(1, 1, 1)
        self.add_aquarium_record(2, 1, 2)

        self.assert_summary(1, "Temp/pH: incompatible")

    def test_incompatible_ph(self):
        self.add_fish(1, 22, 28, 5, 6)
        self.add_fish(2, 22, 28, 7, 8)

        self.add_aquarium_record(1, 1, 1)
        self.add_aquarium_record(2, 1, 2)

        self.assert_summary(1, "Temp/pH: incompatible")

    def test_touching_ranges(self):
        self.add_fish(1, 22, 24, 6, 7)
        self.add_fish(2, 24, 28, 7, 8)

        self.add_aquarium_record(1, 1, 1)
        self.add_aquarium_record(2, 1, 2)

        self.assert_summary(
            1, "Temp/pH: 24.0-24.0 C | pH 7.0-7.0"
        )

    def test_other_aquarium_is_ignored(self):
        self.add_fish(1, 22, 28, 6, 8)
        self.add_fish(2, 10, 15, 4, 5)

        self.add_aquarium_record(1, 1, 1)
        self.add_aquarium_record(2, 2, 2)

        self.assert_summary(
            1, "Temp/pH: 22.0-28.0 C | pH 6.0-8.0"
        )

    def test_matching_record_exists(self):
        self.add_aquarium_record(5, 1, 2)

        self.assert_matching_record(1, 2, 5)

    def test_matching_record_does_not_exist(self):
        self.assert_matching_record(1, 2, None)

    def test_first_matching_record_is_selected(self):
        self.add_aquarium_record(10, 1, 2)
        self.add_aquarium_record(3, 1, 2)
        self.add_aquarium_record(7, 1, 2)

        self.assert_matching_record(1, 2, 3)

    def test_matching_record_filters_aquarium_and_fish(self):
        self.add_aquarium_record(1, 2, 2)
        self.add_aquarium_record(2, 1, 3)
        self.add_aquarium_record(3, 1, 2)

        self.assert_matching_record(1, 2, 3)


if __name__ == "__main__":
    unittest.main()
