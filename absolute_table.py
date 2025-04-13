import logging
import pandas as pd
import panel as pn

from aggregate_table import AggregateTable

logger = logging.getLogger("visualizer.absolute_table")

class AbsoluteTable(AggregateTable):

    def __init__(self, **params):
        super().__init__(**params)

        self.report_information = """
                <p>A full table on all attributes, comparing the different 
                algorithms against each other and aggregating over domains /
                all problems.</p>
                
                <p>Data is organized by attribute, then domain, then problem.
                You can click on attributes/domains to unfold the next level,
                and reclick to fold again. Clicking on a concrete problem opens
                a ProblemReport comparing all attributes for this specific
                problem. Several popups can be open at the same time.</p>

                <p>Numeric values are aggregated over the set of instances where
                all selected algorithms have a value for the corresponding
                attribute. They are also color-coded, with blue denoting a worse
                and green a better value.</p>"""

        self.param_view.insert(0, pn.pane.HTML("<label>Algorithms</label>", margin=(5, 0, -5, 0)))
        self.param_view.insert(1, pn.widgets.CrossSelector.from_param(
            self.param.algorithms,
            name="",
            definition_order=False,
            options = self.experiment_data.param.algorithms,
            margin=(5, 0, 5, 0),
            width=400
            # TODO: can we have a min_width with stretching? (Could not get it to work so far)
        ))
        self.data_view.style.apply(func=self.style_table_by_row, axis=1)


    def style_table_by_row(self, row):
        style = super().style_table_by_row(row)
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


    def get_algorithms_on_new_experiment_data(self):
        logger.debug("getting algorithms on new experiment data")
        return self.param.algorithms.default


    def update_data_view_table(self, patch_df):
        logger.debug("updating data view table")
        self.data_view.patch(patch_df)


    def algorithms_updated(self, event):
        self.data_view.value.drop(self.data_view.value.columns[1:], axis=1, inplace=True)
        self.data_view.value[[x.get_name() for x in self.algorithms]] = self.experiment_data.data[[x.name for x in self.algorithms]]
        self.data_view.param.trigger("value")
        super().algorithms_updated(event)


    def get_watchers_for_param_config(self):
        return super().get_watchers_for_param_config() + [
            "algorithms",
        ]


    def get_param_config_dict(self):
        d = super().get_param_config_dict()
        if self.algorithms != self.param.algorithms.default:
            d["algs"] = [alg.id for alg in self.algorithms]
        return d


    def set_params_from_param_config_dict(self, d):
        super().set_params_from_param_config_dict(d)
        update = {}
        if "algs" in d:
            update["algorithms"] = [self.experiment_data.get_algorithm_by_id(id) for id in d["algs"]]
        self.param.update(update)
