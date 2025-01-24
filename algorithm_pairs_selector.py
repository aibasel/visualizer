import logging
import panel as pn
from panel.viewable import Viewer
import param

logger = logging.getLogger("visualizer.algorithm_pairs_selector")


class AlgorithmPair(Viewer):
    first = param.Parameter(default="")
    second = param.Parameter(default="")

    algorithm_pairs = param.List(default=[])

    def __init__(self, algorithm_pair_selector, exp_data, **params):
        super().__init__(**params)
        self.exp_data = exp_data
        self.algorithm_pair_selector = algorithm_pair_selector

        self.set_pairs()

    @param.depends("exp_data.algorithms")
    def first_view(self):
        return pn.widgets.AutocompleteInput.from_param(
            self.param.first,
            name="",
            options=[""] + list(self.exp_data.algorithms.keys()),
            case_sensitive=False,
            search_strategy='includes',
            restrict=False,
            margin=(5, 0, 5, 0),
            min_width=100,
            sizing_mode="stretch_width",
        )

    @param.depends("exp_data.algorithms")
    def second_view(self):
        return pn.widgets.AutocompleteInput.from_param(
            self.param.second,
            name="",
            options=[""] + list(self.exp_data.algorithms.keys()),
            case_sensitive=False,
            search_strategy='includes',
            restrict=False,
            margin=(5, 0, 5, 0),
            min_width=100,
            sizing_mode="stretch_width",
        )

    @param.depends("first", "second", watch=True)
    def set_pairs(self):
        if self.first in self.exp_data.algorithms.keys() and self.second in self.exp_data.algorithms.keys():
            self.algorithm_pairs = [(self.exp_data.algorithms[self.first], self.exp_data.algorithms[self.second])]
        elif len(self.first) > 1 and len(self.second) > 1 and self.first[0] == self.first[-1] == self.second[0] == self.second[-1]:
            result = []
            subname1 = self.first[1:-1]
            subname2 = self.second[1:-1]
            match1 = [x for x in list(self.exp_data.algorithms.keys()) if subname1 in x]
            match2 = [x for x in list(self.exp_data.algorithms.keys()) if subname2 in x]
            for alg1 in match1:
                for alg2 in match2:
                    if alg1.replace(subname1, "") == alg2.replace(subname2, ""):
                        result.append((self.exp_data.algorithms[alg1], self.exp_data.algorithms[alg2]))
            self.algorithm_pairs = result
        else:
            self.algorithm_pairs = []
        self.algorithm_pair_selector.param.trigger("entries")



class AlgorithmPairsSelector(Viewer):
    entries = param.List(default=[])
    algorithm_pairs = param.List(default=[])

    def __init__(self, exp_data, **params):
        super().__init__(**params)
        self.exp_data = exp_data
        self.entries = [AlgorithmPair(self, self.exp_data)]

        self.param_view = pn.Column(
            pn.pane.HTML("<label>Algorithms</label>", margin=(5,0,0,0)),
            pn.Column(
                pn.Row(self.entries[0].first_view, self.entries[0].second_view, margin=(-5,0,0,0))
            ),
            pn.widgets.Button(name='+', button_type='primary', margin=(5,0,5,0))
        )

        def add_button_clicked(event):
            if not event:
                return
            self.entries.append(AlgorithmPair(self, self.exp_data))
            # TODO: it would be nicer to define the param_view above reactively to just contain a row for each entry
            # (then we could also avoid the setting of param_view in set_params()
            self.param_view[1].append(pn.Row(self.entries[-1].first_view, self.entries[-1].second_view, margin=(-5,0,0,0)))

        pn.bind(add_button_clicked, self.param_view[-1], watch=True)


    @param.depends("entries", watch=True)
    def set_pairs(self):
        self.algorithm_pairs = [pair for object in self.entries for pair in object.algorithm_pairs]


    def __panel__(self):
        return self.param_view


    def get_params(self):
        # TODO: It seems the encoding changes tuples to lists, can we avoid that and pass tuples here instead?
        return [ [x.first, x.second] for x in self.entries if x.algorithm_pairs != [] ]


    def set_params(self, l):
        self.entries = [AlgorithmPair(self, self.exp_data, first=x[0], second=x[1]) for x in l]
        self.param_view[1].objects = [pn.Row(x.first_view, x.second_view, margin=(-5,0,0,0)) for x in self.entries]
