import panel as pn
import param

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
