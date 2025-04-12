from bokeh.plotting import figure
from bokeh.models import HoverTool, TapTool, Legend, LegendItem, Span
import logging
import math
import numpy as np
import param
import pandas as pd
import panel as pn

from experiment_data import NumericAttribute
from report import Report


logger = logging.getLogger("visualizer.cactus")


COLORS = ["black", "red", "blue", "teal", "orange",
          "purple", "olive", "lime", "cyan"]


class Cactusplot(Report):

    # widget parameters
    attribute = param.Parameter(label="Attribute", default="")
    algorithms = param.ListSelector()
    x_scale = param.Selector(label="X Axis scale", default = "log", objects = ["log","linear"])
    y_scale = param.Selector(label="Y Axis scale", default = "linear", objects = ["log","linear"])
    replace_zero = param.Number(default = 0,
        doc = "Replace all 0 values with the chosen number. Afterwards, all 0 values will be dropped.")
    line_width = param.Integer(default = 2, bounds=(1,10))
    legend_width = param.Integer(label="Legend Width", default = 1500, bounds = (200,5000))


    def __init__(self, experiment_data, **params):
        super().__init__(experiment_data, **params)

        self.data_view = pn.Column(sizing_mode="stretch_both")
        self.param_view.extend([
            pn.widgets.AutocompleteInput.from_param(
                self.param.attribute,
                name="",
                options=self.experiment_data.param.numeric_attributes,
                case_sensitive=False,
                search_strategy='includes',
                restrict=False,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width",
            ),
            pn.widgets.CrossSelector.from_param(
                self.param.algorithms,
                name="",
                definition_order=False,
                options=self.experiment_data.param.algorithms,
                margin=(5, 0, 5, 0),
                width=400
                # TODO: can we have a min_width with stretching? (Could not get it to work so far)
            ),
            pn.Row(
                pn.widgets.RadioButtonGroup.from_param(
                    self.param.x_scale,
                    name="",
                    margin=(5, 0, 5, 0),
                    min_width=100,
                    sizing_mode="stretch_width"
                ),
                pn.widgets.RadioButtonGroup.from_param(
                    self.param.y_scale,
                    name="",
                    margin=(5, 0, 5, 0),
                    min_width=100,
                    sizing_mode="stretch_width"
                ),
                sizing_mode="stretch_width"
            ),
            pn.widgets.FloatInput.from_param(
                self.param.replace_zero,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width"
            ),
            pn.widgets.IntSlider.from_param(
                self.param.line_width,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width"
            ),
            pn.widgets.IntSlider.from_param(
                self.param.legend_width,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width"
            )
        ])


    @param.depends("experiment_data.data", watch=True)
    def experiment_data_updated(self):
        self.param.algorithms.default =  list(self.experiment_data.algorithms.values())
        self.algorithms = self.param.algorithms.default

    @param.depends("attribute", "algorithms", "x_scale", "y_scale", "replace_zero", "line_width", "experiment_data.custom_algorithm_aliases", watch=True)
    def update_data_view(self):
        logger.debug("start updating data view")
        if type(self.attribute) is not NumericAttribute or not self.algorithms:
            return

        # Build the DataFrame used in the plot.
        frames = []
        max_values = {}
        for alg in self.algorithms:
            xcol = np.sort(self.experiment_data.get_data(self.attribute, alg)[alg.get_name()].dropna())
            max_values[alg] = len(xcol)
            ycol = np.array(range(1,len(xcol)+1))
            new_frame = pd.DataFrame({'x':xcol, 'y':ycol, 'name':alg.get_name()})
            frames.append(new_frame)
        overall_frame = pd.concat(frames)
        overall_frame.replace(0, self.replace_zero, inplace=True)

        if self.x_scale == "log":
            overall_frame = overall_frame[~(overall_frame['x'] <= 0)]
        if self.y_scale == "log":
            overall_frame = overall_frame[~(overall_frame['y'] <= 0)]

        if overall_frame.empty or pd.isnull(overall_frame['x']).all() or pd.isnull(overall_frame['y']).all():
            self.data_view = pn.pane.Markdown("All points have been dropped")
            return

        # Define axis labels
        xlabel = self.attribute.name
        ylabel = "coverage"

        xmax = overall_frame['x'].max()
        for alg in self.algorithms:
            overall_frame.loc[len(overall_frame)] = [xmax, max_values[alg], alg.get_name()]
        overall_frame.set_index("name", inplace=True)

        indices = [x.get_name() for x in self.algorithms]
        plot = figure(x_axis_label=xlabel, y_axis_label = ylabel,
                      x_axis_type = self.x_scale, y_axis_type = self.y_scale,
                      active_scroll = "wheel_zoom", sizing_mode="stretch_both")

        legend_items = []
        for i, index in enumerate(indices):
            df = overall_frame.loc[[index]].reset_index()
            p = plot.step(x='x', y='y', source=df, line_width=self.line_width,
                line_color=COLORS[i%len(COLORS)], mode="after")
            # the line plot is invisible but allows for hover (step does not offer support for hover: https://github.com/bokeh/bokeh/wiki/Glyph-Hit-Testing-Census)
            p = plot.line(x='x', y='y', source=df, line_alpha=0)
            legend_items.append(LegendItem(label=index, renderers = [plot.renderers[2*i]]))

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
            if (width > self.legend_width):
                ncols -= 1
                break

        # legend
        legend = Legend(items = legend_items)
        legend.click_policy='mute'
        plot.add_layout(legend, 'below')
        plot.legend.ncols = ncols


        # hover info
        plot.add_tools(HoverTool(tooltips=[
            (self.attribute.name, '@x'),
            ('coverage', '@y'),
            ('algorithm', '@name'),
            ]))

        self.data_view.objects = [plot]


    def get_watchers_for_param_config(self):
        return [
            "attribute",
            "algorithms",
            "x_scale",
            "y_scale",
            "replace_zero",
            "line_width",
            "legend_width"
        ]


    def get_param_config_dict(self):
        d = {}
        if type(self.attribute) is NumericAttribute:
            d["attr"] = self.attribute.id
        if self.algorithms != self.param.algorithms.default:
            d["alg"] = [alg.id for alg in self.algorithms]
        if self.x_scale != self.param.x_scale.default:
            d["xsc"] = self.x_scale
        if self.y_scale != self.param.y_scale.default:
            d["ysc"] = self.y_scale
        if self.replace_zero != self.param.replace_zero.default:
            d["rep0"] = self.replace_zero
        if self.line_width != self.param.line_width.default:
            d["linew"] = self.line_width
        if self.legend_width != self.param.legend_width.default:
            d["legw"] = self.legend_width
        return d



    def set_params_from_param_config_dict(self, d):
        update = dict()
        if "attr" in d:
            update["attribute"] = self.experiment_data.get_numeric_attribute_by_id(d["attr"])
        if "alg" in d:
            update["algorithms"] = [self.experiment_data.get_algorithm_by_id(id) for id in d["alg"]]
        if "xsc" in d:
            update["x_scale"] = d["xsc"]
        if "ysc" in d:
            update["y_scale"] = d["ysc"]
        if "rep0" in d:
            update["replace_zero"] = d["rep0"]
        if "linew" in d:
            update["line_width"] = d["linew"]
        if "legw" in d:
            update["legend_width"] = d["legw"]
        self.param.update(update)