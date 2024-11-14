import pandas as pd
import panel as pn
import param

from report import Report

class ScatterReport(Report):

    param1 = param.Integer(label="Param 1", doc="First scatter parameter")
    param2 = param.String(label="Param 2", doc="Second scatter parameter")

    df = param.Parameter(precedence=-1)

    def __init__(self, experiment_data, **params):
        self.df = pd.DataFrame({'col1': [1,2], 'col2': [3,4]})
        super().__init__(experiment_data, **params)

        self.param1 = 5
        self.param2 = self.name

        self.param_view.append(pn.WidgetBox("## Scatter Report Options",
            pn.Param(self.param.param1),
            pn.Param(self.param.param2),
        ))


    @param.depends("param1", watch=True)
    def change_df1(self):
        print("changing df based on param1")
        self.df['col1'][0] = self.param1
        self.param.trigger('df')


    @param.depends("experiment_data.number", watch=True)
    def change_df2(self):
        print("changing df based on experiment_data.number")
        self.df['col2'][1] = self.experiment_data.number
        self.param.trigger('df')


    def __panel__(self):
        return pn.Column(
            pn.pane.Str(self.experiment_data.param.word),
            pn.pane.Str(self.param.param2),
            pn.widgets.Tabulator(self.param.df) #we need to pass the parameter object so it is reactive
        )

    def get_param_config_dict(self):
        return {
            "param1" : self.param1,
            "param2" : self.param2
        }
