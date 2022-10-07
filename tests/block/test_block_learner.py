import unittest

import pytest
from pytest import MonkeyPatch, fixture

from oagdedupe._typing import StatsDict
from oagdedupe.block.learner import Conjunctions
from oagdedupe.block.optimizers import DynamicProgram
from oagdedupe.block.sql import LearnerSql


@pytest.fixture
def stats():
    return StatsDict(
        n_pairs=10,
        scheme=tuple(["scheme"]),
        rr=0.999,
        positives=100,
        negatives=1,
    )


@pytest.fixture
def statslist():
    return [
        StatsDict(
            n_pairs=100,
            scheme=tuple(["scheme"]),
            rr=0.9,
            positives=100,
            negatives=1,
        ),
        StatsDict(
            n_pairs=100,
            scheme=tuple(["scheme"]),
            rr=0.99,
            positives=1,
            negatives=100,
        ),
    ]


@pytest.fixture
def conjunctions():
    return [
        [
            StatsDict(
                n_pairs=100,
                scheme=tuple(["scheme"]),
                rr=0.9,
                positives=100,
                negatives=1,
            ),
            StatsDict(
                n_pairs=100,
                scheme=tuple(["scheme"]),
                rr=0.99,
                positives=1,
                negatives=100,
            ),
        ],
        [
            StatsDict(
                n_pairs=100,
                scheme=tuple(["scheme"]),
                rr=0.9,
                positives=100,
                negatives=1,
            ),
            StatsDict(
                n_pairs=100,
                scheme=tuple(["scheme"]),
                rr=0.99,
                positives=1,
                negatives=100,
            ),
        ],
        None,
    ]


class TestConjunctions(unittest.TestCase):
    @pytest.fixture(autouse=True)
    def prepare_fixtures(self, settings, stats, statslist, conjunctions):
        # https://stackoverflow.com/questions/22677654/why-cant-unittest-testcases-see-my-py-test-fixtures
        self.settings = settings
        self.stats = stats
        self.statslist = statslist
        self.conjunctions = conjunctions

    def setUp(self):
        self.monkeypatch = MonkeyPatch()
        self.cover = Conjunctions(settings=self.settings)
        return

    def test_get_best(self):
        def mockstats(*args, **kwargs):
            return self.stats

        with self.monkeypatch.context() as m:
            m.setattr(DynamicProgram, "score", mockstats)
            m.setattr(LearnerSql, "blocking_schemes", list(tuple(["scheme"])))
            res = self.cover.optimizer.get_best(tuple(["scheme"]))
        self.assertEqual(res[0], self.stats)

    def test_conjunctions_list(self):
        with self.monkeypatch.context() as m:
            m.setattr(Conjunctions, "_conjunctions", self.conjunctions)
            res = self.cover.conjunctions_list
        self.assertEqual(res[0].rr, 0.99)
        self.monkeypatch.delattr(Conjunctions, "_conjunctions")

    def test__check_rr(self):
        with self.monkeypatch.context() as m:
            m.setattr(LearnerSql, "min_rr", 0.9)
            res = self.cover._check_rr(self.stats)
        self.assertEqual(res, False)
