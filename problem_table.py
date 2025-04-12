import logging
import param
import pandas as pd
import panel as pn

from report import Report

logger = logging.getLogger("visualizer.problem_table")

class ProblemTable(Report):
    domain = param.Parameter(label="Domain", default="")
    problem = param.Parameter(label="Problem", default="")
    algorithms = param.List(label="Algorithms", default=[])

    # internal parameters
    df = param.DataFrame(default=pd.DataFrame(), precedence=-1)

    def __init__(self, experiment_data, sizing_mode = "stretch_both", **params):
        super().__init__(experiment_data, **params)
        # setting experiment_data in super triggers select_all_algorithms(),
        # meaning we need to set it to the given parameter manually here
        if "algorithms" in params:
            self.algorithms = params["algorithms"]

        self.data_view = pn.widgets.Tabulator(
                value=self.param.df, disabled = True, sortable=False, pagination="remote", page_size=10000, widths=250,
                frozen_columns = ["attribute"], show_index = False, sizing_mode=sizing_mode)
        self.data_view.style.apply(func=self.style_table_by_row, axis=1)

        self.param_view.extend([
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
            pn.widgets.CrossSelector.from_param(
                self.param.algorithms,
                name="",
                definition_order=False,
                # we don't set possible options here but use "select_all_algorithms()" to update it
                # (setting options here with 'options = self.experiment_data.param.algorithms'
                # crashes when calling a FloatPanel Report)
                #     options = self.experiment_data.param.algorithms,
                margin=(5, 0, 5, 0),
                width=400 #TODO: can we have a min_width with stretching? (Could not get it to work so far)
            )
        ])


    def style_table_by_row(self, row):
        style = [""] * len(row)
        numeric_attribute = self.experiment_data.numeric_attributes.get(row.iloc[0], None)
        if numeric_attribute is None: # the attribute is not a numeric attribute
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


    # TODO see if we can do the two functions below reactive functions instead.
    @param.depends("experiment_data.algorithms", watch=True)
    def select_all_algorithms(self):
        logger.debug("experiment data algorithms changed")
        self.param.algorithms.default = list(self.experiment_data.algorithms.values())
        # TODO: can we do this nicer? The function can already trigger when
        # calling super().__init__(), which sets experiment_data, and at this
        # point param_view does not exist yet.
        if hasattr(self, 'param_view'):
            self.param_view[4].options = self.param.algorithms.default
        self.algorithms = self.param.algorithms.default


    @param.depends('domain', watch=True)
    def update_problems(self):
        logger.debug("start updating problem selection")
        self.param_view[3].options = [] if not self.domain or self.domain == "" else self.experiment_data.problems_by_domain[self.domain]
        logger.debug("end updating problem selection")


    @param.depends("domain", "problem", "algorithms", watch=True)
    def update_data(self):
        logger.debug("start updating data")
        if not self.problem or self.problem == "" or not self.algorithms:
            self.df = pd.DataFrame()
        else:
            tmp = self.experiment_data.get_data(self.experiment_data.attributes,  self.algorithms)
            self.df = tmp.xs((self.domain, self.problem), level=(1,2)).reset_index()
        logger.debug("end updating data")


    # Trigger a redraw when min_wins settings change
    @param.depends("experiment_data.custom_min_wins", watch=True)
    def redraw(self):
        self.param.trigger("df")


    def get_watchers_for_param_config(self):
        return [
            "domain",
            "problem",
            "algorithms"
        ]


    def get_param_config_dict(self):
        d = {}
        if self.domain != self.param.domain.default:
            d["dom"] = self.domain
        if self.problem != self.param.domain.default:
            d["prob"] = self.problem
        if self.algorithms != self.param.algorithms.default:
            d["alg"] = [alg.id for alg in self.algorithms]
        return d


    def set_params_from_param_config_dict(self, param_config_dict):
        update = {}
        if "dom" in param_config_dict:
            update["domain"] = param_config_dict["dom"]
        if "prob" in param_config_dict:
            update["problem"] = param_config_dict["prob"]
        if "alg" in param_config_dict:
            update["algorithms"] = [self.experiment_data.get_algorithm_by_id(id) for id in param_config_dict["alg"]]
        self.param.update(update)
