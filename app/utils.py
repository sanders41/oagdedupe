import json
from collections import Counter
from functools import cached_property
from io import BytesIO
import base64
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd


class Labels:
    """
    Object used to handle labelled samples
    """

    def __init__(self, cache_path):
        self.cache_path = cache_path

    @cached_property
    def labels(self):
        with open(f"{self.cache_path}/samples.json", "r") as f:
            return json.load(f)

    @property
    def meta(self):
        counter = Counter()
        for x in [x["label"] for x in self.labels.values()]:
            counter[x] += 1
        for x in [x["type"] for x in self.labels.values()]:
            counter[x] += 1
        return counter

    @property
    def labelled(self):
        return [int(x["idxmat_idx"]) for x in self.labels.values()]

    @property
    def _type(self):
        if self.meta["high"] <= 5:
            return "high"
        elif self.meta["low"] <= 5:
            return "low"
        if self.meta["Yes"] - self.meta["No"] > 10:
            return "low"
        elif self.meta["No"] - self.meta["Yes"] > 10:
            return "high"
        else:
            return "uncertain"
        

    def save(self):
        with open(f"{self.cache_path}/samples.json", "w") as f:
            json.dump(self.labels, f)
        with open(f"{self.cache_path}/meta.json", "w") as f:
            json.dump(self.meta, f)
        del self.labels


def get_plots(X, scores, attributes):

    img = BytesIO()
    sns.set(rc={'figure.figsize': (7, 5)})
    fig, ax = plt.subplots()
    p = sns.scatterplot(x=X[:, 0], y=X[:, 1], hue=scores, ax=ax)
    p.set_xlabel(f"{attributes[0]} distance")
    p.set_ylabel(f"{attributes[1]} distance")
    plt.savefig(img, format='png')
    plt.close()

    img2 = BytesIO()
    sns.set(rc={'figure.figsize': (7, 5)})
    fig, ax = plt.subplots()
    p = sns.kdeplot(scores, ax=ax)
    p.set_xlabel("scores")
    ax2 = ax.twinx()
    sns.histplot(scores, ax=ax2)
    plt.savefig(img2, format='png')
    plt.close()

    img.seek(0)
    scatterplt = base64.b64encode(img.getvalue()).decode('utf8')

    img2.seek(0)
    kdeplot = base64.b64encode(img2.getvalue()).decode('utf8')

    return scatterplt, kdeplot


def html_input(c):
    return '<input name="{}" value="{{}}" />'.format(c)


def labels_to_df(labels):
    """
    df of labels to print on page
    """
    if len(labels) > 0:
        return pd.DataFrame(labels).T[[
            "idl", "idr", "label", "revise"
        ]]
    else:
        return pd.DataFrame(labels).T