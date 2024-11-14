import base64 #for encoding the compressed json parameter dict as url
import json #for dumping the parameter dict as json
import panel as pn
from panel.viewable import Viewer
import param
import zlib #for compressing the json parameter dict

from experiment_data import ExperimentData
from scatter import ScatterReport


class FullViewer(Viewer):

    selected_report = param.Selector(label="Report Type")
    experiment_data = param.Parameter(precedence=-1)
    param_config = param.String(precedence=-1) # encodes all relevant parameter information in a string that is passed to the url


    def __init__(self, **params):
        super().__init__(**params)

        self.experiment_data = ExperimentData()
        self.reports = [
            ScatterReport(name="A", experiment_data=self.experiment_data),
            ScatterReport(name="B", experiment_data=self.experiment_data),
            ScatterReport(name="C", experiment_data=self.experiment_data),
        ]
        self.param.selected_report.objects = self.reports

        # set up all watchers for triggering an update in param_config whenever
        # a relevant parameter changed
        self.param.watch(self.set_param_config, ["selected_report"])
        self.experiment_data.param.watch(
            self.set_param_config,
            list(self.experiment_data.param.values().keys())
        )
        for report in self.reports:
            report.param.watch(
                self.set_param_config,
                list(report.param.values().keys())
            )

        # set up the overall view
        self.report_param_views = pn.Column(*[x.param_view for x in self.reports])
        self.report_data_views = pn.Column(*self.reports)
        self.view = pn.Row(
            pn.Column(
                pn.Param(self.param.selected_report, expand_button=False),
                self.experiment_data.param_view,
                *self.report_param_views
            ),
            pn.Column(
                *self.report_data_views
            )
        )


    @param.depends("selected_report")
    def __panel__(self):
        for i, report in enumerate(self.reports):
            self.report_param_views[i].visible = bool(self.selected_report == report)
            self.report_data_views[i].visible = bool(self.selected_report == report)
        return self.view


    # will load the parameters from the url or set a default if url contains no information
    def load_params(self):
        if not self.param_config:
            self.selected_report = self.reports[0]
            return

        params = json.loads(zlib.decompress(
            base64.urlsafe_b64decode(self.param_config.encode())))
        self.selected_report = self.reports[params["repidx"]]
        self.experiment_data.set_params_from_param_config_dict(params["expdata"])
        self.selected_report.set_params_from_param_config_dict(params["report"])


    # sets a url based on the current parameter values
    def set_param_config(self, *events):
        params = {
            "repidx" : self.reports.index(self.selected_report),
            "expdata": self.experiment_data.get_param_config_dict(),
            "report" : self.selected_report.get_param_config_dict()
        }
        self.param_config = base64.urlsafe_b64encode(zlib.compress(json.dumps(params).encode())).decode()



overall_view = FullViewer()
pn.state.location.sync(overall_view, { "param_config" : "c" })
overall_view.load_params()
overall_view.servable()