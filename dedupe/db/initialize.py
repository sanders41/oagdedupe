from dedupe.settings import Settings
from dedupe.distance.string import RayAllJaro
from dedupe.db.tables import Tables
from sqlalchemy import select, insert, func

import itertools
from dataclasses import dataclass
import logging

@dataclass
class Initialize(Tables):
    settings:Settings
    """
    Object used to initialize SQL tables using sqlalchemy

    Can be used to create:
        - df
        - sample
            - random sample of df of size settings.other.n, drawn each 
            active learning loop
        - pos/neg
            - created to help build train and labels; 
            - pos contains a random sample repeated 4 times
            - neg contains 10 random samples
        - train
            - combines pos and neg
        - labels
            - gets all distinct pairwise comparisons from train
            - pairs from pos are labelled as a match
            - pairs from neg are labelled as a non-match
    """

    def _init_df(self, df):
        logging.info(f"Building table {self.settings.other.db_schema}.df.")
        with self.Session() as session:
            session.bulk_insert_mappings(
                self.maindf, 
                df.to_dict(orient='records')
            )
            session.commit()

    def _init_sample(self):
        logging.info(f"Building table {self.settings.other.db_schema}.sample.")
        with self.Session() as session:
            sample = (
                select([self.maindf])
                .order_by(func.random())
                .limit(self.settings.other.n)
            )
            session.execute(
                insert(self.Sample).from_select(sample.subquery(1).c, sample)
            )
            session.commit()

    def _init_pos(self):
        # create pos
        pos = select([self.maindf]).order_by(func.random()).limit(1)
        with self.Session() as session:
            records = session.execute(pos).first()
            for i in range(-3,1):
                pos = self.Pos()
                for attr in self.settings.other.attributes + ["_index"]:
                    setattr(pos, attr, getattr(records[0], attr))
                if i < 0:
                    setattr(pos, "_index", i)
                session.add(pos)
            session.commit()

    def _init_neg(self):
        # create neg
        neg = select([self.maindf]).order_by(func.random()).limit(10)
        with self.Session() as session:
            records = session.execute(neg).all()
            for r in records:
                neg = self.Neg()
                for attr in self.settings.other.attributes + ["_index"]:
                    setattr(neg, attr, getattr(r[0], attr))
                session.add(neg)
            session.commit()

    def _init_train(self):
        
        logging.info(f"Building table {self.settings.other.db_schema}.train.")
        self._init_pos()
        self._init_neg()
        
        # create train
        with self.Session() as session:
            for tab in [self.Pos, self.Neg]:
                records = session.query(tab).all()
                for r in records:
                    train = self.Train()
                    for attr in self.settings.other.attributes + ["_index"]:
                        setattr(train, attr, getattr(r, attr))
                    session.add(train)
            session.commit()

    def _init_labels(self):
        logging.info(f"Building table {self.settings.other.db_schema}.labels.")
        with self.Session() as session:
            for l,tab in [(1,self.Pos), (0,self.Neg)]:
                records = session.query(tab).all()
                pairs = list(itertools.combinations(records, 2))
                for left,right in pairs:
                    label = self.Labels()
                    if left._index < right._index:
                        label._index_l = left._index
                        label._index_r = right._index
                        label.label = l
                        session.add(label)
            session.commit()
        self._label_distances()

    def _label_distances(self):
        """
        computes distances between pairs of records from labels table 
        then appends distances to the labels table
        """
        self.distance = RayAllJaro(settings=self.settings)
        self.distance.save_distances(
            table=self.Labels,
            newtable=self.Labels
        )

    def setup(self, df=None, reset=True, resample=False):
        """
        runs table creation functions

        Parameters
        ----------
        df: Optional[pd.DataFrame]
            dataframe to dedupe
        reset: bool
            set True to delete and create all tables
        resample: bool
            used for active learning loops where model needs to pull a new 
            sample, without deleting df, train, or labels
        """
        
        # initialize Tables sqlalchemy classes
        self.setup_dynamic_declarative_mapping()

        if reset:
            self.reset_tables()

            logging.info(f"building tables in schema: {self.settings.other.db_schema}")
            if "_index" in df.columns:
                raise ValueError("_index cannot be a column name")
            self._init_df(df=df)

            self._init_sample()
            self._init_train()
            self._init_labels()

        if resample:
            self.engine.execute(f"""
                TRUNCATE TABLE {self.settings.other.db_schema}.sample;
            """)
            self._init_sample()
            self._label_distances()
    