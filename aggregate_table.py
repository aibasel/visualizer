from bokeh.models.widgets.tables import HTMLTemplateFormatter
import logging
import numpy as np
import param
import pandas as pd
import panel as pn
from scipy import stats

from problem_table import ProblemTable
from report import Report


logger = logging.getLogger("visualizer.aggregate_table")

class AggregateTable(Report):
    # widget parameters
    attributes = param.ListSelector(label="Attributes", default=[])
    domains = param.ListSelector(label="Domains", default=[])
    precision = param.Integer(label="Floating point precision", default=3, bounds=(0,15))

    # internal parameters
    df = param.DataFrame(precedence=-1, default=pd.DataFrame())
    view_df = param.DataFrame(precedence=-1, default=pd.DataFrame())
    unfolded = param.Dict(precedence=-1, default={})
    columns = param.List(precedence=-1, default=[])

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


    def __init__(self, experiment_data, **params):
        super().__init__(experiment_data, **params)

        # The following two variables store which aggregates are currently
        # correctly computed. Every time relevant parameters or visible rows
        # change, they are first updated and then the compute_needed_aggregates()
        # (re)computes those aggregates which are visible and out of date.
        self.attributes_aggregated = set()
        self.domains_aggregated = dict()
        # stores for which aggregator function the above two variables store correct data
        self.used_aggregators = dict()

        # ajaxLoader false is set to reduce blinking (https://github.com/olifolkerd/tabulator/issues/1027)
        self.data_view = pn.widgets.Tabulator(
            value=self.param.view_df, disabled=True, show_index=False,
            pagination="remote", page_size=10000, frozen_columns=['Index'],
            sizing_mode='stretch_both', configuration={"ajaxLoader": "False"},
            sortable=False, stylesheets=[AggregateTable.stylesheet]
        )

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
            max_length = max([1] + [len(x) for x in df.loc[indices]['Index']])
            self.data_view.widths = {'Index': 10 + max_length * 7}
            return df.loc[indices]

        self.data_view.add_filter(pn.bind(
            filter, unfolded=self.param.unfolded, attributes=self.param.attributes,
            domains=self.param.domains
        ))
        self.data_view.style.apply(func=self.style_table_by_row, axis=1)
        self.data_view.on_click(self.on_click_callback)

        self.param_view.extend([
            pn.widgets.CrossSelector.from_param(
                self.param.attributes,
                name="",
                definition_order=False,
                options = self.experiment_data.param.attributes,
                margin=(5, 0, 5, 0),
                width=400
                # TODO: can we have a min_width with stretching? (Could not get it to work so far)
            ),
            pn.widgets.CrossSelector.from_param(
                self.param.domains,
                name="",
                definition_order=False,
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


    def get_algorithms(self):
        logger.error("Child class did not implement get_algorithms()!")
        return []

    def on_click_callback(self, e):
        row = self.df.iloc[e.row]
        attribute, domain, problem = row.name[0:3]

        # clicked on concrete problem -> open problem wise report
        if problem != "--":
            problem_report = ProblemTable(
                self.experiment_data, sizing_mode="stretch_width",
                domain=domain, problem=problem, algorithms=self.get_algorithms())
            self.add_popup(problem_report, name=f"{domain} - {problem}")
            return

        # clicked on domain aggregate -> (un)fold that domain for that attribute
        if domain != "--":
            if domain in self.unfolded[attribute]:
                self.unfolded[attribute].remove(domain)
            else:
                self.unfolded[attribute].append(domain)
            self.param.trigger("unfolded")

        # clicked on attribute aggregate -> (un)fold that attribute
        else:
            if attribute in self.unfolded:
                self.unfolded.pop(attribute)
            else:
                self.unfolded[attribute] = []
                self.compute_needed_aggregates()
            self.param.trigger("unfolded")


    def compute_needed_aggregates(self):
        logger.debug("computing needed aggregates")
        def aggregate(df, aggregator):
            # Since gmean is not a built-in function we need to set the variable to the actual function here.
            # Furthermore, since gmean cannot deal with 0, we replace it with a very small positive value.
            if aggregator == "gmean":
                aggregator = stats.gmean
                df = df.replace(0, 0.000001)
            return df.agg(aggregator)

        if not isinstance(self.experiment_data.data, pd.DataFrame):
            return

        # we want to consider all rows where all selected columns have a value
        base_data = self.experiment_data.data[[alg.name for alg in self.get_algorithms()]].dropna()

        for attribute in self.experiment_data.numeric_attributes.values():
            if attribute.name not in self.attributes:
                # If the attribute is currently not shown, don't compute anything
                continue

            attribute_data = pd.DataFrame(columns=base_data.columns)
            if attribute.name in base_data.index:
                attribute_data = base_data.loc[attribute.name]
                # The aggregate only considers the domains that are currently shown
                attribute_data = attribute_data.loc[attribute_data.index.get_level_values('domain').isin(self.domains)]
                attribute_data = attribute_data.apply(pd.to_numeric, errors='coerce')

            # Compute the overall aggregate for this attribute if it is not current
            if attribute.name not in self.attributes_aggregated:
                num_problems = len(attribute_data.index)
                new_aggregates = aggregate(attribute_data, attribute.aggregator)
                # TODO: can we do this nicer? mean and gmean already report NaN for empty dataframes
                if num_problems == 0:
                    new_aggregates = new_aggregates.replace(0, np.NaN)
                index_string = f"{attribute.name} ({attribute.aggregator}, {num_problems}/{self.experiment_data.num_problems})"
                self.df.loc[(attribute.name, "--", "--")] = pd.concat([pd.Series([index_string], index=["Index"]), new_aggregates])
                self.attributes_aggregated.add(attribute.name)

            if attribute.name in self.unfolded:
                relevant_domains = [d for d in self.domains if d not in self.domains_aggregated[attribute.name]]
                if not relevant_domains:
                    break
                # Represents the slice of all domain aggregate rows, but without the Index column.
                rows, cols = (attribute.name, slice(relevant_domains[0], relevant_domains[-1]), "--"), self.df.columns[1:]
                # Clear the slice and apply combine_first (this way, the newly aggregated data is taken wherever it exists).
                self.df.loc[rows, cols] = np.NaN
                self.df.loc[rows, cols] = self.df.loc[rows, cols].combine_first(attribute_data.groupby(level=0).agg(attribute.aggregator))
                for domain in relevant_domains:
                    num_problems = len(self.experiment_data.problems_by_domain[domain])
                    num_aggregated = 0 if domain not in attribute_data.index.get_level_values(0) else len(attribute_data.loc[domain].index)
                    self.df.loc[(attribute.name, domain, "--"),'Index'] = f"{domain} ({num_aggregated}/{num_problems})"
                self.domains_aggregated[attribute.name].update(relevant_domains)
        self.redraw()
        logger.debug("done computing needed aggregates")


    @param.depends("columns", watch=True)
    def columns_updated(self):
        self.attributes_aggregated = set()
        self.domains_aggregated = {a: set() for a in self.domains_aggregated.keys()}
        self.compute_needed_aggregates()

    @param.depends("attributes", watch=True)
    def attributes_updated(self):
        self.compute_needed_aggregates()

    @param.depends("domains", watch=True)
    def domains_updated(self):
        self.attributes_aggregated = set()
        self.compute_needed_aggregates()

    @param.depends("experiment_data.custom_aggregators", watch=True)
    def aggregators_changed(self):
        for attribute in self.experiment_data.numeric_attributes.values():
            if self.used_aggregators.get(attribute.name) != attribute.aggregator:
                self.attributes_aggregated.discard(attribute.name)
                self.domains_aggregated[attribute.name] = set()
                self.used_aggregators[attribute.name] = attribute.aggregator
        self.compute_needed_aggregates()

    @param.depends("experiment_data.data", watch=True)
    def new_experiment_data(self):
        logger.debug("experiment data changed")
        self.param.domains.default = list(self.experiment_data.domains)
        self.param.attributes.default = list(self.experiment_data.attributes)

        self.domains_aggregated = {a: set() for a in self.experiment_data.numeric_attributes.keys()}
        self.used_aggregators = {name: a.aggregator for name, a in self.experiment_data.numeric_attributes.items()}

        # Build the rows for the aggregated values such that we later just overwrite values rather than concatenate.
        mi = pd.MultiIndex.from_product([self.experiment_data.attributes, ["--", *self.experiment_data.domains], ["--"]],
                                        names = ["attribute", "domain", "problem"])
        aggregated_data_skeleton = pd.DataFrame(data = "", index = mi, columns = self.experiment_data.algorithms)
        # Combine experiment data and aggregated data skeleton.
        new_df = pd.concat([self.experiment_data.data, aggregated_data_skeleton]).sort_index()

        # Add Index column (solely used in the visualization).
        pseudoindex = [x[0] if x[1]=="--" else (x[1] if x[2] == "--" else x[2]) for x in new_df.index]
        new_df.insert(0, "Index", pseudoindex)

        self.param.update({
            "domains": self.param.domains.default,
            "attributes": self.param.attributes.default,
            "columns": [],
            "df": new_df
        })


    @param.depends("precision", "view_df", watch=True)
    def set_formatter_for_precision(self):
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
            self.data_view.formatters = {x: HTMLTemplateFormatter(template=template) for x in self.view_df.columns}

# TODO it's not really nice to add min_wins here since it doesn't directly get used in the funciton,
# but otherwise the style will not be applied right away when min_wins changes
    @param.depends("df", "columns", "experiment_data.custom_min_wins", "experiment_data.custom_algorithm_aliases", watch=True)
    def redraw(self):
        self.view_df = self.df[self.columns].rename(columns=self.experiment_data.get_rename_dict())


    def get_watchers_for_param_config(self):
        return [
            "attributes",
            "domains",
            "precision"
        ]


    def get_param_config_dict(self):
        d = {}
        if self.attributes != self.param.attributes.default:
            d['attrs'] = [self.experiment_data.get_attribute_id(a) for a in  self.attributes]
        if self.domains != self.param.domains.default:
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
