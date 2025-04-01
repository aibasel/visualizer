from bokeh.models.widgets.tables import HTMLTemplateFormatter
import logging
import param
import pandas as pd
import panel as pn
from scipy import stats

from custom_tabulator import CustomTabulator
from problem_table import ProblemTable
from report import Report


logger = logging.getLogger("visualizer.aggregate_table")

# TODO: current problems
# 1) style still causes a lot of jumping around
# 2) when forcing a redraw by triggering the data_view value, the table might jump to the top (e.g. when changing min_wins)
# 3) TODOs in code (queued and precedence on watchers / manual triggering attributes & domains in updated exp_data)

class AggregateTable(Report):
    stylesheet = """
            .tabulator-row.tabulator-selected .tabulator-cell{
                background-color: #9abcea !important;
            }

            .tabulator-row:hover {
                background-color: #bbbbbb !important;
            }

            .tabulator .tabulator-row.tabulator-selectable:hover .tabulator-cell{
                background-color: #769bcc !important;
            }
        """

    # widget parameters
    algorithms = param.ListSelector(default=[])
    attributes = param.ListSelector(default=[])
    domains = param.ListSelector(default=[])
    precision = param.Integer(default=3, bounds=(0,15))

    # internal parameters
    # stores which attributes are unfolded (the keys, and for each
    # unfolded attribute which domains are unfolded (the values)
    unfolded = param.Dict(precedence=-1, default={})
    # for these attributes, their overall aggregates are current
    aggregated_attributes = param.List(default=[]) # TODO: Ideally we would have a set...
    # these domain aggregates (=value, set of domains) of attribute key are current
    aggregated_attribute_domains = param.Dict(default={})
    recompute_aggregate_needed = param.Event()


    def __init__(self, experiment_data, **params):
        super().__init__(experiment_data, **params)

        # ajaxLoader false is set to reduce blinking (https://github.com/olifolkerd/tabulator/issues/1027)
        self.data_view = CustomTabulator(
            value=pd.DataFrame(), disabled=True, show_index=False,
            pagination="remote", page_size=10000, frozen_columns=['Index'],
            sizing_mode='stretch_both', configuration={"ajaxLoader": "False"},
            sortable=False,  stylesheets=[AggregateTable.stylesheet]
        )
        self.used_aggregators = dict()

        def filter(df, unfolded, attributes, domains):
            if df.empty:
                return df
            indices = [(a, "--", "--") for a in attributes]
            for a, doms in unfolded.items():
                if a not in attributes:
                    continue
                indices += [(a, d, "--") for d in domains]
                for d in doms:
                    if d not in domains:
                        continue
                    indices += [(a, d, p) for p in
                                self.experiment_data.problems_by_domain[d]]
            indices.sort()
            return df.loc[indices]

        self.data_view.add_filter(pn.bind(
            filter, unfolded=self.param.unfolded, attributes=self.param.attributes,
            domains=self.param.domains
        ))
        self.data_view.on_click(self.on_click_callback)

        self.param_view.extend([
            pn.widgets.CrossSelector.from_param(
                self.param.attributes,
                name="",
                options = self.experiment_data.param.attributes,
                margin=(5, 0, 5, 0),
                width=400
                # TODO: can we have a min_width with stretching? (Could not get it to work so far)
            ),
            pn.widgets.CrossSelector.from_param(
                self.param.domains,
                name="",
                options = self.experiment_data.param.domains,
                margin=(5, 0, 5, 0),
                width=400
                # TODO: can we have a min_width with stretching? (Could not get it to work so far)
            ),
            pn.widgets.IntSlider.from_param(
                self.param.precision,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width"
            ),
        ])

        # TODO: rethink if the queued and precendence is really how we want it
        self.param.watch(self.algorithms_updated, ["algorithms"], precedence=1)
        self.param.watch(self.attributes_updated, ["attributes"], precedence=2)
        self.param.watch(self.domains_updated, ["domains"], precedence=3)
        self.experiment_data.param.watch(self.aggregators_changed, ["custom_aggregators"], precedence=4)
        self.param.watch(self.compute_needed_aggregates, ["recompute_aggregate_needed"], precedence=5)

        self.experiment_data.param.watch(self.algorithm_aliases_changed, ["custom_algorithm_aliases"])
        self.experiment_data.param.watch(self.min_wins_changed, ["custom_min_wins"])


    def style_table_by_row(self, row):
        # Give aggregates a different style, and indent Index col text if it's a domain or problem.
        style = [""] * len(row)
        if row.name[1] == "--":
            style = [x + "font-weight: bold; background-color: #E6E6E6;" for x in style]
        elif row.name[2] == "--":
            style = [x + "font-weight: bold; background-color: #F6F6F6;" for x in style]
            style[0] = style[0] + "text-indent:25px;"
        else:
            style[0] = "text-indent:50px;"
        return style


    def on_click_callback(self, e):
        row = self.data_view.value.iloc[e.row]
        attribute, domain, problem = row.name[0:3]

        # clicked on concrete problem -> open problem wise report
        if problem != "--":
            problem_report = ProblemTable(
                self.experiment_data, sizing_mode="stretch_width",
                domain=domain, problem=problem, algorithms=self.algorithms)
            self.add_popup(problem_report, name=f"{domain} - {problem}")
            return

        if domain != "--": # clicked on domain aggregate
            if domain in self.unfolded[attribute]:
                self.unfolded[attribute].remove(domain)
            else:
                self.unfolded[attribute].append(domain)
        else: # clicked on attribute aggregate
            if attribute in self.unfolded:
                self.unfolded.pop(attribute)
            else:
                self.unfolded[attribute] = []
        self.param.trigger("recompute_aggregate_needed")


    def update_data_view_table(self, patch_df):
        raise NotImplementedError

    def compute_needed_aggregates(self, *events):
        logger.debug("computing needed aggregates")
        if not isinstance(self.experiment_data.data, pd.DataFrame):
            return
        mi = pd.MultiIndex.from_tuples([], names=self.data_view.value.index.names)
        cols = {"Index": pd.Series(dtype='string')} | {a.name: pd.Series(dtype='object') for a in self.algorithms}
        patch_df = pd.DataFrame(cols, index = mi)

        def update_patch_dict(df, row, index_string, aggregator):
            # Since gmean is not a built-in function we need to set the variable
            # to the actual function here. Furthermore, since gmean cannot deal
            # with 0, we replace it with a very small positive value.
            if aggregator == "gmean":
                aggregator = stats.gmean
                df = df.replace(0, 0.000001)
            res = df.agg(aggregator)
            res["Index"] = index_string % str(len(df))
            patch_df.loc[row] = res
        def get_rows_with_index_value(df, value):
            return (df.loc[value] if value in df.index
                    else pd.DataFrame({}, columns=df.columns))

        # we want to consider all rows where all selected columns have a value
        base_data = self.experiment_data.data[[a.name for a in self.algorithms]].dropna()

        for attribute in self.experiment_data.numeric_attributes.values():
            if attribute.name not in self.attributes:
                # If the attribute is currently not shown, don't compute anything
                continue

            attribute_data = get_rows_with_index_value(base_data, attribute.name)
            if len(attribute_data) > 0:
                # remove domains that are currently not considered
                attribute_data = attribute_data.loc[attribute_data.index.get_level_values('domain').isin(self.domains)]
                attribute_data = attribute_data.apply(pd.to_numeric, errors='coerce')

            # Compute the overall attribute aggregate if it is not current.
            if attribute.name not in self.aggregated_attributes:
                row_index = (attribute.name, "--", "--")
                num_probs = sum([len(self.experiment_data.problems_by_domain[d]) for d in self.domains])
                index_string = f"{attribute.name} ({attribute.aggregator}, %s/{num_probs})"
                update_patch_dict(
                    attribute_data, row_index, index_string, attribute.aggregator)
                self.aggregated_attributes.append(attribute.name)

            # For unfolded attributes we might need to update domain aggregates.
            if attribute.name in self.unfolded:
                relevant_domains = [d for d in self.domains if d not in self.aggregated_attribute_domains[attribute.name]]
                for domain in relevant_domains:
                    domain_data = get_rows_with_index_value(attribute_data, domain)
                    row_index = (attribute.name, domain, "--")
                    index_string = f"{domain} (%s/{len(self.experiment_data.problems_by_domain[domain])})"
                    update_patch_dict(
                        domain_data, row_index, index_string, attribute.aggregator)
                self.aggregated_attribute_domains[attribute.name].update(relevant_domains)
        self.update_data_view_table(patch_df)


    def get_algorithms_on_new_experiment_data(self):
        raise NotImplementedError("get_algorithms_on_new_experiment_data not implemented")


    @param.depends("experiment_data.data", watch=True)
    def experiment_data_updated(self):
        logger.debug("experiment data was updated")
        if not hasattr(self, "data_view") or isinstance(self.data_view, pn.pane.Str):
            return

        self.param.algorithms.default = list(self.experiment_data.algorithms.values())
        self.param.attributes.default = self.experiment_data.attributes
        self.param.domains.default = self.experiment_data.domains

        # Build the rows for the aggregated values such that we later just overwrite values rather than concatenate.
        mi = pd.MultiIndex.from_product([self.experiment_data.attributes, ["--", *self.experiment_data.domains], ["--"]],
                                        names = ["attribute", "domain", "problem"])
        aggregated_data_skeleton = pd.DataFrame(data = "", index = mi, columns = [])
        # Combine experiment data and aggregated data skeleton indices into an empty dataframe.
        new_df = pd.concat([self.experiment_data.data[[]], aggregated_data_skeleton]).sort_index()

        # Add Index column (solely used in the visualization).
        pseudoindex = [x[0] if x[1]=="--" else (x[1] if x[2] == "--" else x[2]) for x in new_df.index]
        new_df.insert(0, "Index", pseudoindex)

        self.data_view.value = new_df

        self.used_aggregators = { a.name: a.aggregator for a in self.experiment_data.numeric_attributes.values()}

        self.param.update({
            "algorithms": self.get_algorithms_on_new_experiment_data(),
            "attributes": self.param.attributes.default,
            "domains": self.param.domains.default,
            "unfolded": {}
        })
        # TODO: we need to trigger attributes and domains because otherwise the widgets shows them as none selected - why?
        self.param.trigger("attributes")
        self.param.trigger("domains")


    def algorithms_updated(self, event):
        logger.debug("algorithms were updated")

        self.param.update({
            "aggregated_attributes": [],
            "aggregated_attribute_domains": {a.name: set() for a in self.experiment_data.numeric_attributes.values()},
            "recompute_aggregate_needed" : True
        })
        index_width = 17 + max([len(x) for x in self.data_view.value['Index']])*7
        col_width = 17 + max([len(x) for x in self.data_view.value.columns[1:]] + [20])*7
        widths_dict = {'Index': index_width} | {x : col_width for x in self.data_view.value.columns[1:]}
        self.data_view.widths = widths_dict


    def attributes_updated(self, event):
        logger.debug("attributes were updated")
        # Updating attributes does not invalidate aggregates, but we might need
        # to (re-)compute new ones.
        self.param.trigger("recompute_aggregate_needed")


    def domains_updated(self, event):
        logger.debug("domains were updated")
        self.aggregated_attributes = []
        self.param.trigger("recompute_aggregate_needed")


    def aggregators_changed(self, event):
        logger.debug("custom aggregators were updated")
        for attribute in self.experiment_data.numeric_attributes.values():
            if self.used_aggregators.get(attribute.name) != attribute.aggregator:
                self.used_aggregators[attribute.name] = attribute.aggregator
                self.aggregated_attributes.remove(attribute.name)
                self.aggregated_attribute_domains[attribute.name] = set()
        self.param.trigger("recompute_aggregate_needed")


    def algorithm_aliases_changed(self, event):
        logger.debug("custom algorithm aliases changed")
        self.data_view.value.columns= ["Index"] + [x.get_name() for x in self.algorithms]
        self.data_view.param.trigger("value")

    def min_wins_changed(self, event):
        logger.debug("custom min wins changed")
        self.data_view.param.trigger("value")


    @param.depends("precision", "algorithms", "experiment_data.custom_aggregators", watch=True)
    def set_formatter_for_precision(self):
        logger.debug("setting formatter for precision")
        template = f"""
          <%= function formatnumber() {{
            f_val = parseFloat(value);
            if (!isNaN(f_val)) {{
              if (Number.isInteger(f_val)) {{
                return '<div style="text-align:right">' + f_val + "</div>";
              }} else {{
                return '<div style="text-align:right">' + f_val.toFixed({self.precision}) + "</div>";
              }}
            }} else {{
              return  value;
            }}
          }}() %>
        """
        if hasattr(self, "data_view"):
            self.data_view.formatters = {x : HTMLTemplateFormatter(template=template) for x in self.data_view.value.columns}


    def get_watchers_for_param_config(self):
        return [
            "attributes",
            "domains",
            "precision"
        ]


    def get_param_config_dict(self):
        d = {}
        if set(self.attributes) != set(self.param.attributes.default):
            d['attrs'] = [self.experiment_data.get_attribute_id(a) for a in  self.attributes]
        if set(self.domains) != set(self.param.domains.default):
            d['doms'] = [self.experiment_data.get_domain_id(d) for d in self.domains]
        if self.precision != self.param.precision.default:
            d['prec'] = self.precision
        return d


    def set_params_from_param_config_dict(self, param_config_dict):
        update = {}
        if 'attrs' in param_config_dict:
            update['attributes'] = [self.experiment_data.get_attribute_by_id(id) for id in param_config_dict['attrs']]
        if 'doms' in param_config_dict:
            update['domains'] = [self.experiment_data.get_domain_by_id(id) for id in param_config_dict['doms']]
        if 'prec' in param_config_dict:
            update['precision'] = param_config_dict['prec']
        self.param.update(update)
