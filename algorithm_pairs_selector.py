import panel as pn
from panel.viewable import Viewer
import param

from custom_logging import logging
from experiment_data import Algorithm

logger = logging.getLogger("visualizer.algorithm_pairs_selector")

class AlgorithmPair(Viewer):
    first = param.Parameter(default="")
    second = param.Parameter(default="")

    def __init__(self, algorithm_pair_selector, exp_data, **params):
        super().__init__(**params)
        self.exp_data = exp_data
        self.algorithm_pair_selector = algorithm_pair_selector

    def first_view(self):
        ret = pn.widgets.AutocompleteInput.from_param(
            self.param.first,
            name="",
            options=list(self.exp_data.algorithms.keys()),
            case_sensitive=False,
            search_strategy='includes',
            restrict=False,
            margin=(5, 0, 5, 0),
            min_width=100,
            sizing_mode="stretch_width",
        )
        return ret

    def second_view(self):
        ret = pn.widgets.AutocompleteInput.from_param(
            self.param.second,
            name="",
            options=list(self.exp_data.algorithms.keys()),
            case_sensitive=False,
            search_strategy='includes',
            restrict=False,
            margin=(5, 0, 5, 0),
            min_width=100,
            sizing_mode="stretch_width",
        )
        return ret

    @param.depends("first", "second", watch=True)
    def trigger_algorithm_pairs_update(self):
        self.algorithm_pair_selector.param.trigger("entries")

    def get_pairs(self):
        if self.first == "" and self.second == "":
            return []
        ret = []
        if self.first[0] == self.first[-1] == self.second[0] == self.second[-1]:
            subname1 = self.first[1:-1]
            subname2 = self.second[1:-1]
            match1 = [x for x in list(self.exp_data.algorithms.keys()) if subname1 in x]
            match2 = [x for x in list(self.exp_data.algorithms.keys()) if subname2 in x]
            for alg1 in match1:
                for alg2 in match2:
                    if alg1.replace(self.first, "") == alg2.replace(self.second, ""):
                        ret.append((self.exp_data.algorithms[alg1], self.exp_data.algorithms[alg2]))
        else:
            if self.first in list(self.exp_data.algorithms.keys()) and self.second in list(self.exp_data.algorithms.keys()):
                ret.append((self.exp_data.algorithms[self.first], self.exp_data.algorithms[self.second]))
        return ret



class AlgorithmPairsSelector(Viewer):
    entries = param.List(default=[])

    def __init__(self, exp_data, **params):
        super().__init__(**params)
        self.exp_data = exp_data
        self.entries = [AlgorithmPair(self, self.exp_data)]

        self.param_view = pn.Column(
            pn.pane.HTML("<label>Algorithms</label>", margin=(5,0,-5,0)),
            pn.Column(
                pn.Row(self.entries[0].first_view, self.entries[0].second_view)
            ),
            pn.widgets.Button(name='+', button_type='primary', margin=(5,0,5,0))
        )

        def add_button_clicked(event):
            if not event:
                return
            self.entries.append(AlgorithmPair(self, self.exp_data))
            self.param_view[1].append(pn.Row(self.entries[-1].first_view, self.entries[-1].second_view, margin=(-5,0,0,0)))

        pn.bind(add_button_clicked, self.param_view[-1], watch=True)

    def get_pairs(self):
        result = []
        for entry in self.entries:
            result += entry.get_pairs()
        return result

    def __panel__(self):
        return self.param_view