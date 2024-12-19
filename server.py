import base64 #for encoding the compressed json parameter dict as url
import json #for dumping the parameter dict as json
import panel as pn
from panel.viewable import Viewer
import param
import zlib #for compressing the json parameter dict

from custom_logging import logging, custom_formatter
from experiment_data import ExperimentData
from scatter import ScatterReport

from custom_golden_template import GoldenTemplate

logger = logging.getLogger("visualizer")


class FullViewer(Viewer):

    selected_report = param.Selector(label="Report Type")
    experiment_data = param.Parameter(precedence=-1)
    param_config = param.String(precedence=-1) #encodes all relevant parameter information in a string that is passed to the url
    log_messages = param.String(precedence=-1)

    def __init__(self, **params):
        super().__init__(**params)

        self.experiment_data = ExperimentData()
        self.reports = [
            ScatterReport(name="A", experiment_data=self.experiment_data),
            ScatterReport(name="B", experiment_data=self.experiment_data),
            ScatterReport(name="C", experiment_data=self.experiment_data),
        ]
        self.param.selected_report.objects = self.reports

        # We wrap param and report views into a Column since we need one
        # constant object whose visibility we manipulate when switching
        # report type. (Param and report views might return new objects.)
        self.report_param_views = pn.Column(*[pn.Column(x.param_view) for x in self.reports])
        self.report_data_views = pn.Column(*[pn.Column(report) for report in self.reports])
        self.log_view = pn.Column(pn.Column(scroll=True),scroll=True)

        self.template = GoldenTemplate(
            title='Visualizer',
            sidebar=pn.Column(
                pn.widgets.Select.from_param(
                    self.param.selected_report,
                    options={},
                    margin=(10, 0, 5, 0),
                    min_width=100,
                    sizing_mode="stretch_width"
                ),
                pn.pane.Markdown("## Properties", margin=(25,0,0,0)),
                pn.layout.Divider(margin=(-15,0,0,0)),
                self.experiment_data.param_view,
                pn.pane.Markdown("## Report", margin=(25,0,0,0)),
                pn.layout.Divider(margin=(-15,0,0,0)),
                *self.report_param_views,
                sizing_mode="stretch_width",
                scroll=True
            ),
            main=pn.Column(
                *self.report_data_views,
                sizing_mode="stretch_both",
                scroll=True,
            ),
            modal=pn.pane.Str(self.param.log_messages)
        )
        # HACK: if we initialize the Select widget with the right options, we
        # get an expand button (https://github.com/holoviz/panel/issues/3836)
        # Initializing it empty and changing the options afterwards avoids this.
        self.template.sidebar[0].options = {x.name: x for x in self.reports}


    def log_event(self, record):
        if record.levelno >= logging.INFO:
            self.log_messages = custom_formatter.format(record) + "\n" + self.log_messages
        return True

    def __panel__(self):
        return self.template

    @param.depends("selected_report", watch=True)
    def report_selected(self):
        logger.debug("setting selected report")
        for i, report in enumerate(self.reports):
            self.report_param_views[i].visible = bool(self.selected_report == report)
            self.report_data_views[i].visible = bool(self.selected_report == report)


    # will load the parameters from the url or set a default if url contains no information
    def load_params(self):
        if not self.param_config:
            self.selected_report = self.reports[0]
            return

        logger.debug("loading parameters from url")

        params = json.loads(zlib.decompress(
            base64.urlsafe_b64decode(self.param_config.encode())))
        logger.debug(f"loading param dict: {params}")
        logger.debug("loading selected report")
        self.selected_report = self.reports[params["repid"]]
        logger.debug("loading experiment data params")
        self.experiment_data.set_params_from_param_config_dict(params["data"])
        logger.debug("loading selected report params")
        self.selected_report.set_params_from_param_config_dict(params["rep"])

        logger.debug("done loading parameters from url")


    def setup_param_config_watchers(self):
        self.param.watch(self.set_param_config, ["selected_report"])
        self.experiment_data.param.watch(
            self.set_param_config,
            self.experiment_data.get_watchers_for_param_config()
        )
        for report in self.reports:
            report.param.watch(
                self.set_param_config,
                report.get_watchers_for_param_config()
            )


    # sets a url based on the current parameter values
    def set_param_config(self, *events):
        self.param_config = ""
        logger.debug("setting param config string")
        # we only want to set an url if the properties file was passed by url
        if self.experiment_data.properties_mode == "file":
            self.param_config = ""
            return

        params = {
            "repid" : self.reports.index(self.selected_report),
            "data": self.experiment_data.get_param_config_dict(),
            "rep" : self.selected_report.get_param_config_dict()
        }
        self.param_config = base64.urlsafe_b64encode(zlib.compress(json.dumps(params).encode())).decode()
        logger.debug(f"set param config string with dictionary {params}")



overall_view = FullViewer()
pn.state.location.sync(overall_view, { "param_config" : "c" })
overall_view.load_params()
overall_view.setup_param_config_watchers()
overall_view.servable()
