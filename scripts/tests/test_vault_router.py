import pytest
from utils.vault_router import folder_for_type, FOLDER_BY_TYPE

def test_maps_known_types():
    assert folder_for_type("project") == "projects"
    assert folder_for_type("decision") == "decisions"
    assert folder_for_type("pattern") == "patterns"
    assert folder_for_type("reference") == "references"
    assert folder_for_type("concept") == "concepts"
    assert folder_for_type("journal") == "journal"

def test_rejects_unknown_type():
    with pytest.raises(ValueError):
        folder_for_type("banana")

def test_all_types_have_folders():
    assert set(FOLDER_BY_TYPE) == {"project","decision","pattern","reference","concept","journal"}
