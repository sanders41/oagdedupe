import unittest
from oagdedupe.settings import (
    Settings,
    SettingsOther,
    SettingsService,
    SettingsLabelStudio,
)
from oagdedupe.block.learner import Conjunctions, DynamicProgram
from oagdedupe.block.sql import LearnerSql
import pytest
from pytest import fixture
from pytest import MonkeyPatch

@pytest.fixture
def stats():
    return {
        "n_pairs":10, 
        "scheme":tuple(["scheme"]), 
        "rr":.999,
        "positives":100,
        "negatives":1
    }

@pytest.fixture
def statslist():
    return [
        {
            "n_pairs":100, 
            "scheme":tuple(["scheme"]), 
            "rr":.9,
            "positives":100,
            "negatives":1
        },
        {
            "n_pairs":100, 
            "scheme":tuple(["scheme"]), 
            "rr":.99,
            "positives":1,
            "negatives":100
        }
    ]

@pytest.fixture
def conjunctions():
    return [
        [
            {
                "n_pairs":100, 
                "scheme":tuple(["scheme"]), 
                "rr":.9,
                "positives":100,
                "negatives":1
            },
            {
                "n_pairs":100, 
                "scheme":tuple(["scheme"]), 
                "rr":.99,
                "positives":1,
                "negatives":100
            }
        ],
        [
            {
                "n_pairs":100, 
                "scheme":tuple(["scheme"]), 
                "rr":.9,
                "positives":100,
                "negatives":1
            },
            {
                "n_pairs":100, 
                "scheme":tuple(["scheme"]), 
                "rr":.99,
                "positives":1,
                "negatives":100
            }
        ],
        None
    ]

@fixture
def settings(tmp_path) -> Settings:
    return Settings(
        name="test",
        folder=tmp_path,
        other=SettingsOther(
            n=5000,
            k=3,
            cpus=15,
            attributes=["name", "addr"],
            path_database="test.db",
            db_schema="dedupe",
            path_model=tmp_path / "test_model",
            label_studio=SettingsLabelStudio(
                port=8089,
                api_key="test_api_key",
                description="test project",
            ),
            fast_api=SettingsService(port=8003),
        ),
    )

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

    def test_get_stats(self):

        def mockstats(*args, **kwargs):
            return {
                "n_pairs":10, 
                "positives":100,
                "negatives":1
            }
            
        self.monkeypatch.setattr(LearnerSql,"get_inverted_index_stats", mockstats)
        self.monkeypatch.setattr(LearnerSql,"n_comparisons", 10_000)

        res = self.cover.get_stats(
            names=tuple(["scheme"]), 
            table="table"
        )
        
        self.assertDictEqual(res, self.stats)
    
    def test__keep_if(self):
        self.assertEqual(self.cover._keep_if(self.stats), True)
        

    def test__max_key(self):
        maxstat = max(self.statslist, key=self.cover._max_key)
        self.assertEqual(maxstat["rr"], 0.99)
        
    def test__filter_and_sort(self):
        dp = self.cover._filter_and_sort(
            dp=self.statslist, 
            n=1, 
            scores=self.statslist
        )
        self.assertEqual(dp[-1]["rr"], 0.99)

    def test_get_best(self):
        def mockstats(*args, **kwargs):
            return self.stats
        self.monkeypatch.setattr(DynamicProgram,"score", mockstats)
        self.monkeypatch.setattr(LearnerSql,"blocking_schemes", list(tuple(["scheme"])))
        res = self.cover.get_best(tuple(["scheme"]))
        self.assertDictEqual(res[0], self.stats)

    def test_conjunctions_list(self):
        self.monkeypatch.setattr(Conjunctions,"_conjunctions", self.conjunctions)
        res = self.cover.conjunctions_list
        self.assertEqual(res[0]["rr"], 0.99)

    def test__check_rr(self):
        self.monkeypatch.setattr(LearnerSql,"min_rr", 0.9)
        res = self.cover._check_rr(self.stats)
        self.assertEqual(res, False)