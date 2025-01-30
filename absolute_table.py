import logging
import param
import pandas as pd
import panel as pn

from aggregate_table import AggregateTable

logger = logging.getLogger("visualizer.absolute_table")

class AbsoluteTable(AggregateTable):
    algorithms = param.ListSelector(label="Algorithms", default=[])

    def __init__(self, **params):
        super().__init__(**params)
        self.param_view.insert(0, pn.widgets.CrossSelector.from_param(
            self.param.algorithms,
            name="",
            definition_order=False,
            options = self.experiment_data.param.algorithms,
            margin=(5, 0, 5, 0),
            width=400
            # TODO: can we have a min_width with stretching? (Could not get it to work so far)
        ))


    def style_table_by_row(self, row):
        style = super().style_table_by_row(row)
        attribute = row.name[0]

        numeric_attribute = self.experiment_data.numeric_attributes.get(row.name[0], None)
        if numeric_attribute is None:  # the attribute is not a numeric attribute
            return style

        numeric_values = pd.to_numeric(row,errors='coerce')
        min_val = numeric_values.dropna().min()
        max_val = numeric_values.dropna().max()
        if min_val == max_val:
            return style
        for i, val in enumerate(numeric_values):
            if not pd.isnull(val):
                percentage = (val - min_val) / (max_val-min_val)
                if numeric_attribute.min_wins:
                  percentage = 1-percentage
                green = (percentage*175).astype(int)
                blue = ((1-percentage)*255).astype(int)
                style[i] = style[i]+ "color: #00{:02x}{:02x};".format(green, blue)
        return style


    @param.depends("experiment_data.algorithms", watch=True)
    def select_all_algorithms(self):
        self.param.algorithms.default = list(self.experiment_data.algorithms.values())
        self.algorithms = self.param.algorithms.default


    @param.depends("algorithms", watch=True)
    def set_columns(self):
        self.columns = ["Index"] + [alg.get_name() for alg in self.algorithms]


    def get_algorithms(self):
        return self.algorithms


    def get_watchers_for_param_config(self):
        return [
            "algorithms",
            "attributes",
            "domains",
            "precision"
        ]


    def get_param_config_dict(self):
        d = {}
        return d


    def set_params_from_param_config_dict(self, param_config_dict):
        update = {}
        self.param.update(update)
