# %%
from IPython import get_ipython
if get_ipython() is not None:
    get_ipython().run_line_magic("load_ext", "autoreload")
    get_ipython().run_line_magic("autoreload", "2")

# %%
from oagdedupe.settings import (
    Settings,
    SettingsOther,
)
from oagdedupe.api import Dedupe

import glob
import pandas as pd
pd.options.display.precision = 12
from sqlalchemy import create_engine
engine = create_engine("postgresql+psycopg2://username:password@172.22.39.26:8000/db")

# %%
settings = Settings(
    name="default",  # the name of the project, a unique identifier
    folder="./.dedupe",  # path to folder where settings and data will be saved
    other=SettingsOther(
        dedupe=True,
        n=5000,
        k=3,
        max_compare=200_000,
        n_covered=5000,
        cpus=20,  # parallelize distance computations
        attributes=["givenname", "surname", "suburb", "postcode"],  # list of entity attribute names
        path_database="postgresql+psycopg2://username:password@172.22.39.26:8000/db",  # where to save the sqlite database holding intermediate data
        db_schema="dedupe",
        path_model="./.dedupe/test_model",  # where to save the model
        label_studio={
            "port": 8089,  # label studio port
            "api_key": "33344e8a477f8adc3eb6aa1e41444bde76285d96",  # label studio port
            "description": "chansoo test project",  # label studio description of project
        },
        fast_api={"port": 8090},  # fast api port
    ),
)
settings.save()

# %%
files = glob.glob(
    "/mnt/Research.CF/References & Training/Satchel/dedupe_rl/baseline_datasets/north_carolina_voters/*"
)[:2]
df = pd.concat([pd.read_csv(f) for f in files]).reset_index(drop=True)
for attr in settings.other.attributes:
    df[attr] = df[attr].astype(str)
df = df.sample(100_000)

# %%
%%time
d = Dedupe(settings=settings)
d.initialize(df=df, reset=True)

# %%
d.fit_blocks()
res = d.predict()