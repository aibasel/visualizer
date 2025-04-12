import logging
import numpy as np
import pandas as pd
import panel as pn
import param

from aggregate_table import AggregateTable
from algorithm_pairs_selector import AlgorithmPairsSelector

logger = logging.getLogger("visualizer.diff_table")

class DiffTable(AggregateTable):

    #widget parameters
    algorithm_pairs_selector = param.Parameter()
    relative = param.Boolean(default=False, label="Relative", doc="If true, the Diff column evaluates to y/x - 1 instead of y-x.")

    # config string parameters
    aps_config = param.List(default=[], precedence=-1)

    def __init__(self, **params):
        super().__init__(**params)
        self.algorithm_pairs_selector = AlgorithmPairsSelector(self.experiment_data)
        self.param_view.insert(0, self.algorithm_pairs_selector)
        self.param_view.append(pn.widgets.Checkbox.from_param(
                self.param.relative,
                margin=(5, 0, 5, 0),
        ))
        self.data_view.style.apply(func=self.style_table_by_row, axis=1)

    def style_table_by_row(self, row):
        style = super().style_table_by_row(row)
        numeric_attribute = self.experiment_data.numeric_attributes.get(row.name[0], None)
        if numeric_attribute is None:  # the attribute is not a numeric attribute
            return style

        numeric_values = pd.to_numeric(row,errors='coerce')
        vals_without_diff = numeric_values[[x for x in numeric_values.index if "Diff" not in x]]
        min_val = vals_without_diff.dropna().min()
        max_val = vals_without_diff.dropna().max()
        for i, val in enumerate(numeric_values):
            if pd.isnull(val):
                continue
            if "Diff" in numeric_values.index[i]:
                if val == 0:
                    continue
                if (val > 0) ^ (numeric_attribute.min_wins):
                    style[i] += f"color: green"
                else:
                    style[i] += f"color: red"
            else:
                if min_val == max_val:
                    continue
                percentage = (val - min_val) / (max_val-min_val)
                if numeric_attribute.min_wins:
                  percentage = 1-percentage
                green = (percentage*175).astype(int)
                blue = ((1-percentage)*255).astype(int)
                style[i] += "color: #00{:02x}{:02x};".format(green, blue)
        return style



    def get_algorithms_on_new_experiment_data(self):
        return []


    def update_data_view_table(self, patch_df):
        new_df = patch_df[["Index"]].copy()

        for i, (alg1, alg2) in enumerate(self.algorithm_pairs_selector.algorithm_pairs, start=1):
            new_df.loc[:,f"{i}-{alg1.get_name()}"] = patch_df[alg1.name]
            new_df[f"{i}-{alg2.get_name()}"] = patch_df[alg2.name]
            if self.relative:
                new_df[f"{i}-Diff"] = (pd.to_numeric(patch_df[alg2.name], errors='coerce') / pd.to_numeric(patch_df[alg1.name], errors='coerce')) - 1
            else:
                new_df[f"{i}-Diff"] = patch_df[alg2.name] - patch_df[alg1.name]
        self.data_view.patch(new_df)


    @param.depends("relative", watch=True)
    def relative_changed(self):
        new_df = pd.DataFrame()
        for i, (alg1, alg2) in enumerate(self.algorithm_pairs_selector.algorithm_pairs, start=1):
            alg1_col = pd.to_numeric(self.data_view.value[f"{i}-{alg1.get_name()}"], errors='coerce')
            alg2_col = pd.to_numeric(self.data_view.value[f"{i}-{alg2.get_name()}"], errors='coerce')
            if self.relative:
                self.data_view.value[f"{i}-Diff"] = (alg2_col / alg1_col) - 1
            else:
                self.data_view.value[f"{i}-Diff"] = alg2_col - alg1_col
        self.data_view.param.trigger("value")


    @param.depends("algorithm_pairs_selector.algorithm_pairs", watch=True)
    def algorithm_pairs_changed(self):
        collected_algs = set()
        self.data_view.value.drop(self.data_view.value.columns[1:], axis=1, inplace=True)
        for i, (alg1, alg2) in enumerate(self.algorithm_pairs_selector.algorithm_pairs, start=1):
            collected_algs.update([alg1,alg2])
            self.data_view.value[f"{i}-{alg1.get_name()}"] = self.experiment_data.data[alg1.name]
            self.data_view.value[f"{i}-{alg2.get_name()}"] = self.experiment_data.data[alg2.name]
            self.data_view.value[f"{i}-Diff"] = np.nan
        self.data_view.param.trigger("value")
        self.algorithms = list(collected_algs)



    # TODO: figure out if we can do this more directly
    @param.depends("algorithm_pairs_selector.algorithm_pairs", watch=True)
    def set_aps_config(self):
        self.aps_config = self.algorithm_pairs_selector.get_params()


    def get_watchers_for_param_config(self):
        return super().get_watchers_for_param_config() + [
            "aps_config",
            "relative"
        ]


    def get_param_config_dict(self):
        d = super().get_param_config_dict()
        if self.aps_config != self.param.aps_config.default:
            d["aps"] = self.aps_config
        if self.relative != self.param.relative.default:
            d["rel"] = self.relative
        return d


    def set_params_from_param_config_dict(self, d):
        super().set_params_from_param_config_dict(d)
        if "aps" in d:
            self.algorithm_pairs_selector.set_params(d["aps"])
        update = {}
        if "rel" in d:
            update["relative"] = d["rel"]
        self.param.update(update)
