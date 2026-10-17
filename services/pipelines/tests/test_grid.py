import pytest

from domain.grid import MalformedCell, cell_id, peat_class, staged_cells

SQUARE = {
    "type": "Polygon",
    "coordinates": [[[102.0, 0.4], [102.01, 0.4], [102.01, 0.41], [102.0, 0.4]]],
}


def feature(grid_index, mode):
    return {
        "type": "Feature",
        "geometry": SQUARE,
        "properties": {"grid_index": grid_index, "peat_mode": mode},
    }


def test_cell_id_joins_region_and_grid_index():
    assert cell_id("riau", "160,38") == "riau-160-38"


@pytest.mark.parametrize("grid_index", ["160", "160,38,1", "a,b", "", "160;38", None])
def test_a_malformed_grid_index_raises(grid_index):
    with pytest.raises(MalformedCell):
        cell_id("riau", grid_index)


@pytest.mark.parametrize(("mode", "expected"), [(1.0, 1), (2, 2), (2.0, 2)])
def test_peat_modes_one_and_two_are_peat_classes(mode, expected):
    assert peat_class(mode) == expected


@pytest.mark.parametrize("mode", [0, 3, 1.5, None])
def test_other_modes_are_not_peat(mode):
    assert peat_class(mode) is None


def test_staged_cells_keep_only_peat_and_carry_the_geometry():
    features = [feature("160,38", 1), feature("161,38", 0), feature("162,38", 2.0)]

    cells = staged_cells("riau", features)

    assert [(c.cell_id, c.peat_class) for c in cells] == [
        ("riau-160-38", 1),
        ("riau-162-38", 2),
    ]
    assert cells[0].region == "riau"
    assert cells[0].geometry == SQUARE


def test_a_duplicate_cell_raises():
    with pytest.raises(MalformedCell, match="riau-160-38"):
        staged_cells("riau", [feature("160,38", 1), feature("160,38", 2)])


def test_a_feature_without_geometry_raises():
    broken = {
        "type": "Feature",
        "geometry": None,
        "properties": feature("1,2", 1)["properties"],
    }

    with pytest.raises(MalformedCell):
        staged_cells("riau", [broken])
