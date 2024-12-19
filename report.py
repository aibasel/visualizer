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

    # Returns a list of parameters who when changed trigger an update to the
    # param_config string stored in server.py.
    def get_watchers_for_param_config(self):
        return list(self.param.values().keys())

    # Returns a dict containing all information needed for recreating the
    # current view. This dict will be built every time any of the parameters
    # from get_watchers_for_param_config() (in this and other classes) changes.
    def get_param_config_dict(self):
        ret = self.param.values()
        ret.pop("name")
        return ret

    # Sets parameters based on the given param_config_dict, which was built by
    # get_param_config_dict().
    def set_params_from_param_config_dict(self, param_config_dict):
        self.param.update(param_config_dict)