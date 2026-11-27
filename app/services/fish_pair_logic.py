from functools import lru_cache

from app.services.aquarium_indicator_logic import AggressionLevel
from app.services.fish_logic import get_all_fish

STATUS_SELF = 0
STATUS_GREEN = 1
STATUS_YELLOW = 2
STATUS_RED = 3


def map_db_to_fish(db_fish: dict) -> tuple[str, int, float, float, float, float]:
    aggression_map = {
        "PEACEFUL": AggressionLevel.PEACEFUL.value,
        "SEMI_AGGRESSIVE": AggressionLevel.SEMI_AGGRESSIVE.value,
        "AGGRESSIVE": AggressionLevel.AGGRESSIVE.value,
    }

    return (
        db_fish["fish_name"],
        aggression_map.get(db_fish["aggression"], AggressionLevel.PEACEFUL.value),
        float(db_fish["temp_min"]),
        float(db_fish["temp_max"]),
        float(db_fish["ph_min"]),
        float(db_fish["ph_max"]),
    )



def check_range_compatibility(
    min1: float, max1: float,
    min2: float, max2: float,
    min_overlap: float
) -> int:
    overlap = min(max1, max2) - max(min1, min2)

    if overlap < 0:
        return STATUS_RED

    if overlap < min_overlap:
        return STATUS_YELLOW

    return STATUS_GREEN


def check_fish_pair_code(fish1: tuple[str, int, float, float, float, float], fish2: tuple[str, int, float, float, float, float]) -> int:
    aggression_levels = (fish1[1], fish2[1])

    if AggressionLevel.AGGRESSIVE.value in aggression_levels:
        return STATUS_RED

    aggression_status = (
        STATUS_YELLOW
        if AggressionLevel.SEMI_AGGRESSIVE.value in aggression_levels
        else STATUS_GREEN
    )

    temperature_status = check_range_compatibility(
        fish1[2], fish1[3], fish2[2], fish2[3], 2
    )

    ph_status = check_range_compatibility(
        fish1[4], fish1[5], fish2[4], fish2[5], 1
    )

    return max(aggression_status, temperature_status, ph_status)


@lru_cache(maxsize=1)
def build_compatibility_matrix() -> dict:
    fish_objects = [map_db_to_fish(row) for row in get_all_fish()]
    count = len(fish_objects)
    matrix = [bytearray(count) for _ in range(count)]

    for index in range(count):
        matrix[index][index] = STATUS_SELF

    for left_index in range(count):
        left_fish = fish_objects[left_index]
        left_row = matrix[left_index]
        for right_index in range(left_index + 1, count):
            status = check_fish_pair_code(left_fish, fish_objects[right_index])
            left_row[right_index] = status
            matrix[right_index][left_index] = status

    return {
        "fish": [fish[0] for fish in fish_objects],
        "matrix": matrix,
    }
