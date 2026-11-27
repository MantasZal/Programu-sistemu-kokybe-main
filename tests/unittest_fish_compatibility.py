
import unittest
from unittest.mock import patch

from app.services.aquarium_indicator_logic import AggressionLevel
from app.services.fish_pair_logic import (
    STATUS_SELF,
    STATUS_GREEN,
    STATUS_YELLOW,
    STATUS_RED,
    map_db_to_fish,
    check_fish_pair_code,
    build_compatibility_matrix,
)


class TestFishCompatibility(unittest.TestCase):

    def setUp(self):
        self.peaceful = AggressionLevel.PEACEFUL.value
        self.semi_aggressive = AggressionLevel.SEMI_AGGRESSIVE.value
        self.aggressive = AggressionLevel.AGGRESSIVE.value

        self.fish = ("Neon", self.peaceful, 22.0, 28.0, 6.0, 8.0)

        build_compatibility_matrix.cache_clear()
        self.addCleanup(build_compatibility_matrix.cache_clear)

    def test_map_db_to_fish(self):
        db_fish = {
            "fish_name": "Neon",
            "aggression": "PEACEFUL",
            "temp_min": 22,
            "temp_max": 28,
            "ph_min": 6,
            "ph_max": 8,
        }

        self.assertEqual(map_db_to_fish(db_fish), self.fish)

    def test_map_unknown_aggression(self):
        db_fish = {
            "fish_name": "Neon",
            "aggression": "UNKNOWN",
            "temp_min": 22,
            "temp_max": 28,
            "ph_min": 6,
            "ph_max": 8,
        }

        self.assertEqual(map_db_to_fish(db_fish)[1], self.peaceful)

    def test_compatible_fish(self):
        fish2 = ("Guppy", self.peaceful, 23.0, 27.0, 6.5, 8.0)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_GREEN)

    def test_aggressive_fish(self):
        fish2 = ("Cichlid", self.aggressive, 22.0, 28.0, 6.0, 8.0)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_RED)
        self.assertEqual(check_fish_pair_code(fish2, self.fish), STATUS_RED)

    def test_semi_aggressive_fish(self):
        fish2 = ("Barb", self.semi_aggressive, 22.0, 28.0, 6.0, 8.0)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_YELLOW)
        self.assertEqual(check_fish_pair_code(fish2, self.fish), STATUS_YELLOW)

    def test_temperature_mismatch(self):
        fish2 = ("ColdFish", self.peaceful, 10.0, 15.0, 6.0, 8.0)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_RED)

    def test_temperature_narrow_overlap(self):
        fish2 = ("HotFish", self.peaceful, 27.0, 30.0, 6.0, 8.0)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_YELLOW)

    def test_temperature_boundary(self):
        fish2 = ("HotFish", self.peaceful, 26.0, 30.0, 6.0, 8.0)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_GREEN)

    def test_temperature_touching_ranges(self):
        fish2 = ("HotFish", self.peaceful, 28.0, 30.0, 6.0, 8.0)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_YELLOW)

    def test_ph_mismatch(self):
        fish2 = ("AlkalineFish", self.peaceful, 22.0, 28.0, 8.5, 9.0)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_RED)

    def test_ph_narrow_overlap(self):
        fish2 = ("Guppy", self.peaceful, 22.0, 28.0, 7.5, 8.5)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_YELLOW)

    def test_ph_boundary(self):
        fish2 = ("Guppy", self.peaceful, 22.0, 28.0, 7.0, 9.0)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_GREEN)

    def test_ph_touching_ranges(self):
        fish2 = ("Guppy", self.peaceful, 22.0, 28.0, 8.0, 9.0)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_YELLOW)

    def test_ph_mismatch_overrides_yellow(self):
        fish2 = ("Barb", self.semi_aggressive, 27.0, 30.0, 8.5, 9.0)

        self.assertEqual(check_fish_pair_code(self.fish, fish2), STATUS_RED)

    @patch("app.services.fish_pair_logic.get_all_fish")
    def test_build_compatibility_matrix(self, mock_get_all_fish):
        mock_get_all_fish.return_value = [
            {
                "fish_name": "Neon",
                "aggression": "PEACEFUL",
                "temp_min": 22,
                "temp_max": 28,
                "ph_min": 6,
                "ph_max": 8,
            },
            {
                "fish_name": "Guppy",
                "aggression": "PEACEFUL",
                "temp_min": 23,
                "temp_max": 27,
                "ph_min": 6.5,
                "ph_max": 8,
            },
            {
                "fish_name": "Cichlid",
                "aggression": "AGGRESSIVE",
                "temp_min": 24,
                "temp_max": 28,
                "ph_min": 7,
                "ph_max": 8.5,
            },
        ]

        result = build_compatibility_matrix()

        self.assertEqual(result["fish"], ["Neon", "Guppy", "Cichlid"])
        self.assertEqual(
            result["matrix"],
            [
                bytearray([STATUS_SELF, STATUS_GREEN, STATUS_RED]),
                bytearray([STATUS_GREEN, STATUS_SELF, STATUS_RED]),
                bytearray([STATUS_RED, STATUS_RED, STATUS_SELF]),
            ],
        )


if __name__ == "__main__":
    unittest.main()
