"""Tests for voice sentiment detection."""

import pytest

from voice_input import SentimentDetector


class TestSentimentDetector:
    def setup_method(self):
        self.detector = SentimentDetector()

    def test_praise_good_job(self):
        label, conf = self.detector.detect("Good job Alice!")
        assert label == "praise"
        assert conf > 0

    def test_praise_thank_you(self):
        label, _ = self.detector.detect("Thank you")
        assert label == "praise"

    def test_praise_awesome(self):
        label, _ = self.detector.detect("That was awesome")
        assert label == "praise"

    def test_scold_no(self):
        label, _ = self.detector.detect("No, not there!")
        assert label == "scold"

    def test_scold_stop(self):
        label, _ = self.detector.detect("Stop doing that")
        assert label == "scold"

    def test_scold_wrong(self):
        label, _ = self.detector.detect("That's wrong")
        assert label == "scold"

    def test_scold_put_it_back(self):
        label, _ = self.detector.detect("Put it back")
        assert label == "scold"

    def test_question_what(self):
        label, _ = self.detector.detect("What is that over there?")
        assert label == "question"

    def test_question_can_you(self):
        label, _ = self.detector.detect("Can you grab the cup?")
        assert label == "question"

    def test_neutral(self):
        label, _ = self.detector.detect("The weather is warm today")
        assert label == "neutral"

    def test_empty_string(self):
        label, _ = self.detector.detect("")
        assert label == "neutral"

    def test_praise_stronger_than_scold(self):
        """When both keywords present, stronger signal wins."""
        label, _ = self.detector.detect("Well done, thank you, awesome, perfect!")
        assert label == "praise"

    def test_scold_stronger_than_praise(self):
        label, _ = self.detector.detect("No stop wrong bad!")
        assert label == "scold"

    def test_confidence_scales(self):
        _, conf_single = self.detector.detect("thanks")
        _, conf_multi = self.detector.detect("thanks awesome perfect")
        assert conf_multi >= conf_single

    def test_case_insensitive(self):
        label, _ = self.detector.detect("GOOD JOB")
        assert label == "praise"

    def test_punctuation_stripped(self):
        label, _ = self.detector.detect("Thank you!!!")
        assert label == "praise"
