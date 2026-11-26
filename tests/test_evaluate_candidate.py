import sqlite3
from contextlib import closing, contextmanager

import pytest
from app.services import aquarium_indicator_logic as logic


@contextmanager
def db_connection(db_path):
    # sqlite3.Connection kaip konteksto valdiklis pats ryšio neuždaro.
    # Todėl aiškiai uždarome ryšį, o transakciją patvirtiname/atšaukiame.
    with closing(sqlite3.connect(db_path)) as connection:
        with connection:
            yield connection


@pytest.fixture
def candidate_db(tmp_path, monkeypatch):
    db_path = tmp_path / "aquarium_test.db"
    monkeypatch.setattr(logic, "APP_DB", str(db_path))
    with db_connection(db_path) as connection:
        connection.executescript("""
            CREATE TABLE aquarium (id INTEGER PRIMARY KEY, aquarium_name TEXT, volume REAL);
            CREATE TABLE fish_list (
                id INTEGER PRIMARY KEY, fish_name TEXT, aggression TEXT, size REAL,
                temp_min REAL, temp_max REAL, ph_min REAL, ph_max REAL
            );
            CREATE TABLE fish_in_aquarium (aquarium_id INTEGER, fish_id INTEGER);
        """)
        connection.execute("INSERT INTO aquarium VALUES (1, 'Testinis', 50)")
        connection.execute(
            "INSERT INTO fish_list VALUES (1, 'Gupija', 'PEACEFUL', 5, 23, 27, 6.5, 7.5)"
        )
    return db_path


def insert_fish(db_path, *, fish_id=2, name="Kita", aggression="PEACEFUL",
                size=5, temp=(23, 27), ph=(6.5, 7.5), in_aquarium=True):
    with db_connection(db_path) as connection:
        connection.execute(
            "INSERT INTO fish_list VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (fish_id, name, aggression, size, temp[0], temp[1], ph[0], ph[1]),
        )
        if in_aquarium:
            connection.execute("INSERT INTO fish_in_aquarium VALUES (1, ?)", (fish_id,))


def update_candidate(db_path, **fields):
    allowed = {"fish_name", "aggression", "size", "temp_min", "temp_max", "ph_min", "ph_max"}
    assert set(fields) <= allowed
    with db_connection(db_path) as connection:
        for field, value in fields.items():
            connection.execute(f"UPDATE fish_list SET {field} = ? WHERE id = 1", (value,))


def evaluate(aquarium_id=1, fish_id=1, quantity=1):
    return logic.CompatibilityChecker.evaluate_candidate_for_aquarium(
        aquarium_id, fish_id, quantity
    )


def assert_result(result, status, codes, *, names=True):
    assert result["status"] == status
    assert result["label"] == logic.StatusColor[status].value
    assert result["color"] == logic.StatusColor[status].value
    assert result["codes"] == codes
    assert result["messages"] == [logic.CODE_MESSAGES[code] for code in codes]
    if names:
        assert result["aquarium_name"] == "Testinis"
        assert result["fish_name"] == "Gupija"


def test_fish_not_found(candidate_db):
    assert_result(evaluate(fish_id=999), "RED", ["PREDATOR_ALERT"], names=False)


def test_aquarium_not_found(candidate_db):
    assert_result(evaluate(aquarium_id=999), "RED", ["VOLUME_LIMIT_EXCEEDED"], names=False)


def test_empty_aquarium_peaceful(candidate_db):
    assert_result(evaluate(), "GREEN", ["ALL_PARAMETERS_PERFECT", "AQUARIUM_EMPTY"])


def test_empty_aquarium_aggressive(candidate_db):
    update_candidate(candidate_db, aggression="AGGRESSIVE")
    assert_result(evaluate(), "RED", ["PREDATOR_ALERT", "AQUARIUM_EMPTY"])


def test_existing_fish_compatible(candidate_db):
    insert_fish(candidate_db, temp=(23, 27), ph=(6.5, 7.5))
    result = evaluate()
    assert result["status"] in ("GREEN", "YELLOW")


def test_existing_fish_temperature_mismatch(candidate_db):
    insert_fish(candidate_db, temp=(15, 18))
    result = evaluate()
    assert "TEMP_MISMATCH_CRITICAL" in result["codes"]


def test_existing_fish_ph_mismatch(candidate_db):
    insert_fish(candidate_db, ph=(8.5, 9.0))
    result = evaluate()
    assert "PH_MISMATCH_CRITICAL" in result["codes"]


def test_existing_fish_aggressive(candidate_db):
    insert_fish(candidate_db, aggression="AGGRESSIVE")
    result = evaluate()
    assert "PREDATOR_ALERT" in result["codes"]


def test_volume_and_social_requirements(candidate_db):
    update_candidate(candidate_db, size=100)
    result = evaluate(quantity=1)
    assert "VOLUME_LIMIT_EXCEEDED" in result["codes"]



