import panel as pn
from panel.viewable import Viewer
import param

from experiment_data import ExperimentData
from scatter import ScatterReport


class FullViewer(Viewer):

    selected_report = param.Selector(label="Report Type")

    def __init__(self, **params):
        super().__init__(**params)

        experiment_data = ExperimentData()
        self.reports = [
            ScatterReport(name="A", experiment_data=experiment_data),
            ScatterReport(name="B", experiment_data=experiment_data),
            ScatterReport(name="C", experiment_data=experiment_data),
        ]
        self.param.selected_report.objects = self.reports

        self.report_param_views = pn.Column(*[x.param_view for x in self.reports])
        self.report_data_views = pn.Column(*self.reports)
        self.view = pn.Row(
            pn.Column(
                pn.Param(self.param.selected_report, expand_button=False),
                experiment_data.param_view,
                *self.report_param_views
            ),
            pn.Column(
                *self.report_data_views
            )
        )

        # set after building the GUI because it triggers the __panel__ method
        self.selected_report = self.param.selected_report.objects[0]

    @param.depends("selected_report")
    def __panel__(self):
        for i, report in enumerate(self.reports):
            self.report_param_views[i].visible = bool(self.selected_report == report)
            self.report_data_views[i].visible = bool(self.selected_report == report)
        return self.view


overall_view = FullViewer()
overall_view.servable()
