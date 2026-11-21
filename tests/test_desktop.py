"""Tests for the desktop app's detection rules, language, palettes and settings.

Run from the project folder:  .venv\\Scripts\\python.exe -m pytest
"""
import json

import pytest

from clearview import config, detection as det, language, palette, speech, storage


def detection(label, box, confidence=0.8):
    return {"label": label, "confidence": confidence, "coordinates": box}


class TestClosestObject:
    def test_largest_object_wins_over_most_confident(self):
        cup = detection("cup", [0, 0, 50, 50], confidence=0.95)
        laptop = detection("laptop", [0, 0, 400, 300], confidence=0.40)
        assert det.select_closest([cup, laptop])["label"] == "laptop"

    def test_people_are_never_the_answer_when_an_object_is_present(self):
        person = detection("person", [0, 0, 640, 480])
        book = detection("book", [500, 0, 600, 100])
        assert det.select_closest([person, book])["label"] == "book"

    def test_held_object_is_preferred_over_a_bigger_one_away_from_the_hand(self):
        hand = detection("hand", [100, 100, 200, 200])
        held_cup = detection("cup", [120, 120, 180, 180])
        far_tv = detection("tv", [400, 0, 640, 300])
        chosen = det.select_closest([hand, held_cup, far_tv])
        assert chosen["label"] == "cup"

    def test_no_detections_means_no_answer(self):
        assert det.select_closest([]) is None


class TestWornItems:
    def test_hat_on_a_person_does_not_beat_the_skis(self):
        person = detection("person", [100, 0, 300, 400])
        hat = detection("hat", [150, 0, 260, 90])
        skis = detection("skis", [80, 380, 330, 420])
        assert det.select_closest([person, hat, skis])["label"] == "skis"

    def test_a_hat_on_its_own_is_still_named(self):
        assert det.select_closest([detection("hat", [0, 0, 100, 100])])["label"] == "hat"


class TestObjectList:
    def test_lists_each_object_once_biggest_first_without_people(self):
        detections = [
            detection("cup", [0, 0, 50, 50]),
            detection("laptop", [0, 0, 400, 300]),
            detection("person", [0, 0, 640, 480]),
            detection("book", [500, 0, 600, 100]),
            detection("cup", [1, 1, 49, 49]),
        ]
        assert det.list_labels(detections) == ["laptop", "book", "cup"]

    def test_underscored_labels_are_normalised(self):
        detections = [detection("cell_phone", [0, 0, 10, 10])]
        assert det.list_labels(detections) == ["cell phone"]


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
        assert language.is_mostly_chinese(text) is expected


class TestPalettes:
    @pytest.mark.parametrize("name", list(palette.APP_COLOR_PRESETS))
    def test_every_palette_has_unique_colours(self, name):
        # Theme switching maps old colour values to new ones, so duplicates break it.
        colours = palette.APP_COLOR_PRESETS[name]
        assert len(set(colours.values())) == len(colours)

    def test_every_palette_defines_the_same_keys(self):
        keys = {frozenset(colours) for colours in palette.APP_COLOR_PRESETS.values()}
        assert len(keys) == 1

    def test_mix(self):
        assert palette.mix("#000000", "#ffffff", 0.5) == "#808080"
        assert palette.mix("#123456", "#abcdef", 0) == "#123456"


class TestEverydayObjectDetector:
    def test_desktop_model_matches_vocabulary(self):
        # If this fails, vocabulary.txt was edited without running build_detector.py.
        from ultralytics import YOLO

        from build_detector import read_vocabulary

        model = YOLO(str(config.APP_DIR / config.CLEARVIEW_MODEL_FILE))
        assert list(model.names.values()) == read_vocabulary()

    def test_every_detector_has_a_name_and_threshold(self):
        assert set(config.DETECTOR_NAMES) == set(config.DETECTOR_CONFIDENCE)


class TestCombinedDetectors:
    COCO = ["person", "cell phone", "mouse", "cup", "book", "laptop"]

    def test_yolo26_corrects_objects_it_knows(self):
        merged = det.merge_with_coco(
            [detection("cell phone", [0, 0, 100, 100], 0.52)],
            [detection("mouse", [2, 0, 102, 100], 0.49)],
            self.COCO,
        )
        assert [d["label"] for d in merged] == ["computer mouse"]

    def test_yolo26_cannot_overrule_objects_it_does_not_know(self):
        merged = det.merge_with_coco(
            [detection("wallet", [0, 0, 100, 100], 0.6)],
            [detection("cell phone", [1, 0, 101, 100], 0.7)],
            self.COCO,
        )
        assert [d["label"] for d in merged] == ["wallet"]

    def test_objects_found_by_one_model_are_kept(self):
        merged = det.merge_with_coco(
            [detection("keys", [0, 0, 100, 100], 0.5)],
            [detection("cup", [500, 0, 600, 100], 0.8)],
            self.COCO,
        )
        assert sorted(d["label"] for d in merged) == ["cup", "keys"]


class TestSettingsFile:
    def test_round_trip(self, tmp_path):
        path = tmp_path / "settings.json"
        storage.save_settings({"font_size": 26, "app_color_choice": "Blue"}, path)
        assert storage.load_settings(path) == {"font_size": 26, "app_color_choice": "Blue"}

    def test_missing_file_gives_defaults(self, tmp_path):
        assert storage.load_settings(tmp_path / "missing.json") == {}

    def test_damaged_file_gives_defaults(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text("{not json", encoding="utf-8")
        assert storage.load_settings(path) == {}

    def test_non_object_file_gives_defaults(self, tmp_path):
        path = tmp_path / "settings.json"
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        assert storage.load_settings(path) == {}


class TestSharedDescriptions:
    def test_desktop_reads_the_file_the_phone_serves(self):
        descriptions, warning = storage.load_descriptions()
        assert warning == ""
        assert descriptions["computer mouse"]
        assert config.DESCRIPTIONS_FILE.parent.name == "public"


class TestSpeechHelpers:
    def test_speed_maps_to_sapi_scale(self):
        assert speech.to_sapi_rate(1.0) == 0
        assert speech.to_sapi_rate(1.3) == 5
        assert speech.to_sapi_rate(0.7) == -5
        assert speech.to_sapi_rate(9) == 10

    def test_word_positions_count_utf16_like_windows(self):
        # An emoji takes two UTF-16 units, so later words shift in SAPI's counting.
        text = "😀 cup 烏龍茶"
        positions = speech.word_positions(text)
        assert positions[(3, 3)] == (2, 5)
        assert text[slice(*positions[(7, 3)])] == "烏龍茶"

    def test_voice_menu_labels_and_deduplicates(self):
        class Voice:
            def __init__(self, name, voice_id):
                self.name, self.Id = name, voice_id

            def GetDescription(self):
                return self.name

        class Voices:
            items = [Voice("Microsoft Zira", "z"), Voice("Microsoft David", "d"), Voice("Microsoft Zira", "z2")]
            Count = 3

            def Item(self, index):
                return self.items[index]

        assert speech.voice_menu(Voices()) == {
            "Default": None,
            "Female - Microsoft Zira": "z",
            "Male - Microsoft David": "d",
            "Female - Microsoft Zira (3)": "z2",
        }
