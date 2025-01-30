from bokeh.models.widgets.tables import HTMLTemplateFormatter
import logging
import param
import pandas as pd
import panel as pn

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

        self.data_view = pn.widgets.Tabulator(
            value=self.param.df.rx()[self.param.columns], disabled=True, show_index=False,
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
            self.param.trigger("unfolded")


    @param.depends("experiment_data.data", watch=True)
    def new_experiment_data(self):
        logger.debug("experiment data changed")
        self.param.domains.default = list(self.experiment_data.domains)
        self.param.attributes.default = list(self.experiment_data.attributes)

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


    @param.depends("precision", "df", watch=True)
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
            self.data_view.formatters = {x: HTMLTemplateFormatter(template=template) for x in self.df.columns}