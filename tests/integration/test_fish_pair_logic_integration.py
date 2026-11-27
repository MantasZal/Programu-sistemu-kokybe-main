
import os
import tempfile
import unittest
from unittest.mock import patch

import app.services.fish_logic as fish_logic
import app.services.fish_pair_logic as fish_pair_logic


class TestFishPairLogicIntegration(unittest.TestCase):
    def setUp(self):
        fish_pair_logic.build_compatibility_matrix.cache_clear()

        fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(fd)

        self.db_patches = [
            patch("app.services.fish_logic.APP_DB", self.db_path),
            patch("app.database.db_setup.APP_DB", self.db_path),
        ]

        for db_patch in self.db_patches:
            db_patch.start()

        fish_logic.initialize_fish_module()

    def tearDown(self):
        fish_pair_logic.build_compatibility_matrix.cache_clear()

        for db_patch in reversed(self.db_patches):
            db_patch.stop()

        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_build_compatibility_matrix_uses_real_database_records(self):
        fish_logic.add_fish(
            "Neon",
            "PEACEFUL",
            2.0,
            22.0,
            28.0,
            6.0,
            8.0,
        )
        fish_logic.add_fish(
            "Guppy",
            "PEACEFUL",
            3.0,
            24.0,
            26.0,
            6.8,
            7.5,
        )
        fish_logic.add_fish(
            "Barb",
            "SEMI_AGGRESSIVE",
            5.0,
            24.0,
            28.0,
            6.5,
            8.0,
        )
        fish_logic.add_fish(
            "Cichlid",
            "AGGRESSIVE",
            10.0,
            25.0,
            29.0,
            7.0,
            8.5,
        )

        result = fish_pair_logic.build_compatibility_matrix()

        self.assertEqual(result["fish"], ["Neon", "Guppy", "Barb", "Cichlid"])
        self.assertEqual(
            result["matrix"],
            [
                bytearray([0, 2, 2, 3]),
                bytearray([2, 0, 2, 3]),
                bytearray([2, 2, 0, 3]),
                bytearray([3, 3, 3, 0]),
            ],
        )


if __name__ == "__main__":
    unittest.main()
