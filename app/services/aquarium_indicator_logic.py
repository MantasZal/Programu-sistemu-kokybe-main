import sqlite3
from enum import Enum

from app.config import APP_DB


class StatusColor(Enum):
    GREEN = "Green (Compatible)"
    YELLOW = "Yellow (Caution)"
    RED = "Red (Incompatible)"


class AggressionLevel(Enum):
    PEACEFUL = 1
    SEMI_AGGRESSIVE = 2
    AGGRESSIVE = 3


CODE_MESSAGES = {
    "ALL_PARAMETERS_PERFECT": "All parameters are perfect.",
    "VOLUME_LIMIT_EXCEEDED": "Aquarium does not have enough volume for the selected fish and their quantities.",
    "PREDATOR_ALERT": "Aggressive conflict or predatory fish detected.",
    "SEMI_AGGRESSIVE_WARNING": "Species is semi-aggressive, so caution is needed.",
    "TEMP_MISMATCH_CRITICAL": "Temperature ranges do not match critically.",
    "TEMP_MISMATCH_MINOR": "Temperature compatibility is marginal but still possible.",
    "TEMP_RANGE_NARROW": "The overall temperature range is very narrow.",
    "PH_MISMATCH_CRITICAL": "pH ranges do not match critically.",
    "PH_MISMATCH_MINOR": "pH compatibility is marginal but still possible.",
    "PH_RANGE_NARROW": "The overall pH range is very narrow.",
    "SOCIAL_NEED_UNMET": "Species requires a larger group.",
    "AQUARIUM_EMPTY": "Aquarium is still empty, so the assessment is based on general fish information.",
}


class Fish:
    def __init__(
        self,
        name,
        temp_range,
        ph_range,
        min_volume,
        aggression,
        needs_school=False,
        school_min_size=5,
    ):
        self.name = name
        self.temp_min, self.temp_max = temp_range
        self.ph_min, self.ph_max = ph_range
        self.min_volume = min_volume
        self.aggression = aggression
        self.needs_school = needs_school
        self.school_min_size = school_min_size


class Aquarium:
    def __init__(self, current_temp, current_ph, available_volume):
        self.current_temp = current_temp
        self.current_ph = current_ph
        self.available_volume = available_volume

# kiek reikšmė nutolusi nuo leistino intervalo
def calculate_range_deviation(value: float, minimum: float, maximum: float) -> float:
    if value < minimum:
        return minimum - value
    if value > maximum:
        return value - maximum
    return 0


def prioritize_status(current: StatusColor, new: StatusColor) -> StatusColor:
    priority = {
        StatusColor.GREEN: 0,
        StatusColor.YELLOW: 1,
        StatusColor.RED: 2,
    }
    return max((current, new), key=lambda status: priority[status])


def check_range_overlap(
    existing_fish,
    candidate_min,
    candidate_max,
    min_key,
    max_key,
    narrow_limit,
    critical_code,
    narrow_code,
):
    existing_min = max(float(row[min_key]) for row in existing_fish)
    existing_max = min(float(row[max_key]) for row in existing_fish)

    overlap = min(existing_max, candidate_max) - max(
        existing_min, candidate_min
    )

    if overlap < 0:
        return StatusColor.RED, critical_code

    if overlap < narrow_limit:
        return StatusColor.YELLOW, narrow_code

    return StatusColor.GREEN, None


def load_aquarium_data(aquarium_id, fish_id):
    conn = sqlite3.connect(APP_DB)
    conn.row_factory = sqlite3.Row

    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, fish_name, aggression, size,
                   temp_min, temp_max, ph_min, ph_max
            FROM fish_list
            WHERE id = ?
            """,
            (fish_id,),
        )
        fish_row = cursor.fetchone()

        if fish_row is None:
            return None, None, []

        cursor.execute(
            "SELECT id, aquarium_name, volume FROM aquarium WHERE id = ?",
            (aquarium_id,),
        )
        aquarium_row = cursor.fetchone()

        if aquarium_row is None:
            return fish_row, None, []

        cursor.execute(
            """
            SELECT fl.id, fl.fish_name, fl.aggression,
                   fl.size, fl.temp_min, fl.temp_max,
                   fl.ph_min, fl.ph_max
            FROM fish_in_aquarium fia
            JOIN fish_list fl ON fl.id = fia.fish_id
            WHERE fia.aquarium_id = ?
            """,
            (aquarium_id,),
        )
        existing_fish = cursor.fetchall()

        return fish_row, aquarium_row, existing_fish

    finally:
        conn.close()


def check_aggression(candidate, existing_fish):
    existing_aggressions = {
        map_aggression(row["aggression"]) for row in existing_fish
    }

    if (
        candidate.aggression == AggressionLevel.AGGRESSIVE
        or AggressionLevel.AGGRESSIVE in existing_aggressions
    ):
        return StatusColor.RED, "PREDATOR_ALERT"

    if (
        candidate.aggression == AggressionLevel.SEMI_AGGRESSIVE
        or AggressionLevel.SEMI_AGGRESSIVE in existing_aggressions
    ):
        return StatusColor.YELLOW, "SEMI_AGGRESSIVE_WARNING"

    return StatusColor.GREEN, None


class CompatibilityChecker:
    @staticmethod
    def check_compatibility(fish: Fish, aquarium: Aquarium, quantity_to_add: int = 1) -> dict:
        alerts = []
        worst_status = StatusColor.GREEN

        required_volume = fish.min_volume * quantity_to_add
        if aquarium.available_volume < required_volume:
            worst_status = StatusColor.RED
            alerts.append("VOLUME_LIMIT_EXCEEDED")

        if fish.aggression == AggressionLevel.AGGRESSIVE:
            worst_status = StatusColor.RED
            alerts.append("PREDATOR_ALERT")
        elif fish.aggression == AggressionLevel.SEMI_AGGRESSIVE:
            worst_status = prioritize_status(worst_status, StatusColor.YELLOW)
            alerts.append("SEMI_AGGRESSIVE_WARNING")

        temp_diff = calculate_range_deviation(
            aquarium.current_temp, fish.temp_min, fish.temp_max
        )

        if temp_diff > 2:
            worst_status = StatusColor.RED
            alerts.append("TEMP_MISMATCH_CRITICAL")
        elif 0 < temp_diff <= 2:
            worst_status = prioritize_status(worst_status, StatusColor.YELLOW)
            alerts.append("TEMP_MISMATCH_MINOR")

        ph_diff = calculate_range_deviation(
            aquarium.current_ph, fish.ph_min, fish.ph_max
        )

        if ph_diff > 2:
            worst_status = StatusColor.RED
            alerts.append("PH_MISMATCH_CRITICAL")
        elif 0 < ph_diff <= 2:
            worst_status = prioritize_status(worst_status, StatusColor.YELLOW)
            alerts.append("PH_MISMATCH_MINOR")

        if fish.needs_school and quantity_to_add < fish.school_min_size:
            worst_status = prioritize_status(worst_status, StatusColor.YELLOW)
            alerts.append("SOCIAL_NEED_UNMET")

        if not alerts:
            alerts.append("ALL_PARAMETERS_PERFECT")

        return CompatibilityChecker._build_result(worst_status, alerts)

    @staticmethod
    def evaluate_candidate_for_aquarium(aquarium_id: int, fish_id: int, quantity_to_add: int = 1) -> dict:

        fish_row, aquarium_row, existing_fish = load_aquarium_data(
            aquarium_id, fish_id
        )

        if fish_row is None:
            return CompatibilityChecker._build_result(
                StatusColor.RED, ["PREDATOR_ALERT"]
            )

        if aquarium_row is None:
            return CompatibilityChecker._build_result(
                StatusColor.RED, ["VOLUME_LIMIT_EXCEEDED"]
            )

        candidate = fish_from_row(fish_row)
        alerts = []
        worst_status = StatusColor.GREEN

        used_volume = sum(float(row["size"]) for row in existing_fish)
        required_volume = candidate.min_volume * quantity_to_add
        if used_volume + required_volume > float(aquarium_row["volume"]):
            worst_status = StatusColor.RED
            alerts.append("VOLUME_LIMIT_EXCEEDED")

        existing_same_species = sum(1 for row in existing_fish if int(row["id"]) == fish_id)

        if (candidate.needs_school and existing_same_species + quantity_to_add < candidate.school_min_size):
            worst_status = prioritize_status(worst_status, StatusColor.YELLOW)
            alerts.append("SOCIAL_NEED_UNMET")

        if not existing_fish:
            aggression_status, aggression_code = check_aggression(candidate, existing_fish)
            worst_status = prioritize_status(worst_status, aggression_status)

            if aggression_code:
                alerts.append(aggression_code)

            alerts.append("AQUARIUM_EMPTY")
            if "ALL_PARAMETERS_PERFECT" not in alerts and len(alerts) == 1:
                alerts.insert(0, "ALL_PARAMETERS_PERFECT")
            return CompatibilityChecker._build_result(
                worst_status,
                deduplicate_codes(alerts),
                aquarium_name=aquarium_row["aquarium_name"],
                fish_name=candidate.name,
            )

        temp_status, temp_code = check_range_overlap(
            existing_fish,
            candidate.temp_min,
            candidate.temp_max,
            "temp_min",
            "temp_max",
            2,
            "TEMP_MISMATCH_CRITICAL",
            "TEMP_RANGE_NARROW",
        )

        worst_status = prioritize_status(worst_status, temp_status)

        if temp_code:
            alerts.append(temp_code)

        ph_status, ph_code = check_range_overlap(
            existing_fish,
            candidate.ph_min,
            candidate.ph_max,
            "ph_min",
            "ph_max",
            1,
            "PH_MISMATCH_CRITICAL",
            "PH_RANGE_NARROW",
        )

        worst_status = prioritize_status(worst_status, ph_status)

        if ph_code:
            alerts.append(ph_code)

        aggression_status, aggression_code = check_aggression(candidate, existing_fish)
        worst_status = prioritize_status(worst_status, aggression_status)

        if aggression_code:
            alerts.append(aggression_code)

        if not alerts:
            alerts.append("ALL_PARAMETERS_PERFECT")

        return CompatibilityChecker._build_result(
            worst_status,
            deduplicate_codes(alerts),
            aquarium_name=aquarium_row["aquarium_name"],
            fish_name=candidate.name,
        )

    @staticmethod
    def _build_result(status: StatusColor, codes: list[str], aquarium_name: str | None = None, fish_name: str | None = None) -> dict:
        return {
            "status": status.name,
            "label": status.value,
            "color": status.value,
            "codes": codes,
            "messages": [CODE_MESSAGES.get(code, code) for code in codes],
            "aquarium_name": aquarium_name,
            "fish_name": fish_name,
        }


def deduplicate_codes(codes: list[str]) -> list[str]:
    seen = set()
    result = []
    for code in codes:
        if code in seen:
            continue
        seen.add(code)
        result.append(code)
    return result


def map_aggression(value: str | None) -> AggressionLevel:
    normalized = (value or "PEACEFUL").strip().upper()
    mapping = {
        "PEACEFUL": AggressionLevel.PEACEFUL,
        "SEMI_AGGRESSIVE": AggressionLevel.SEMI_AGGRESSIVE,
        "AGGRESSIVE": AggressionLevel.AGGRESSIVE,
    }
    return mapping.get(normalized, AggressionLevel.PEACEFUL)


def infer_schooling(name: str) -> bool:
    lowered_name = name.lower()
    schooling_keywords = (
        "tetra",
        "rasbora",
        "barb",
        "danio",
        "cory",
        "corydora",
        "minnow",
        "headstander",
    )
    return any(keyword in lowered_name for keyword in schooling_keywords)


def fish_from_row(row: sqlite3.Row) -> Fish:
    return Fish(
        name=row["fish_name"],
        temp_range=(float(row["temp_min"]), float(row["temp_max"])),
        ph_range=(float(row["ph_min"]), float(row["ph_max"])),
        min_volume=float(row["size"]),
        aggression=map_aggression(row["aggression"]),
        needs_school=infer_schooling(row["fish_name"]),
    )


if __name__ == "__main__":
    my_aquarium = Aquarium(current_temp=25, current_ph=7.0, available_volume=50)
    neon_tetra = Fish("Neoninė tetra", (22, 26), (6.0, 7.0), 2, AggressionLevel.PEACEFUL, needs_school=True)
    result_tetra = CompatibilityChecker.check_compatibility(neon_tetra, my_aquarium, quantity_to_add=1)
    print(result_tetra)
