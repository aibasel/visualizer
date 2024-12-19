from bokeh.plotting import figure
from bokeh.models import HoverTool, TapTool, Legend, LegendItem, Span
import math
import numpy as np
import pandas as pd
import panel as pn
import param

from custom_logging import logging
from experiment_data import NumericAttribute, Algorithm
from report import Report

logger = logging.getLogger("visualizer.scatter")


class ScatterReport(Report):

    # widget parameters
    x_attribute = param.Parameter(label="X Axis Attribute", default="")
    y_attribute = param.Parameter(label="Y Axis Attribute", default="")
    x_algorithm = param.Parameter(label="X Algorithm Attribute", default="")
    y_algorithm = param.Parameter(label="Y Algorithm Attribute", default="")

    # internal parameters
    df = param.Parameter(precedence=-1)


    def __init__(self, experiment_data, **params):
        super().__init__(experiment_data, **params)

        self.param_view.extend([
            pn.widgets.AutocompleteInput.from_param(
                self.param.x_attribute,
                options=self.experiment_data.param.numeric_attributes,
                case_sensitive=False,
                search_strategy='includes',
                restrict=False,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width",
            ),
            pn.widgets.AutocompleteInput.from_param(
                self.param.y_attribute,
                options=self.experiment_data.param.numeric_attributes,
                case_sensitive=False,
                search_strategy='includes',
                restrict=False,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width",
            ),
            pn.widgets.AutocompleteInput.from_param(
                self.param.x_algorithm,
                options=self.experiment_data.param.algorithms,
                case_sensitive=False,
                search_strategy='includes',
                restrict=False,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width",
            ),
            pn.widgets.AutocompleteInput.from_param(
                self.param.y_algorithm,
                options=self.experiment_data.param.algorithms,
                case_sensitive=False,
                search_strategy='includes',
                restrict=False,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width",
            ),
        ])

        self.plot = figure(active_scroll = "wheel_zoom", sizing_mode="stretch_both")


    @param.depends("x_attribute", "y_attribute", "x_algorithm", "y_algorithm", watch=True)
    def update_data(self):
        logger.debug("start updating data")
        if (type(self.x_attribute) is not NumericAttribute or
            type(self.y_attribute)  is not NumericAttribute):
            self.df = None
            logger.debug("end updating data (empty)")
            return

        frames = []
        index_order = ['name', 'domain', 'problem']
        # TODO: adjust once more than one alg pair is possible
        i=0
        for (xalg, yalg) in [(self.x_algorithm, self.y_algorithm)]:
            if type(xalg) is not Algorithm or type(yalg) is not Algorithm:
                continue
            xcol = self.experiment_data.get_data(self.x_attribute, xalg)
            ycol = self.experiment_data.get_data(self.y_attribute, yalg)
            if len(xcol) != len(ycol):
                continue
            xalg_name = xalg.get_name()
            yalg_name = yalg.get_name()
            yrel = ycol.div(xcol.replace(0, np.nan))
            name = xalg_name if xalg == yalg else f"{xalg_name} vs {yalg_name}"
            algs = [xalg_name] if xalg == yalg else [xalg_name, yalg_name]
            new_frame = pd.DataFrame({'x':xcol, 'y':ycol, 'yrel': yrel, 'name':name, 'algs': [algs]*len(xcol)}).reset_index().set_index(index_order)
            frames.append(new_frame)
            i=i+1

        if len(frames) == 0:
            self.df = None
        else:
            overall_frame = pd.concat(frames).sort_index(level=0)
            overall_frame['yrel'] = overall_frame.y.div(overall_frame.x.replace(0,  np.nan))
            self.df = overall_frame
        logger.debug("end updating data")


    @param.depends("df")
    def __panel__(self):
        logger.debug("start __panel__")
        self.plot = figure(active_scroll = "wheel_zoom", sizing_mode="stretch_both")
        if self.df is None:
            logger.debug("end __panel__ (empty)")
            return self.plot

        indices = self.df.index.get_level_values(0).unique()
        legend_items = []
        for i, index in enumerate(indices):
            p = self.plot.scatter(x="x", y="y", source=self.df.loc[[index]].reset_index(),
                line_color="black", marker="x",
                fill_color="black", fill_alpha=0.5,
                size=10, muted_fill_alpha = 0.1)
            legend_items.append(LegendItem(label=index, renderers = [self.plot.renderers[i]]))

        # compute appropriate number of columns and height of legend
        indices_length = [len(i) for i in indices]
        ncols = 1
        for i in range(len(indices)):
            ncols += 1
            nrows = math.ceil(len(indices)/ncols)
            if nrows*(ncols-1) >= len(indices): #no rows gained
                continue
            max_num_chars_per_column = [max(indices_length[x*nrows:min((x+1)*nrows, len(indices))]) for x in range(ncols)]
            width = sum([7*x+20 for x in max_num_chars_per_column])+20
            if (width > 1800): # TODO: make 1800 a parameter
                ncols -= 1
                break

        # legend
        legend = Legend(items = legend_items, location="center")
        legend.click_policy="mute"
        self.plot.add_layout(legend, "below")
        self.plot.legend.ncols = ncols

        # hover info
        self.plot.add_tools(HoverTool(tooltips=[
            ('Domain', '@domain'),
            ('Problem', '@problem'),
            ('Name', '@name'),
            ('x', '@x'),
            ('y', '@y'),
            ('yrel', '@yrel'),
            ]))
        self.plot.add_tools(TapTool())
        logger.debug("end __panel__")
        return self.plot

    def get_watchers_for_param_config(self):
        return [
            "x_attribute",
            "y_attribute",
            "x_algorithm",
            "y_algorithm"
        ]


    def get_param_config_dict(self):
        d = {}
        if type(self.x_attribute) is NumericAttribute:
            d['xattr'] = self.x_attribute.id
        if type(self.y_attribute) is NumericAttribute:
            d['yattr'] = self.y_attribute.id
        if type(self.x_algorithm) is Algorithm:
            d['xalg'] = self.x_algorithm.id
        if type(self.y_algorithm) is Algorithm:
            d['yalg'] = self.y_algorithm.id
        return d


    def set_params_from_param_config_dict(self, d):
        update = {}
        if "xattr" in d:
            update["x_attribute"] = self.experiment_data.get_numeric_attribute_by_id(d["xattr"])
        if "yattr" in d:
            update["y_attribute"] = self.experiment_data.get_numeric_attribute_by_id(d["yattr"])
        if "xalg" in d:
            update["x_algorithm"] = self.experiment_data.get_algorithm_by_id(d["xalg"])
        if "yalg" in d:
            update["y_algorithm"] = self.experiment_data.get_algorithm_by_id(d["yalg"])
        self.param.update(update)