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



class Algorithm(Viewer):
    alias = param.String(default="")

    def __init__(self, exp_data, **params):
        super().__init__(**params)
        self.exp_data = exp_data


    def name_view(self):
        return pn.pane.HTML(self.param.name, styles={"overflow-wrap": "break-word"}, sizing_mode="stretch_width")
    def alias_view(self):
        return pn.widgets.TextInput.from_param(self.param.alias, name="")

    def get_name(self):
        if self.alias == "":
            return self.name
        else:
            return self.alias


    @param.depends("alias", watch=True)
    def update_alias(self):
        logger.debug(f"Updating alias for algorithm {self.name} to {self.alias}")
        if self.alias == "":
            self.exp_data.custom_algorithm_aliases.pop(self.name, None)
        else:
            in_use = False
            for alg, alias in self.exp_data.custom_algorithm_aliases.items():
                if alias == self.alias and alg != self.name:
                    in_use = True
                    logger.warning(f"Ignoring alias for {self.name}: alias {self.alias} already in use for algorithm {alg}")
            if not in_use:
                self.exp_data.custom_algorithm_aliases[self.name] = self.alias
        self.exp_data.algorithms = {x.get_name() : x for x in self.exp_data.algorithms.values()}
        self.exp_data.param.trigger("custom_algorithm_aliases")


# TODO: we need to somehow invalidate or update data when algorithm aliases change
class ExperimentData(param.Parameterized):

    # widget parameters
    properties_url = param.String()
    properties_file = param.FileSelector()
    properties_mode = param.Selector(objects=["file", "url"], default="url",
        doc="whether the properties file should be uploaded as file or specified as url")

    # internal parameters
    data = param.DataFrame(precedence=-1)
    attributes = param.List(default=[], precedence=-1)
    numeric_attributes = param.Dict(default={}, precedence=-1) # values are NumericAttribute objects
    algorithms = param.Dict(default = {}, precedence=-1)
    domains = param.List(default=[], precedence=-1)
    num_problems = param.Integer(default=0)
    num_problems_by_domain = param.Dict(default={}, precedence=-1)

    # config string parameters
    custom_min_wins = param.Dict(precedence=-1)
    custom_aggregators = param.Dict(precedence=-1)
    custom_algorithm_aliases = param.Dict(precedence=-1)

    def __init__(self, **params):
        super().__init__(**params)

        self.numeric_attr_views = pn.GridBox(
            pn.pane.HTML("<b>Attribute</b>"),
            pn.pane.HTML("<b>Aggregator</b>"),
            pn.pane.HTML("<b>Min wins</b>"),
            name="Attributes", ncols=3)

        self.algorithm_views = pn.GridBox(
            pn.pane.HTML("<b>Algorithm</b>"),
            pn.pane.HTML("<b>Alias</b>"),
            name="Algorithms", ncols=2)

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
            pn.Accordion(pn.rx(self.numeric_attr_views), margin=(0,15,0,15)),
            pn.Accordion(pn.rx(self.algorithm_views), margin=(0,15,15,15)),
            sizing_mode="stretch_width"
        )

    # TODO: check if we should copy the data
    def get_data(self, attributes, algorithms):
        logger.debug("start get_data")
        attr_names = []
        if type(attributes) is NumericAttribute:
            attr_names = attributes.name
        elif attributes is list:
            attr_names = [x.name for x in attributes if type(x) is NumericAttribute]
        alg_names = []
        if type(algorithms) is Algorithm:
            alg_names = algorithms.name
        elif algorithms is list:
            alg_names = [x.name for x in algorithms if type(x) is Algorithm]
        logger.debug("end get data")
        return self.data.loc[attr_names][alg_names].rename(self.custom_algorithm_aliases)


    @param.depends("properties_mode", watch=True)
    def switch_properties_mode(self):
        logger.debug("start switch properties mode")
        if self.properties_mode == "url":
            self.properties_file = None
        else:
            self.properties_url = ""
        logger.debug("end switch properties mode")


    @param.depends("properties_url", "properties_file", watch=True)
    def set_data(self):
        logger.debug("start set data")
        properties = None
        if self.properties_mode == "url" and self.properties_url != "":
            properties = self.properties_url
        elif self.properties_file is not None:
            properties = BytesIO(self.properties_file)
        if properties is not None:
            logger.info("start reading in properties from " + ("file" if self.properties_mode == "file" else "url " + properties))

        try:
            data = pd.read_json(properties, orient="index")
            attributes = [x for x in data.columns if x not in ["algorithm", "domain", "problem"]]
            numeric_attributes = {x: NumericAttribute(name=x, exp_data=self)
                for x in attributes if pd.api.types.is_numeric_dtype(data.dtypes[x])}
            algorithms = {x: Algorithm(name=x, exp_data=self)
                for x in data.algorithm.unique()}
            domains = list(data.domain.unique())
            num_problems = 0 #actual value is set after pivoting data
            num_problems_by_domain = dict() #actual value is set after pivoting data

            # pivot such that the columns are a combination of algorithm-attribute, and then stack such that the attribute becomes part of the index
            data =data.pivot(index=["domain","problem"], columns="algorithm", values=attributes).stack(0, future_stack=True)
            # pivot does not set a name for the newly created index columnc
            data.index.names = ["domain","problem","attribute"]
            # reorder and sort such that attribute is the first index column
            data = data.reorder_levels(["attribute","domain","problem"]).sort_index()

            for domain in self.domains:
                num_problems_by_domain[domain] = [x for x in data.loc[(self.attributes[0],domain)].index.get_level_values('problem')]
                num_problems  += len(num_problems_by_domain[domain])

            self.param.update({
                "data": data,
                "attributes" : attributes,
                "numeric_attributes" : numeric_attributes,
                "algorithms" : algorithms,
                "domains" : domains,
                "num_problems" : num_problems,
                "num_problems_by_domain" : num_problems_by_domain,
                "custom_min_wins": {},
                "custom_aggregators": {},
                "custom_algorithm_aliases": {},
            })


            self.numeric_attr_views.objects = self.numeric_attr_views.objects[0:3] + [
                v for x in self.numeric_attributes.values() for v in [x.name_view, x.aggregator_view, x.min_wins_view]]
            self.algorithm_views.objects = self.algorithm_views.objects[0:2] + [
                v for x in self.algorithms.values() for v in [x.name_view, x.alias_view]]

            logger.info("done reading in properties")

        except Exception as e:
            self.numeric_attr_views.objects = self.numeric_attr_views.objects[0:3]
            self.algorithm_views.objects = self.algorithm_views.objects[0:2]

            self.param.update({
                "data": pd.DataFrame(),
                "attributes" : [],
                "numeric_attributes" : {},
                "algorithms" : {},
                "domains" : [],
                "num_problems" : 0,
                "num_problems_by_domain" : {},
                "custom_min_wins": {},
                "custom_aggregators": {},
                "custom_algorithm_aliases": {}
            })
            if properties is not None:
                logger.warning("Could not read properties")


    # returns a dict containing all information needed for recreating the current view
    def get_param_config_dict(self):
        relevant_params = [
            "properties_url",
            "custom_min_wins",
            "custom_aggregators",
            "custom_algorithm_aliases"
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
        for alg, alias in self.custom_algorithm_aliases.items():
            self.algorithms[alg].alias = alias

