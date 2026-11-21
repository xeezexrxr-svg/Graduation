"""Tests for the desktop app's detection choice, language and settings logic.

Run from the project folder:  .venv\\Scripts\\python.exe -m pytest
"""
import json

import pytest

import app
from app import AnalysisWorker


def detection(label, box, confidence=0.8):
    return {"label": label, "confidence": confidence, "coordinates": box}


class TestClosestObject:
    def test_largest_object_wins_over_most_confident(self):
        cup = detection("cup", [0, 0, 50, 50], confidence=0.95)
        laptop = detection("laptop", [0, 0, 400, 300], confidence=0.40)
        assert AnalysisWorker._select_detection([cup, laptop])["label"] == "laptop"

    def test_people_are_never_the_answer_when_an_object_is_present(self):
        person = detection("person", [0, 0, 640, 480])
        book = detection("book", [500, 0, 600, 100])
        assert AnalysisWorker._select_detection([person, book])["label"] == "book"

    def test_held_object_is_preferred_over_a_bigger_one_away_from_the_hand(self):
        hand = detection("hand", [100, 100, 200, 200])
        held_cup = detection("cup", [120, 120, 180, 180])
        far_tv = detection("tv", [400, 0, 640, 300])
        chosen = AnalysisWorker._select_detection([hand, held_cup, far_tv])
        assert chosen["label"] == "cup"

    def test_no_detections_means_no_answer(self):
        assert AnalysisWorker._select_detection([]) is None


class TestObjectList:
    def test_lists_each_object_once_biggest_first_without_people(self):
        detections = [
            detection("cup", [0, 0, 50, 50]),
            detection("laptop", [0, 0, 400, 300]),
            detection("person", [0, 0, 640, 480]),
            detection("book", [500, 0, 600, 100]),
            detection("cup", [1, 1, 49, 49]),
        ]
        assert AnalysisWorker._list_labels(detections) == ["laptop", "book", "cup"]

    def test_underscored_labels_are_normalised(self):
        detections = [detection("cell_phone", [0, 0, 10, 10])]
        assert AnalysisWorker._list_labels(detections) == ["cell phone"]


class TestChineseDetection:
    @pytest.mark.parametrize(
        "text, expected",
        [
            ("營養標示 熱量 蛋白質", True),
            ("This is a cup.", False),
            ("營養標示 Nutrition facts per serving", False),
            ("烏龍茶 Oolong", True),
            ("", False),
        ],
    )
    def test_is_mostly_chinese(self, text, expected):
        assert app.is_mostly_chinese(text) is expected


class TestPalettes:
    @pytest.mark.parametrize("name", list(app.APP_COLOR_PRESETS))
    def test_every_palette_has_unique_colours(self, name):
        # Theme switching maps old colour values to new ones, so duplicates break it.
        palette = app.APP_COLOR_PRESETS[name]
        assert len(set(palette.values())) == len(palette)

    def test_every_palette_defines_the_same_keys(self):
        keys = {frozenset(palette) for palette in app.APP_COLOR_PRESETS.values()}
        assert len(keys) == 1

    def test_mix(self):
        assert app._mix("#000000", "#ffffff", 0.5) == "#808080"
        assert app._mix("#123456", "#abcdef", 0) == "#123456"


class TestSettingsFile:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "settings.json"
        app.save_settings({"font_size": 26, "app_color_choice": "Blue"}, path)
        assert app.load_settings(path) == {"font_size": 26, "app_color_choice": "Blue"}

    def test_missing_file_gives_defaults(self, tmp_path):
        assert app.load_settings(tmp_path / "missing.json") == {}

    def test_damaged_file_gives_defaults(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("{not json", encoding="utf-8")
        assert app.load_settings(path) == {}

    def test_non_object_file_gives_defaults(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        assert app.load_settings(path) == {}
