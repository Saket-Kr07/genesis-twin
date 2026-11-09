"""Quick self-check:  python test_predict.py   (works with or without a trained model)."""
from predict import predict_health, ORGAN_IDS
from age_progression import age_progression
from twin_comparison import compare_twins

LABELS = {"measured", "model_predicted", "illustrative"}


def main():
    r = predict_health(40, "male", 7, 150, "never", 4)
    assert list(r["organs"]) == ORGAN_IDS, "organ IDs/order changed!"
    assert 0 <= r["overall_health"]["score"] <= 100
    for organ, o in r["organs"].items():
        assert 0 <= o["score"] <= 100, organ
        assert o["score_label"] in LABELS, organ
        for v in o["vitals"].values():
            assert v["label"] in LABELS, organ

    good = predict_health(40, "male", 8, 200, "never", 5)["overall_health"]["score"]
    bad = predict_health(40, "male", 5, 0, "current", 1)["overall_health"]["score"]
    assert good > bad, "healthy lifestyle should score higher"

    tl = age_progression("female", 7.5, 150, "never", 3)["timeline"]
    assert tl[0]["age"] == 20 and tl[-1]["age"] == 80
    assert tl[0]["overall"] > tl[-1]["overall"], "health should decline with age"

    c = compare_twins(dict(age=40, sex="male", sleep=5, exercise=0, smoking="current", diet=1),
                      dict(age=40, sex="male", sleep=8, exercise=200, smoking="never", diet=5))
    assert c["overall"]["difference"] > 0

    try:
        predict_health(10, "male", 7, 100, "never", 3)
        raise AssertionError("age 10 should be rejected")
    except ValueError:
        pass
    print("All checks passed. Mode:", r["model_info"]["mode"])


if __name__ == "__main__":
    main()
