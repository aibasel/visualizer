from collections.abc import Iterable
from io import BytesIO # for reading in bytestrings for file upload
import logging
import pandas as pd
import panel as pn
from panel.viewable import Viewer
import param

from user_logger import UserLogger

logger = logging.getLogger("visualizer.experiment_data")
pd.set_option('future.no_silent_downcasting', True)

PREDEFINED_ATTRIBUTES = {
  "cost" : (True, "sum"),
  "coverage" : (False, "sum"),
  "dead_ends" : (False, "sum"),
  "evaluated" : (True, "gmean"),
  "evaluations" : (True, "gmean"),
  "evaluations_until_last_jump" : (True, "gmean"),
  "expansions" : (True, "gmean"),
  "expansions_until_last_jump" : (True, "gmean"),
  "generated" : (True, "gmean"),
  "generated_until_last_jump" : (True, "gmean"),
  "initial_h_value" : (False, "sum"),
  "ipc-sat-score" : (False, "sum"),
  "ipc-sat-score-no-planning-domains" : (False, "sum"),
  "memory" : (True, "sum"),
  "plan_length" : (True, "sum"),
  "planner_memory" : (True, "sum"),
  "planner_time" : (True, "gmean"),
  "planner_wall_clock_time" : (True, "gmean"),
  "raw_memory" : (True, "sum"),
  "score_evaluations" : (False, "sum"),
  "score_expansions" : (False, "sum"),
  "score_generated" : (False, "sum"),
  "score_memory" : (False, "sum"),
  "score_planner_memory" : (False, "sum"),
  "score_planner_time" : (False, "sum"),
  "score_search_time" : (False, "sum"),
  "score_total_time" : (False, "sum"),
  "search_time" : (True, "gmean"),
  "total_time" : (True, "gmean"),
  "translator_time_done" : (True, "gmean")
}


class NumericAttribute(Viewer):
    min_wins = param.Boolean(default=False, doc="Whether a lower value is better or not")
    aggregator = param.Selector(objects=['sum', 'mean', 'gmean'], default='sum', doc="The operation used when aggregating data")

    def __init__(self, exp_data, id, **params):
        super().__init__(**params)
        self.exp_data = exp_data
        self.id = id
        self.default_aggregator = self.aggregator
        self.default_min_wins = self.min_wins


    def name_view(self):
        return pn.pane.HTML(
            self.param.name,
            styles={"overflow-wrap": "break-word"},
            sizing_mode="stretch_width"
        )
    def aggregator_view(self):
        return pn.widgets.Select.from_param(
            self.param.aggregator,
            name="",
            width=75
        )
    def min_wins_view(self):
        return pn.widgets.Switch.from_param(
            self.param.min_wins,
            name="",
            width=35
        )


    @param.depends("min_wins", watch=True)
    def update_min_wins(self):
        logger.debug(f"Updating min wins for NumericAttribute {self.name}")
        if self.min_wins == self.default_min_wins:
            self.exp_data.custom_min_wins.pop(self.id, None)
        else:
            self.exp_data.custom_min_wins[self.id] = self.min_wins
        self.exp_data.param.trigger("custom_min_wins")


    @param.depends("aggregator", watch=True)
    def update_aggregator(self):
        logger.debug(f"Updating aggregator for NumericAttribute {self.name}")
        if self.aggregator == self.default_aggregator:
            self.exp_data.custom_aggregators.pop(self.id, None)
        else:
            self.exp_data.custom_aggregators[self.id] = self.aggregator
        self.exp_data.param.trigger("custom_aggregators")



class Algorithm(Viewer):
    alias = param.String(default="")

    def __init__(self, exp_data, id, **params):
        super().__init__(**params)
        self.exp_data = exp_data
        self.id = id


    def name_view(self):
        return pn.pane.HTML(
            self.param.name,
            styles={"overflow-wrap": "break-word"},
            sizing_mode="stretch_width"
        )
    def alias_view(self):
        return pn.widgets.TextInput.from_param(
            self.param.alias,
            name="",
            margin=(5,5,5,10),
            min_width=100,
            sizing_mode="stretch_width"
        )

    def get_name(self):
        if self.alias == "":
            return self.name
        else:
            return self.alias


    @param.depends("alias", watch=True)
    def update_alias(self):
        logger.debug(f"Updating alias for algorithm {self.name} to {self.alias}")
        if self.alias == "":
            self.exp_data.custom_algorithm_aliases.pop(self.id, None)
        else:
            in_use = False
            for alg in self.exp_data.algorithms.values():
                if alg != self and alg.get_name() == self.alias:
                    in_use = True
                    self.exp_data.user_logger.log(logging.WARNING, f"Ignoring alias for {self.name}: alias {self.alias} already in use for algorithm {alg}")
                    self.alias = ""
                    break
            if not in_use:
                self.exp_data.custom_algorithm_aliases[self.id] = self.alias
        self.exp_data.algorithms = {x.get_name() : x for x in self.exp_data.algorithms.values()}
        self.exp_data.param.trigger("custom_algorithm_aliases")



class ExperimentData(param.Parameterized):

    # widget parameters
    properties_mode = param.Selector(objects=["file", "url"], default="url",
        doc="whether the properties file should be uploaded as file or specified as url")
    properties_url = param.String(default="", doc="A url pointing to a properties json file.")
    properties_file = param.FileSelector()

    # internal parameters
    data = param.DataFrame(precedence=-1, default=pd.DataFrame())
    attributes = param.List(default=[], precedence=-1)
    sorted_num_attr_names = param.List(default=[], precedence=-1)
    numeric_attributes = param.Dict(default={}, precedence=-1) # values are NumericAttribute objects
    sorted_alg_names = param.List(default=[], precedence=-1)
    algorithms = param.Dict(default = {}, precedence=-1) # values are Algorithm objects
    domains = param.List(default=[], precedence=-1)
    num_problems = param.Integer(default=0)
    problems_by_domain = param.Dict(default={}, precedence=-1)

    # config string parameters
    custom_min_wins = param.Dict(default={}, precedence=-1)
    custom_aggregators = param.Dict(default={}, precedence=-1)
    custom_algorithm_aliases = param.Dict(default={}, precedence=-1)

    def __init__(self, **params):
        self.user_logger = params.pop("user_logger", UserLogger())
        super().__init__(**params)

        self.numeric_attr_views = pn.GridBox(
            pn.pane.HTML("<b>Attribute</b>"),
            pn.Row(
                pn.pane.HTML("<b>Aggregator</b>", margin=(5,-10,5,0)),
                pn.widgets.TooltipIcon(
                    value="Which aggregator to use in table aggregate rows (domains/attribute). gmean is the geometric mean."
                )
            ),
            pn.Row(
                pn.pane.HTML("<b>Min wins</b>", margin=(5,-10,5,0)),
                pn.widgets.TooltipIcon(
                    value="Whether a smaller value is better. Used for color highlights in tables."
                )
            ),
            name="Attributes", ncols=3, sizing_mode="stretch_width")

        self.algorithm_views = pn.GridBox(
            pn.pane.HTML("<b>Algorithm</b>"),
            pn.pane.HTML("<b>Alias</b>"),
            name="Algorithms", ncols=2, sizing_mode="stretch_width")

        self.param_view = pn.Column(
            pn.Row(
                pn.pane.HTML(
                    "<label>Properties</label>",
                    margin=(10, 0, 0, 0)
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
                margin=(0, 0, -8, -10),
            ),
            pn.widgets.TextInput.from_param(
                self.param.properties_url,
                visible = (self.param.properties_mode.rx() == "url"),
                name="",
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width"
            ),
            pn.widgets.FileInput.from_param(
                self.param.properties_file,
                visible=(self.param.properties_mode.rx() == "file"),
                name="",
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width"
            ),
            pn.Accordion(pn.rx(self.numeric_attr_views), margin=(10,0,5,-5), sizing_mode="stretch_width"),
            pn.Accordion(pn.rx(self.algorithm_views), margin=(0,0,5,-5), sizing_mode="stretch_width"),
            sizing_mode="stretch_width"
        )

    # TODO: check if we should copy the data
    def get_data(self, attributes, algorithms):
        logger.debug("start get_data")
        attr_names = []
        if not isinstance(attributes, Iterable):
            attributes = [attributes]
        for attribute in attributes:
            name = attribute.name if type(attribute) is NumericAttribute else attribute
            if name not in self.attributes:
                self.user_logger.log(
                    logging.WARNING,
                    f"Encountered unknown attribute {name} when retrieving experiment data.")
            else:
                attr_names.append(name)

        alg_names = []
        if not isinstance(algorithms, Iterable):
            algorithms = [algorithms]
        for algorithm in algorithms:
            if not isinstance(algorithm, Algorithm):
                self.user_logger.log(
                    logging.WARNING,
                    f"Encountered unknown algorithm variable {algorithm} when retrieving experiment data.")
            else:
                alg_names.append(algorithm.name)
        rename_dict = { self.get_algorithm_by_id(id).name: alias for id, alias in self.custom_algorithm_aliases.items() }
        ret = self.data.loc[attr_names][alg_names].rename(columns=rename_dict)
        logger.debug("end get data")
        return ret


    def get_numeric_attribute_by_position(self, id):
        return self.numeric_attributes[self.sorted_num_attr_names[int(id)]]

    def get_numeric_attribute_position(self, name):
        return self.sorted_num_attr_names.index(name)

    def get_algorithm_by_id(self, id):
        id = int(id)
        name = self.custom_algorithm_aliases.get(id,self.sorted_alg_names[id])
        return self.algorithms[name]

    # NOTE: These methods assume that attributes and domains are sorted!
    def get_attribute_by_position(self, id):
        return self.attributes[id]

    def get_attribute_position(self, name):
        return self.attributes.index(name)

    def get_domain_by_id(self, id):
        return self.domains[id]

    def get_domain_id(self, domain):
        return self.domains.index(domain)

    def get_rename_dict(self):
        return {
            alg.name : alg.get_name() for alg in self.algorithms.values()
        }


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
            self.user_logger.log(logging.INFO, "start reading in properties from " + ("file" if self.properties_mode == "file" else "url " + properties))

        try:
            data = pd.read_json(properties, orient="index")
            attributes = sorted([x for x in data.columns if x not in ["algorithm", "domain", "problem"]])
            sorted_num_attr_names = [x for x in attributes if pd.api.types.is_numeric_dtype(data.dtypes[x])]
            sorted_alg_names= sorted([x for x in data.algorithm.unique()])
            algorithms = {x: Algorithm(name=x, exp_data=self, id=i)
                for i,x in enumerate(sorted_alg_names)}
            domains = sorted(list(data.domain.unique()))
            num_problems = 0 #actual value is set after pivoting data

            # pivot such that the columns are a combination of algorithm-attribute, and then stack such that the attribute becomes part of the index
            data =data.pivot(index=["domain","problem"], columns="algorithm", values=attributes).stack(0, future_stack=True)
            # pivot does not set a name for the newly created index columnc
            data.index.names = ["domain","problem","attribute"]
            # reorder and sort such that attribute is the first index column
            data = data.reorder_levels(["attribute","domain","problem"]).sort_index()

            problems_by_domain = dict()
            for domain in domains:
                problems_by_domain[domain] = [x for x in data.loc[(attributes[0],domain)].index.get_level_values('problem')]
                num_problems  += len(problems_by_domain[domain])

#            success, new_data = self.compute_ipc_score(data)
#            if success:
#                new_attributes = ["ipc-sat-score", "ipc-sat-score-no-planning-domains"]
#                attributes = sorted(attributes + new_attributes)
#                sorted_num_attr_names = sorted(sorted_num_attr_names + new_attributes)
#                data = new_data.sort_values("attribute")
            # numeric attributes should only be set up once ipc scores have been computed
            numeric_attributes = dict()
            for i,x in enumerate(sorted_num_attr_names):
                min_wins, agg = PREDEFINED_ATTRIBUTES.get(x, (False, "sum"))
                numeric_attributes[x] = NumericAttribute(name=x, exp_data=self, id=i, min_wins=min_wins, aggregator=agg)

            self.param.update({
                "data": data,
                "attributes" : attributes,
                "sorted_num_attr_names" : sorted_num_attr_names,
                "numeric_attributes" : numeric_attributes,
                "sorted_alg_names" : sorted_alg_names,
                "algorithms" : algorithms,
                "domains" : domains,
                "num_problems" : num_problems,
                "problems_by_domain" : problems_by_domain,
                "custom_min_wins": {},
                "custom_aggregators": {},
                "custom_algorithm_aliases": {},
            })

            self.numeric_attr_views.objects = self.numeric_attr_views.objects[0:3] + [
                v for x in self.numeric_attributes.values() for v in [x.name_view, x.aggregator_view, x.min_wins_view]]
            self.algorithm_views.objects = self.algorithm_views.objects[0:2] + [
                v for x in self.algorithms.values() for v in [x.name_view, x.alias_view]]

            self.user_logger.log(logging.INFO, "finished reading in properties")

        except ValueError as e:
            self.numeric_attr_views.objects = self.numeric_attr_views.objects[0:3]
            self.algorithm_views.objects = self.algorithm_views.objects[0:2]

            self.param.update({
                "data": pd.DataFrame(),
                "attributes" : [],
                "sorted_num_attr_names" : [],
                "numeric_attributes" : {},
                "sorted_alg_names" : [],
                "algorithms" : {},
                "domains" : [],
                "num_problems" : 0,
                "problems_by_domain" : {},
                "custom_min_wins": {},
                "custom_aggregators": {},
                "custom_algorithm_aliases": {}
            })
            if properties is not None:
                self.user_logger.log(logging.ERROR, "Could not read properties")




    def compute_ipc_score(self, data):
        if "cost" not in data.index.get_level_values(0):
            return False, pd.DataFrame()
        upper_bounds = pd.read_json("upper_bounds.json", orient="index")
        upper_bounds = upper_bounds.set_index(["domain","problem"])
        costs = data.loc["cost"]

        new_data = data
        for with_upper in [True, False]:
            tmp_data = costs.copy()
            if with_upper:
                tmp_data["upper_bounds"] = upper_bounds
            min_costs = tmp_data.min(axis=1)

            score_data = (1/costs).fillna(0).multiply(min_costs, axis=0)
            score_data["attribute"] = "ipc-sat-score" if with_upper else "ipc-sat-score-no-planning-domains"
            score_data.set_index(["attribute", score_data.index], inplace=True)
            new_data = pd.concat([new_data, score_data])
        return True, new_data


    def get_watchers_for_param_config(self):
        return [
            "properties_mode",
            "properties_url",
            "properties_file",
            "custom_min_wins",
            "custom_aggregators",
            "custom_algorithm_aliases"
        ]

    # returns a dict containing all information needed for recreating the current view
    def get_param_config_dict(self):
        d = {}
        if self.properties_url != self.param["properties_url"].default:
            d["url"] = self.properties_url
        if self.custom_min_wins != self.param["custom_min_wins"].default:
            d["minw"] = self.custom_min_wins
        if self.custom_aggregators != self.param["custom_aggregators"].default:
            d["aggs"] = self.custom_aggregators
        if self.custom_algorithm_aliases != self.param["custom_algorithm_aliases"].default:
            d["alis"] = self.custom_algorithm_aliases
        return d


    # sets parameters based on the param_config_dict
    def set_params_from_param_config_dict(self, d):
        self.properties_mode = "url"
        if "url" in d:
            self.properties_url = d["url"]
        if "minw" in d:
            for id, value in d["minw"].items():
                self.get_numeric_attribute_by_position(id).min_wins = value
        if "aggs" in d:
            for id, value in d["aggs"].items():
                self.get_numeric_attribute_by_position(id).aggregator = value
        if "alis" in d:
            for id, alias in d["alis"].items():
                self.get_algorithm_by_id(id).alias = alias
