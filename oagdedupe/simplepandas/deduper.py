"""
top-level API for this simple dedupe version
"""

from .concepts import (
    Record,
    Entity,
    LabelRepository,
    ConjunctionFinder,
    Attribute,
    Clusterer,
    Classifier,
    Pair,
    Label,
    Conjunction,
    ActiveLearner,
)
from .subroutines import get_pairs
from typing import Set, Generator

from pandera.typing import DataFrame, Series
from pandera import DataFrameSchema, Column, check_types

from dataclasses import dataclass


@dataclass
class Deduper:
    attributes: Set[Attribute]
    records: DataFrame[Record]
    label_repo: LabelRepository
    conj_finder: ConjunctionFinder
    classifier: Classifier
    active_learner: ActiveLearner
    clusterer: Clusterer
    limit_pairs: int = 1000
    limit_conjunctions: int = 3

    def __post_init__(self):
        self.schema.validate(self.records)

    @property
    def schema(self) -> DataFrameSchema:
        return DataFrameSchema(
            {
                Record.id: Column(int),
                **{attr: Column(str) for attr in self.attributes},
            }
        )

    @property  # type: ignore
    @check_types
    def labels(self) -> DataFrame[Label]:
        return self.label_repo.get()

    @property
    def sample(self) -> DataFrame:
        return self.records.sample(min(5000, len(self.records)))

    @property
    def conjunctions(self) -> Generator[Conjunction, None, None]:
        return self.conj_finder.get_best_conjunctions(
            records=self.sample, attributes=self.attributes, labels=self.labels
        )

    @property
    def learn(self) -> Classifier:
        return self.classifier.learn(
            records=self.records, attrbutes=self.attributes, labels=self.labels
        )

    @check_types
    def get_pairs(self, records: DataFrame) -> DataFrame[Pair]:
        return get_pairs(
            records=records,
            conjs=self.conjunctions,
            limit_pairs=self.limit_pairs,
            limit_conjunctions=self.limit_conjunctions,
        )

    @property  # type: ignore
    @check_types
    def next_to_label(self) -> DataFrame[Pair]:
        self.learn()
        self.active_learner(
            predictions=self.classifier.predict(
                records=self.records,
                attributes=self.attributes,
                pairs=self.get_pairs(records=self.sample),
            )
        ).get_next_to_label()

    @property
    def ids(self) -> Series[int]:
        return self.records[Record.id]

    @property  # type: ignore
    @check_types
    def entities(self) -> DataFrame[Entity]:
        pairs = self.get_pairs(records=self.records)
        self.learn()
        return self.clusterer.get_clusters(
            predictions=self.classifier.predict(pairs)
        )


# %%
# there are separate tracks:
# - learn a good conjunction from sample and labels
# - learn a classifier from labels
# - use a good conjuction and classifier to cluster on all data

# Process:
# 1. take a sample
# 2. generate the best conjunctions from the sample and labels
# 3. get some pairs from the top best conjunctions
# 4. learn a good classifier from the labels
# 5. decide from the classifier what to label next from the pairs
# 6. label
# 7. repeat from 1, or
# 8. do steps 1 through 5
# 9. get all pairs from the top best conjunctions
# 10. classify all of those pairs
# 11. cluster all of those pairs