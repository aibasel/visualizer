from bokeh.plotting import figure
from bokeh.models import HoverTool, TapTool, Legend, LegendItem, Span
import math
import numpy as np
import pandas as pd
import panel as pn
import param

from custom_logging import logging
from report import Report

logger = logging.getLogger("visualizer.scatter")


class ScatterReport(Report):

    x_attribute = param.String(label="X Axis Attribute")
    y_attribute = param.String(label="Y Axis Attribute")
    x_algorithm = param.String(label="X Algorithm Attribute")
    y_algorithm = param.String(label="Y Algorithm Attribute")

    df = param.Parameter(precedence=-1)


    def __init__(self, experiment_data, **params):
        super().__init__(experiment_data, **params)

        self.param_view.extend([
            pn.Param(self.param.x_attribute),
            pn.Param(self.param.y_attribute),
            pn.Param(self.param.x_algorithm),
            pn.Param(self.param.y_algorithm)
        ])

        self.plot = figure(active_scroll = "wheel_zoom")


    @param.depends("x_attribute", "y_attribute", "x_algorithm", "y_algorithm", watch=True)
    def update_data(self):
        if (self.x_attribute not in self.experiment_data.numeric_attributes.keys() or
                self.y_attribute not in self.experiment_data.numeric_attributes.keys()):
            self.df = pd.DataFrame()
            return

        frames = []
        index_order = ['name', 'domain', 'problem']
        # TODO: adjust once more than one alg pair is possible
        i=0
        for (xalg, yalg) in [(self.x_algorithm, self.y_algorithm)]:
            if xalg == "" or yalg == "":
                continue
            xcol = self.experiment_data.get_data(self.x_attribute, xalg)
            ycol = self.experiment_data.get_data(self.y_attribute, yalg)
            if len(xcol) != len(ycol):
                continue
            yrel = ycol.div(xcol.replace(0, np.nan))
            name = xalg if xalg == yalg else f"{xalg} vs {yalg}"
            algs = [xalg] if xalg == yalg else [xalg, yalg]
            new_frame = pd.DataFrame({'x':xcol, 'y':ycol, 'yrel': yrel, 'name':name, 'algs': [algs]*len(xcol)}).reset_index().set_index(index_order)
            frames.append(new_frame)
            i=i+1

        if len(frames) == 0:
            self.df = pd.DataFrame()
        else:
            overall_frame = pd.concat(frames).sort_index(level=0)
            overall_frame['yrel'] = overall_frame.y.div(overall_frame.x.replace(0,  np.nan))
            self.df = overall_frame



    @param.depends("df")
    def __panel__(self):
        plot = figure(active_scroll="wheel_zoom", sizing_mode="stretch_both")
        if self.df is None:
            return plot

        indices = self.df.index.get_level_values(0).unique()
        legend_items = []
        for i, index in enumerate(indices):
            p = plot.scatter(x="x", y="y", source=self.df.loc[[index]].reset_index(),
                line_color="black", marker="x",
                fill_color="black", fill_alpha=0.5,
                size=10, muted_fill_alpha = 0.1)
            legend_items.append(LegendItem(label=index, renderers = [plot.renderers[i]]))

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
        plot.add_layout(legend, "below")
        plot.legend.ncols = ncols

        # hover info
        plot.add_tools(HoverTool(tooltips=[
            ('Domain', '@domain'),
            ('Problem', '@problem'),
            ('Name', '@name'),
            ('x', '@x'),
            ('y', '@y'),
            ('yrel', '@yrel'),
            ]))
        plot.add_tools(TapTool())
        return plot



    def get_param_config_dict(self):
        return {
            "x_attribute" : self.x_attribute,
            "y_attribute" : self.y_attribute,
            "x_algorithm" : self.x_algorithm,
            "y_algorithm" : self.y_algorithm
        }