import logging
import panel as pn
from panel.viewable import Viewer
import param

from user_logger import UserLogger
from experiment_data import ExperimentData

logger = logging.getLogger("visualizer.report")


class Report(Viewer):

    experiment_data = param.Parameter(precedence=-1)


    def __init__(self, experiment_data, **params):
        self.user_logger = params.pop("user_logger", UserLogger())
        super().__init__(**params)

        self.experiment_data=experiment_data
        self.param_view = pn.Column(sizing_mode="stretch_width") #stores all report parameter widgets
        # Child classes should set data_view in init and never fully change the object
        # (as an example see scatter.py, where it is initialized as a column and then the objects of the column are changed
        self.data_view = pn.pane.Str("Placeholder data view")
        self.popup = pn.Column(height=0, width=0)

    def __panel__(self):
        logger.debug("start __panel__")
        self.popup.objects = [x for x in self.popup.objects if x.status != "closed"]
        logger.debug("end __panel__")
        return pn.Column(self.data_view, self.popup)

    def add_popup(self, panel, name):
        logger.debug(f"appending float panel with name {name}")
        self.popup.append(pn.layout.FloatPanel(
            panel, name = name, contained = False, height = 750, width = 750,
            position = "center", config = {"closeOnEscape" : True}
        ))


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
