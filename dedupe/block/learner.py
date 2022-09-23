from dedupe.db.database import DatabaseORM,DatabaseCore
from dedupe.settings import Settings

from dataclasses import dataclass
from typing import List
from functools import lru_cache, cached_property
import pandas as pd
import itertools
from multiprocessing import Pool
import logging

class InvertedIndex:
    """
    Used to build inverted index. An inverted index is dataframe 
    where keys are signatures and values are arrays of entity IDs
    """

    def get_pairs(self, names, table):
        """
        Given forward index, construct inverted index. 
        Then for each row in inverted index, get all "nC2" distinct 
        combinations of size 2 from the array. Concatenates and 
        returns all distinct pairs.

        Parameters
        ----------
        names : List[str]
            list of block schemes
        table : str
            table name of forward index

        Returns
        ----------
        pd.DataFrame
        """
        return self.db.get_inverted_index_pairs(names,table)

    def get_pairs_in_memory(self, names, table):
        """
        same as get_pairs() but runs in-memory;
        faster and used when searching for best conjunctions

        Parameters
        ----------
        names : List[str]
            list of block schemes
        table : str
            table name of forward index

        Returns
        ----------
        pd.Dataframe
        """
        inverted_index = self.db.get_inverted_index(names,table)

        return pd.DataFrame([ 
                y
                for x in list(inverted_index["array_agg"])
                for y in list(itertools.combinations(x, 2))
            ], columns = ["_index_l","_index_r"]
        ).assign(blocked=True).drop_duplicates()

class DynamicProgram(InvertedIndex):
    """
    Given a block scheme, use dynamic programming algorithm getBest()
    to construct best conjunction
    """

    def get_stats(self, names, n_pairs, coverage):
        """
        Evaluate conjunction performance by:
            - percentage of positive / negative labels that are blocked;
            uses blocks_train
            - get comparisons using train data to compute reduction ratio;
            uses blocks_train

        Parameters
        ----------
        names: List[str]
            list of block schemes
        n_pairs: int
            number of comparison pairs obtained from train data
        coverage: pd.DataFrame
            labelled data merged with comparison pairs obtained from 
            train data; contains binary column blocked, which is 1 if 
            the labelled pair was blocked and 0 if it was not blocked;
            used to compute percent of positive and negative labels covered

        Returns
        ----------
        dict
            returns statistics evaluating the conjunction: 
                - reduction ratio
                - percent of positive pairs blocked
                - percent of negative pairs blocked
                - number of pairs generated
                - length of conjunction
        """
        
        n = self.settings.other.n
        n_comparisons = (n * (n-1))/2

        return {
            "scheme": names,
            "rr":1 - (n_pairs / (n_comparisons)),
            "positives":coverage.loc[coverage["label"]==1, "blocked"].mean(),
            "negatives":coverage.loc[coverage["label"]==0, "blocked"].mean(),
            "n_pairs": n_pairs,
            "n_scheme": len(names)
        }

    def get_coverage(self, names):
        """
        Get comparisons using train data then merge with labelled data. 

        Parameters
        ----------
        names: List[str]
            list of block schemes

        Returns
        ----------
        dict
            returns statistics evaluating the conjunction: 
                - reduction ratio
                - percent of positive pairs blocked
                - percent of negative pairs blocked
                - number of pairs generated
                - length of conjunction
        """

        train_pairs = self.get_pairs_in_memory(
            names=names, 
            table="blocks_train"
        )
        
        coverage = self.db.get_labels().merge(train_pairs, how = 'left')
        coverage = coverage.fillna(0)
        
        return self.get_stats(
            names=names, n_pairs=len(train_pairs), coverage=coverage
        )

    @lru_cache
    def score(self, arr:tuple):
        """
        Wraps get_coverage() function with @lru_cache decorator for caching.

        Parameters
        ----------
        arr: tuple
            tuple of block schemes
        """
        return self.get_coverage(names=list(arr))

    def getBest(self, scheme:tuple):
        """
        Dynamic programming implementation to get best conjunction.

        Parameters
        ----------
        scheme: tuple
            tuple of block schemes
        """

        dp = [None for _ in range(self.settings.other.k)]
        dp[0] = self.score(scheme)

        if (dp[0]["positives"] == 0) or (dp[0]["rr"] < 0.99) or (dp[0]["rr"] == 1):
            return None

        for n in range(1,self.settings.other.k):

            scores = [
                self.score(
                    tuple(sorted(dp[n-1]["scheme"] + [x]))
                ) 
                for x in self.db.blocking_schemes
                if x not in dp[n-1]["scheme"]
            ]

            scores = [
                x
                for x in scores
                if (x["positives"] > 0) & \
                    (x["rr"] < 1) & (x["n_pairs"] > 1) & \
                    (sum(["_ngrams" in _ for _ in x["scheme"]]) <= 1)
            ]
            
            if len(scores) == 0:
                return dp[:n]

            dp[n] = max(
                scores, 
                key=lambda x: (
                    x["rr"], 
                    x["positives"], 
                    -x["negatives"],
                    -x["n_scheme"]
                )
            )

        return dp

class Conjunctions(DynamicProgram):
    """
    For each block scheme, get the best block scheme conjunctions of 
    lengths 1 to k using greedy dynamic programming approach.
    """

    def __init__(self, settings):
        self.settings = settings
        self.db = DatabaseCore(settings=self.settings)
    
    @property
    def conjunctions(self):
        """
        Computes conjunctions for each block scheme in parallel
        """
        p = Pool(self.settings.other.cpus)
        res = p.map(
            self.getBest, 
            [tuple([o]) for o in self.db.blocking_schemes]
        )
        p.close()
        p.join()
        return res
    
    @cached_property
    def df_conjunctions(self):
        """
        DataFrame containing best conjunctions and their stats
        """
        df = pd.concat([
            pd.DataFrame(r)
            for r in self.conjunctions
        ]).reset_index(drop=True)
        return df.loc[
            df.astype(str).drop_duplicates().index
        ].sort_values("rr", ascending=False)

    def best_schemes(self, n_covered):
        """
        Subset of best conjunctions such that n_covered samples 
        are covered by the block conjunctions.

        Parameters
        ----------
        n_covered: int
            number of samples to be cumulatively covered
        """
        logging.info(f"getting best conjunctions")        
        best_schemes = self.df_conjunctions.copy()
        return best_schemes.loc[
            best_schemes["n_pairs"].cumsum()<n_covered, 
            "scheme"
        ]

    @property
    def newtablemap(self):
        return {
            "comparisons":self.orm.Comparisons,
            "full_comparisons":self.orm.FullComparisons
        }

    def get_comparisons(
            self, 
            table, 
            n_covered
        ):
        """
        Applies subset of best conjunction to obtain comparison pairs.

        Parameters
        ----------
        table: str
            get pairs from table (either blocks_train for sample or 
            blocks_df for full df)
        n_covered: int
            number of records that the conjunctions should cover
        """
        return pd.concat([
            self.get_pairs(names=x, table=table)  
            for x in self.best_schemes(n_covered=n_covered)
        ]).drop(["blocked"], axis=1).drop_duplicates()

    def save_best(
        self, 
        table, 
        newtable,
        n_covered
    ):
        """
        Applies subset of best conjunction to obtain comparison pairs.

        Parameters
        ----------
        table: str
            get pairs from table (either blocks_train for sample or 
            blocks_df for full df)
        newtable: str
            table to save output (either comparisons for sample or 
            full_comparisons for full df)
        n_covered: int
            number of records that the conjunctions should cover
        """
        
        comparisons = self.get_comparisons(table=table,n_covered=n_covered)
        
        self.orm = DatabaseORM(settings=self.settings)
        
        self.orm.truncate_table(newtable)
        self.orm.bulk_insert(
            df=comparisons, to_table=self.newtablemap[newtable]
        )