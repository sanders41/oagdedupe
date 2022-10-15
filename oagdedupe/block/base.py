from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional, Tuple

from dependency_injector.wiring import Provide

from oagdedupe._typing import StatsDict
from oagdedupe.block.schemes import BlockSchemes
from oagdedupe.containers import SettingsContainer
from oagdedupe.db.base import BaseComputeBlocking
from oagdedupe.settings import Settings


@dataclass
class BaseOptimizer(ABC, BlockSchemes):
    """Abstract base class for all conjunction optimizing algorithms to inherit"""

    compute: BaseComputeBlocking
    settings: Settings = Provide[SettingsContainer.settings]

    @abstractmethod
    def get_best(self, scheme: Tuple[str]) -> Optional[List[StatsDict]]:
        return


@dataclass
class BaseForward(ABC, BlockSchemes):
    compute: BaseComputeBlocking
    settings: Settings = Provide[SettingsContainer.settings]

    @abstractmethod
    def build_forward_indices(self):
        return


@dataclass
class BaseConjunctions(ABC, BlockSchemes):
    optimizer: BaseOptimizer
    settings: Settings = Provide[SettingsContainer.settings]

    @property
    @abstractmethod
    def conjunctions_list(self):
        return


@dataclass
class BasePairs(ABC):
    compute: BaseComputeBlocking
    settings: Settings = Provide[SettingsContainer.settings]

    @abstractmethod
    def add_new_comparisons(self):
        return
