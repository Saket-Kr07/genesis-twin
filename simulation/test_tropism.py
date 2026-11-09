"""Tests for tropism.py and the tropism option of simulate_custom. The tables here are SYNTHETIC."""
import json

import pytest

from fitting import tissue_to_organ
from pathogen import MODEL_VERSION, ORGAN_IDS, model_info, simulate_custom, simulate_custom_timeline, simulate_pathogen
from tropism import main, read_expression_table, tropism_from_expression

TABLE = ("Gene\tGene name\tTissue\tCell type\tLevel\tReliability\n"
         "A1\tGENEA\tlung\tx\tHigh\tr\nA1\tGENEA\tlung\ty\tLow\tr\nA1\tGENEA\tkidney\tx\tMedium\tr\n"
         "A1\tGENEA\tliver\tx\tNot detected\tr\nA1\tGENEA\tskeletal muscle\tx\tLow\tr\n"
         "A1\tGENEA\theart muscle\tx\tNot representative\tr\nB2\tGENEB\tbrain\tx\tHigh\tr\n")
PARAMS = {"growth_rate": 1.2, "decay_rate": 0.6, "peak_day": 4.0}


def test_levels_become_tropism_numbers():
    r = tropism_from_expression(TABLE, gene="GENEA", source="synthetic")
    assert r["tropism"]["lungs"] == 0.9 and r["tropism"]["kidneys"] == 0.6 and r["tropism"]["liver"] == 0.0
    assert r["source"] == "synthetic" and set(r["tropism"]) == set(ORGAN_IDS)


def test_highest_value_wins_when_several_rows_map_to_one_organ():
    r = tropism_from_expression(TABLE, gene="GENEA")
    assert r["evidence"]["lungs"]["value"] == "High"


def test_gene_filter_ignores_other_genes():
    r = tropism_from_expression(TABLE, gene="GENEA")
    assert r["tropism"]["brain"] == 0.05 and "brain" in r["no_data_organs"]


def test_not_representative_is_ignored_and_not_detected_counts_as_data():
    r = tropism_from_expression(TABLE, gene="GENEA")
    assert "heart" in r["no_data_organs"]
    assert "liver" in r["organs_from_data"] and r["tropism"]["liver"] == 0.0


def test_unmapped_tissues_are_listed():
    assert tropism_from_expression(TABLE, gene="GENEA")["unmapped_tissues"] == ["skeletal muscle"]


def test_numbers_are_scaled_so_the_top_tissue_is_0_9():
    r = tropism_from_expression({"lung": 50, "kidney": 25, "liver": 0})
    assert r["tropism"]["lungs"] == 0.9 and r["tropism"]["kidneys"] == 0.45 and r["tropism"]["liver"] == 0.0


def test_pairs_and_dicts_and_default_value():
    r = tropism_from_expression([("lung", "Low")], default=0.1)
    assert r["tropism"]["lungs"] == 0.3 and r["tropism"]["heart"] == 0.1


@pytest.mark.parametrize("bad", [
    "", "Tissue,Colour\nlung,red", "Gene name,Level\nX,High", {"lung": "very high"}, {"lung": -1}, {"lung": "Low", "kidney": 5},
    {"x": "Not representative"}, 5,
])
def test_bad_tables_raise_plain_errors(bad):
    with pytest.raises(ValueError):
        tropism_from_expression(bad)


def test_missing_gene_raises():
    with pytest.raises(ValueError):
        read_expression_table(TABLE, gene="NOTAGENE")


@pytest.mark.parametrize("name,organ", [
    ("cerebral cortex", "brain"), ("nasopharynx", "lungs"), ("small intestine", "intestines"),
    ("urinary bladder", "bladder"), ("lymph node", "spleen"), ("endometrium", "reproductive"),
    ("adrenal gland", "thyroid"), ("gallbladder", "liver"), ("heart muscle", "heart"), ("thyroid gland", "thyroid"),
])
def test_tissue_names_map_to_the_right_organ(name, organ):
    assert tissue_to_organ(name) == organ


def test_unknown_tissue_has_no_organ():
    assert tissue_to_organ("skeletal muscle") is None


def test_simulate_custom_uses_the_tropism():
    lungs = tropism_from_expression({"lung": "High"})["tropism"]
    gut = tropism_from_expression({"small intestine": "High"})["tropism"]
    a = simulate_custom(PARAMS, [], 8, 0.0, tropism=lungs)["organs"]
    b = simulate_custom(PARAMS, [], 8, 0.0, tropism=gut)["organs"]
    assert a["lungs"]["score"] < a["intestines"]["score"]
    assert b["intestines"]["score"] < b["lungs"]["score"]
    tl = simulate_custom_timeline(PARAMS, [], 0.0, tropism=lungs)
    assert min(tl["scores"]["lungs"]) < min(tl["scores"]["intestines"])


def test_tropism_overrides_target_organs():
    out = simulate_custom(PARAMS, ["lungs"], 8, 0.0, tropism={"intestines": 0.9})["organs"]
    assert out["intestines"]["score"] < out["lungs"]["score"]


@pytest.mark.parametrize("bad", [{"heart_valve": 0.5}, {"lungs": 2}, {"lungs": "x"}, [0.5]])
def test_bad_tropism_is_rejected(bad):
    with pytest.raises(ValueError):
        simulate_custom(PARAMS, ["lungs"], 8, 0.0, tropism=bad)


def test_model_version_is_in_every_result_and_in_model_info():
    assert simulate_pathogen("gut_virus", 3, 0.0)["model_version"] == MODEL_VERSION
    assert simulate_custom(PARAMS, ["lungs"], 3, 0.0)["model_version"] == MODEL_VERSION
    info = model_info()
    assert info["model_version"] == MODEL_VERSION and set(info["presets"]) == {
        "respiratory_virus", "gut_virus", "bloodstream_bacterium"}
    info["presets"]["gut_virus"]["params"]["beta"] = 99          # a changed copy must not change the model
    assert model_info()["presets"]["gut_virus"]["params"]["beta"] != 99


def test_command_line_writes_a_json_file(tmp_path, capsys):
    table = tmp_path / "t.tsv"
    table.write_text(TABLE)
    out = tmp_path / "out.json"
    assert main(["--file", str(table), "--gene", "GENEA", "--label", "synthetic", "--out", str(out)]) == 0
    assert json.loads(out.read_text())["tropism"]["lungs"] == 0.9 and "Source: synthetic" in capsys.readouterr().out
