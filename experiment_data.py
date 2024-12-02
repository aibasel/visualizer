from io import BytesIO # for reading in bytestrings for file upload
import pandas as pd
import panel as pn
from panel.viewable import Viewer
import param

from custom_logging import logging

logger = logging.getLogger("visualizer.experiment_data")


class NumericAttribute(Viewer):
    min_wins = param.Boolean(default=False, doc="Whether a lower value is better or not")
    aggregator = param.Selector(objects=['sum', 'mean', 'gmean'], default='sum', doc="The operation used when aggregating data")


    def __init__(self, exp_data, **params):
        super().__init__(**params)
        self.exp_data = exp_data
        self.default_aggregator = self.aggregator
        self.default_min_wins = self.min_wins


    def name_view(self):
        return pn.pane.HTML(self.param.name, styles={"overflow-wrap": "break-word"}, sizing_mode="stretch_width")
    def aggregator_view(self):
        return pn.widgets.Select.from_param(self.param.aggregator, name="", width=75)
    def min_wins_view(self):
        return pn.widgets.Switch.from_param(self.param.min_wins, width=35)


    @param.depends("min_wins", watch=True)
    def update_min_wins(self):
        logger.debug(f"Updating min wins for NumericAttribute {self.name}")
        if self.min_wins == self.default_min_wins:
            self.exp_data.custom_min_wins.pop(self.name, None)
        else:
            self.exp_data.custom_min_wins[self.name] = self.min_wins
        self.exp_data.param.trigger("custom_min_wins")


    @param.depends("aggregator", watch=True)
    def update_aggregator(self):
        logger.debug(f"Updating aggregator for NumericAttribute {self.name}")
        if self.aggregator == self.default_aggregator:
            self.exp_data.custom_aggregators.pop(self.name, None)
        else:
            self.exp_data.custom_aggregators[self.name] = self.aggregator
        self.exp_data.param.trigger("custom_aggregators")



class ExperimentData(param.Parameterized):

    properties_url = param.String()
    properties_file = param.FileSelector()
    properties_mode = param.Selector(objects=["file", "url"], default="url",
        doc="whether the properties file should be uploaded as file or specified as url")

    custom_min_wins = param.Dict()
    custom_aggregators = param.Dict()

    data = param.DataFrame(precedence=-1)

    def __init__(self, **params):
        super().__init__(**params)

        self.attributes = []
        self.numeric_attributes = {}
        self.algorithms = []
        self.domains = []
        self.problems = {}
        self.num_problems = 0

        self.numeric_attr_views = pn.GridBox(
            pn.pane.HTML("<b>Attribute</b>"),
            pn.pane.HTML("<b>Aggregator</b>"),
            pn.pane.HTML("<b>Min wins</b>"),
            name="Attributes", ncols=3)
        self.algorithm_aliases_views = pn.GridBox(name="Algorithms", ncols=3)

        self.param_view = pn.Column(
            pn.Row(
                pn.pane.HTML(
                    "<label>Properties</label>",
                    margin=(10, 0, 0, 20)
                ),
                pn.widgets.TooltipIcon(
                    margin=(10, 0, 0, 0), value=
                    "Expects a json file or an archive containing a json "
                    "file. It can either be uploaded or linked by url. "
                    "If url is used, you can share your current report "
                    "view by copying the link in the address bar."
                )
            ),
            pn.Param(self.param.properties_mode,
                widgets={'properties_mode': {
                    'widget_type': pn.widgets.RadioBoxGroup,
                    'inline': True}},
                margin=(0, 0, -8, 10),
            ),
            pn.Param(self.param.properties_url, margin=(0, 10),
                visible = (self.param.properties_mode.rx() == "url"),
                sizing_mode="stretch_width"
            ),
            pn.Param(self.param.properties_file,
                widgets={'properties_file': pn.widgets.FileInput},
                margin=(0, 10),
                visible=(self.param.properties_mode.rx() == "file"),
                sizing_mode="stretch_width"
            ),
            pn.Accordion(pn.rx(self.numeric_attr_views), margin=(0,15,15,15)),
            sizing_mode="stretch_width"
        )


    @param.depends("properties_mode", watch=True)
    def switch_properties_mode(self):
        logger.debug("start method switch properties mode")
        if self.properties_mode == "url":
            self.properties_file = None
        else:
            self.properties_url = ""


    @param.depends("properties_url", "properties_file", watch=True)
    def set_data(self):
        logger.debug("start method set data")
        properties = None
        if self.properties_mode == "url" and self.properties_url != "":
            properties = self.properties_url
        elif self.properties_file is not None:
            properties = BytesIO(self.properties_file)

        prop_from = "file" if self.properties_mode == "file" else properties
        if properties is not None:
            logger.info("reading in properties from " + prop_from)
        try:
            new_data = pd.read_json(properties, orient="index")
            self.attributes = [x for x in new_data.columns if x not in ["algorithm", "domain", "problem"]]
            self.numeric_attributes = {x: NumericAttribute(name=x, exp_data=self)
                for x in self.attributes if pd.api.types.is_numeric_dtype(new_data.dtypes[x])}
            self.numeric_attr_views.objects = self.numeric_attr_views.objects[0:3] + [
                v for x in self.numeric_attributes.values() for v in [x.name_view, x.aggregator_view, x.min_wins_view]]
            self.algorithms = list(new_data.algorithm.unique())
            self.domains = list(new_data.domain.unique())

            # pivot such that the columns are a combination of algorithm-attribute, and then stack such that the attribute becomes part of the index
            new_data = new_data.pivot(index=["domain","problem"], columns="algorithm", values=self.attributes).stack(0, dropna = False)
            # pivot does not set a name for the newly created index column
            new_data.index.names = ["domain","problem","attribute"]
            # reorder and sort such that attribute is the first index column
            new_data = new_data.reorder_levels(["attribute","domain","problem"])
            new_data = new_data.sort_index()
            # build a dicitonary that stores for every domain a list of problem names
            self.problems = dict()
            self.num_problems = 0
            for domain in self.domains:
                self.problems[domain] = [x for x in new_data.loc[(self.attributes[0],domain)].index.get_level_values('problem')]
                self.num_problems  += len(self.problems[domain])

            self.param.update({
                "data": new_data,
                "custom_min_wins": {},
                "custom_aggregators": {},
            })
            logger.info("done reading in properties")

        except Exception as e:
            self.attributes = []
            self.numeric_attributes = {}
            self.algorithms = []
            self.domains = []
            self.problems = {}
            self.num_problems = 0
            self.numeric_attr_views.objects = self.numeric_attr_views.objects[0:3]

            self.param.update({
                "data": pd.DataFrame(),
                "custom_min_wins": {},
                "custom_aggregators": {}
            })
            if properties is not None:
                logger.warning("Could not read properties")


    # returns a dict containing all information needed for recreating the current view
    def get_param_config_dict(self):
        relevant_params = [
            "properties_url",
            "custom_min_wins",
            "custom_aggregators"
        ]
        return { key: self.param.values()[key] for key in relevant_params }


    # sets parameters based on the param_config_dict
    def set_params_from_param_config_dict(self, param_config_dict):
        self.properties_url = param_config_dict.pop("properties_url")
        self.param.update(param_config_dict)
        for attribute, value in self.custom_min_wins.items():
            self.numeric_attributes[attribute].min_wins = value
        for attribute, value in self.custom_aggregators.items():
            self.numeric_attributes[attribute].aggregator = value
