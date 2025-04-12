from functools import partial
import numpy as np
import param
import pandas as pd
import panel as pn

from experiment_data import NumericAttribute
from problem_table import ProblemTable
from report import Report

class AttributeReport(Report):

    # widget parameters
    attribute = param.Parameter(label="Attribute", default="")

    # internal parameters
    domain_wins = param.DataFrame(default=pd.DataFrame(), precedence=-1)
    task_wins = param.DataFrame(default=pd.DataFrame(), precedence=-1)


    def __init__(self, experiment_data, **params):
        super().__init__(experiment_data, **params)

        self.per_task_table = pd.DataFrame()
        self.per_domain_table = pd.DataFrame()

        self.domain_view = pn.widgets.Tabulator(pd.DataFrame(), disabled = True, sortable=False, pagination="remote", page_size=1000)
        self.domain_view.style.apply(func=partial(self.style_by_row, table_type="domain"), axis=1)
        self.domain_view.on_click(self.on_domain_wise_click_callback)

        self.task_view = pn.widgets.Tabulator(pd.DataFrame(), disabled = True, sortable=False, pagination="remote", page_size=1000)
        self.task_view.style.apply(func=partial(self.style_by_row, table_type="task"), axis=1)
        self.task_view.on_click(self.on_task_wise_click_callback)

        self.data_view = pn.Column(
            pn.pane.HTML("# wins per domain", styles={'font-size': '12pt', 'font-family': 'Arial', 'font-weight': 'bold', 'padding-left': '10px'}),
            self.domain_view,
            pn.pane.HTML("# wins per task", styles={'font-size': '12pt', 'font-family': 'Arial', 'font-weight': 'bold', 'padding-left': '10px'}),
            self.task_view,
        )

        self.param_view.extend([
            pn.widgets.AutocompleteInput.from_param(
                self.param.attribute,
                name="",
                options=self.experiment_data.param.numeric_attributes,
                case_sensitive=False,
                search_strategy='includes',
                restrict=False,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width",
            ),
            pn.pane.Markdown("""
                ### Information

                Shows on how many domains/problems the row entry algorithm is
                better than the column entry algorithm. Clicking on a cell
                gives a detailed comparison table below the domain/task wise
                tables.

                When having a per task comparison open, clicking on a row will
                open a ProblemReport comparing all attributes for this specific
                problem.
            """)
        ])


    def style_by_row(self, row, table_type):
        style = [""] * len(row)
        row_alg = row.name
        df = self.task_wins if table_type == "task" else self.domain_wins

        for i, (alg, val) in enumerate(row.items()):
            if df.at[alg, row_alg] < val:
                style[i] = style[i] + "font-weight:bold;"
            elif row.name == alg:
                style[i] = style[i] + "color:gray;"
        return style


    def on_domain_wise_click_callback(self, e):
        self.domain_view.selection = []
        row_alg = self.domain_wins.iloc[e.row].name
        col_alg = e.column
        if col_alg not in self.domain_wins.columns or row_alg == col_alg:
            return
        comparison = pn.widgets.Tabulator(
            self.per_domain_table[[f"{row_alg}-{col_alg}"]],
            disabled = True, pagination="remote", page_size=100)
        self.add_popup(comparison, name=f"Domain comparison {row_alg} vs {col_alg}")


    def on_task_wise_click_callback(self, e):
        self.task_view.selection = []
        row_alg = self.task_wins.iloc[e.row].name
        col_alg = e.column
        if col_alg not in self.task_wins.columns or row_alg == col_alg:
            return
        comparison = pn.widgets.Tabulator(
            self.per_task_table[[row_alg, col_alg, f"{row_alg}-{col_alg}"]],
            disabled = True, pagination="remote", page_size=100)
        comparison.on_click(partial(self.on_comparison_click_callback, df=comparison.value))
        self.add_popup(comparison, name=f"Task comparison {row_alg} vs {col_alg}")


    def on_comparison_click_callback(self, e, df):
        row = df.iloc[e.row]
        dom = row.name[1]
        prob = row.name[2]
#        alg_names = list(set(row.keys()).intersection(set(self.experiment_data.algorithms.keys())))
        algs = [alg for name,alg in self.experiment_data.algorithms.items() if name in row.keys()]
        problem_report = ProblemTable(self.experiment_data,
            sizing_mode = "stretch_width", domain=dom, problem=prob, algorithms=algs)
        self.add_popup(problem_report, name=f"{dom} - {prob}")


    @param.depends("attribute", watch=True)
    def update_data_view(self):
        if type(self.attribute) is not NumericAttribute:
            self.data_view.value = pd.DataFrame()
            return

        min_wins = self.attribute.min_wins

        self.per_task_table = self.experiment_data.get_data(self.attribute, self.experiment_data.algorithms.values())
        self.per_task_table.replace([np.NaN, None], np.inf if min_wins else -np.inf, inplace=True)


        alg_names = [alg.get_name() for alg in self.experiment_data.algorithms.values()]
        self.task_wins = pd.DataFrame(columns = alg_names, index= alg_names)
        self.domain_wins = pd.DataFrame(columns = alg_names, index=alg_names)
        for a1 in alg_names:
            for a2 in alg_names:
                self.per_task_table[f"{a1}-{a2}"] = (self.per_task_table[a1]-self.per_task_table[a2]).replace(np.nan,0)
                win = np.sign(self.per_task_table[f"{a1}-{a2}"])
                if min_wins:
                  win *= -1
                self.task_wins.at[a1,a2] = win.value_counts().get(1,0)

                self.per_domain_table[f"{a1}-{a2}"] = win.groupby(["domain"]).sum()
                dom_win = np.sign(self.per_domain_table[f"{a1}-{a2}"])
                self.domain_wins.at[a1,a2] = dom_win.value_counts().get(1,0)

        self.domain_view.value = self.domain_wins
        self.task_view.value = self.task_wins


    def get_watchers_for_param_config(self):
        return [
            "attribute",
        ]


    def get_param_config_dict(self):
        d = {}
        if type(self.attribute) is NumericAttribute:
            d["attr"] = self.attribute.id
        return d


    def set_params_from_param_config_dict(self, d):
        update = {}
        if "attr" in d:
            update["attribute"] = self.experiment_data.get_numeric_attribute_by_position(d["attr"])
        self.param.update(update)

