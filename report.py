import panel as pn
from panel.viewable import Viewer
import param

from custom_logging import logging
from experiment_data import ExperimentData

logger = logging.getLogger("visualizer.report")


class Report(Viewer):

    experiment_data : ExperimentData = param.Parameter(precedence=-1)


    def __init__(self, experiment_data, **params):
        super().__init__(**params)

        self.experiment_data=experiment_data
        self.param_view = pn.Column(sizing_mode="stretch_width") #stores all report parameter widgets

    # returns a dict containing all information needed for recreating the current view
    def get_param_config_dict(self):
        ret = self.param.values()
        ret.pop("name")
        return ret

    # sets parameters based on the given param_config_dict
    def set_params_from_param_config_dict(self, param_config_dict):
        self.param.update(param_config_dict)