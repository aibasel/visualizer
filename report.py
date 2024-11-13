import panel as pn
from panel.viewable import Viewer
import param


from experiment_data import ExperimentData

class Report(Viewer):

    experiment_data : ExperimentData = param.Parameter(precedence=-1)

    def __init__(self, experiment_data, **params):
        super().__init__(**params)

        self.experiment_data=experiment_data
        self.param_view = pn.Column()
