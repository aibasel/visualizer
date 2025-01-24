import logging
import param
import pandas as pd
import panel as pn

from report import Report

logger = logging.getLogger("visualizer.scatter")


class ProblemTable(Report):
    domain = param.Parameter(label="Domain", default="")
    problem = param.Parameter(label="Problem", default="")
    algorithms = param.ListSelector()


    def __init__(self, experiment_data, sizing_mode = "stretch_both", **params):
        super().__init__(experiment_data, **params)

        self.data_view = pn.widgets.Tabulator(
                value=pd.DataFrame(), disabled = True, sortable=False, pagination="remote", page_size=10000, widths=250,
                frozen_columns = ["attribute"], show_index = False, sizing_mode=sizing_mode)
        self.data_view.style.apply(func=self.style_table_by_row, axis=1)

        self.param_view = pn.Column(
            pn.pane.HTML("<label>Domain</label>", margin=(5, 0, -5, 0)),
            pn.widgets.Select.from_param(
                self.param.domain,
                name="",
                options=self.experiment_data.param.domains,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width"
            ),
            pn.pane.HTML("<label>Problem</label>", margin=(5, 0, -5, 0)),
            pn.widgets.Select.from_param(
                self.param.problem,
                name="",
                options=[],
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width"
            ),
            pn.pane.HTML("<label>Algorithms</label>", margin=(5, 0, -5, 0)),
            pn.widgets.CrossSelector.from_param(
                self.param.algorithms,
                definition_order = False,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width"
            )
        )


    # TODO see if we can do this with a reactive function instead.
    @param.depends('domain', watch=True)
    def update_problems(self):
        self.param_view[3].options = [] if not self.domain or self.domain == "" else self.experiment_data.problems[self.domain]


    def style_table_by_row(self, row):
        style = [""] * len(row)
        attribute = row.iloc[0]
        min_wins = self.experiment_data.attribute_info[attribute].min_wins
        if min_wins is None:
            return style

        numeric_values = pd.to_numeric(row,errors='coerce')
        min_val = numeric_values.dropna().min()
        max_val = numeric_values.dropna().max()
        if min_val == max_val:
            return style
        for i, val in enumerate(numeric_values):
            if not pd.isnull(val):
                percentage = (val - min_val) / (max_val-min_val)
                if min_wins:
                  percentage = 1-percentage
                green = (percentage*175).astype(int)
                blue = ((1-percentage)*255).astype(int)
                style[i] = style[i]+ "color: #00{:02x}{:02x};".format(green, blue)
        return style


    def __panel__(self):
        if self.problem == "":
            self.data_view.value = pd.DataFrame()
        else:
            self.data_view.value = self.experiment_data.data[self.algorithms].xs((self.domain, self.problem), level=(1,2)).reset_index()
        return self.data_view


    def get_watchers_for_param_config(self):
        return [
            "domain",
            "problem",
            "algorithms"
        ]


    def get_param_config_dict(self):
        d = {}
        if self.domain != self.param.domain.default:
            d['dom'] = self.domain
        if self.problem != self.param.domain.default:
            d['prob'] = self.problem
        if self.algorithms != self.param.algorithms.default:
            d['alg'] = self.algorithms
        return d


    def set_params_from_param_config_dict(self, param_config_dict):
        update = {}
        if 'dom' in param_config_dict:
            update['domain'] = param_config_dict['dom']
        if 'prob' in param_config_dict:
            update['problem'] = param_config_dict['prob']
        if 'alg' in param_config_dict:
            update['algorithms'] = param_config_dict['alg']