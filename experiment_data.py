import panel as pn
import param

from custom_logging import logging

logger = logging.getLogger("visualizer.experiment_data")

class ExperimentData(param.Parameterized):
    number = param.Integer(label="Number", doc="a number")
    word = param.String(label="Word", doc="a word")

    def __init__(self, **params):
        super().__init__(**params)

        self.number = 3
        self.word = "hello"

        self.param_view = pn.WidgetBox("## Experiment Data Options",
            pn.Param(self.param.number),
            pn.Param(self.param.word)
        )

    # returns a dict containing all information needed for recreating the current view
    def get_param_config_dict(self):
        ret = self.param.values()
        ret.pop("name")
        return ret

    # sets parameters based on the param_config_dict
    def set_params_from_param_config_dict(self, param_config_dict):
        self.param.update(param_config_dict)