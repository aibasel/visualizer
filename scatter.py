from bokeh.plotting import figure
from bokeh.models import HoverTool, TapTool, Legend, LegendItem, Span, Range1d
import math
import numpy as np
import pandas as pd
import panel as pn
import param

from algorithm_pairs_selector import AlgorithmPairsSelector
from custom_logging import logging
from experiment_data import NumericAttribute, Algorithm
from report import Report

logger = logging.getLogger("visualizer.scatter")

MARKERS = ["x", "circle", "square", "triangle", "asterisk",
           "diamond", "cross", "star", "inverted_triangle", "plus",
           "hex", "y", "circle_cross", "square_cross", "diamond_cross",
           "circle_x", "square_x", "square_pin", "triangle_pin"]
COLORS = ["black", "red", "blue", "teal", "orange",
          "purple", "olive", "lime", "cyan"]

class ScatterReport(Report):

    # widget parameters
    x_attribute = param.Parameter(label="X Axis Attribute", default="")
    y_attribute = param.Parameter(label="Y Axis Attribute", default="")
    algorithm_pairs_selector = param.Parameter()
    x_scale = param.Selector(label="X Axis Scale", objects=["log", "linear"], default="log")
    y_scale = param.Selector(label="Y Axis Scale", objects=["log", "linear"], default="log")
    relative = param.Boolean(label="Relative", default=False, doc="If true, the values on the y axis are replaced with y/x.")
    group_by = param.Selector(label="Group By", objects=["name", "domain"], default="name")
    marker_size = param.Integer(label="Marker Size", default = 7, bounds = (2,50))
    marker_fill_alpha = param.Number(label="Marker Fill Alpha", default = 0.0, bounds=(0.0,1.0))
    legend_width = param.Integer(label="Legend Width", default = 1800, bounds = (200,10000))

    # internal parameters
    df = param.Parameter(precedence=-1)

    # config string parameters
    aps_config = param.List(default=[], precedence=-1)

    def __init__(self, experiment_data, **params):
        super().__init__(experiment_data, **params)

        self.algorithm_pairs_selector = AlgorithmPairsSelector(self.experiment_data)
        self.param.algorithm_pairs = self.algorithm_pairs_selector.param.algorithm_pairs

        self.param_view.extend([
            pn.pane.HTML("<label>Attributes</label>", margin=(5, 0, -5, 0)),
            pn.Row(
                pn.widgets.AutocompleteInput.from_param(
                    self.param.x_attribute,
                    name="",
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
                    name="",
                    options=self.experiment_data.param.numeric_attributes,
                    case_sensitive=False,
                    search_strategy='includes',
                    restrict=False,
                    margin=(5, 0, 5, 0),
                    min_width=100,
                    sizing_mode="stretch_width",
                ),
                sizing_mode="stretch_width"
            ),
            self.algorithm_pairs_selector,
            pn.pane.HTML("<label>Scale</label>", margin=(5, 0, -5, 0)),
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
            pn.widgets.Checkbox.from_param(
                self.param.relative,
                margin=(5, 0, 5, 0),
            ),
            pn.pane.HTML("<label>Group By</label>", margin=(5, 0, -5, 0)),
            pn.widgets.RadioButtonGroup.from_param(
                self.param.group_by,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width"
            ),
            pn.widgets.IntSlider.from_param(
                self.param.marker_size,
                margin=(5, 0, 5, 0),
                min_width=100,
                sizing_mode="stretch_width"
            ),
            pn.widgets.FloatSlider.from_param(
                self.param.marker_fill_alpha,
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

        self.plot = figure(active_scroll = "wheel_zoom", sizing_mode="stretch_both")


    @param.depends("x_attribute", "y_attribute",  "algorithm_pairs_selector.algorithm_pairs", "group_by", watch=True)
    def update_data(self):
        logger.debug("start updating data")
        if (type(self.x_attribute) is not NumericAttribute or
            type(self.y_attribute)  is not NumericAttribute):
            self.df = None
            logger.debug("end updating data (empty)")
            return

        frames = []
        index_order = ['name', 'domain', 'problem'] if self.group_by == 'name' else ['domain', 'problem', 'name']
        for (xalg, yalg) in self.algorithm_pairs_selector.algorithm_pairs:
            xcol = self.experiment_data.get_data(self.x_attribute, xalg)
            ycol = self.experiment_data.get_data(self.y_attribute, yalg)
            if len(xcol) != len(ycol):
                continue
            xalg_name = xalg.get_name()
            yalg_name = yalg.get_name()
            name = xalg_name if xalg == yalg else f"{xalg_name} vs {yalg_name}"
            algs = [xalg_name] if xalg == yalg else [xalg_name, yalg_name]
            new_frame = pd.DataFrame({'x':xcol, 'y':ycol, 'name':name, 'algs': [algs]*len(xcol)}).reset_index().set_index(index_order)
            frames.append(new_frame)

        if len(frames) == 0:
            self.df = None
        else:
            overall_frame = pd.concat(frames).sort_index(level=0)
            overall_frame['yrel'] = overall_frame.y.div(overall_frame.x.replace(0,  np.nan))
            self.df = overall_frame
        logger.debug("end updating data")


    @param.depends("df", "x_scale", "y_scale", "relative", "marker_size", "marker_fill_alpha", "legend_width")
    def __panel__(self):
        logger.debug("start __panel__")
        self.plot = figure(
            active_scroll = "wheel_zoom", sizing_mode="stretch_both",
            x_axis_type = self.x_scale, y_axis_type = self.y_scale)
        if self.df is None:
            logger.debug("end __panel__ (empty)")
            return self.plot

        df_alt = self.df.copy()

        def get_failed(max_val, scale):
            if scale == "log":
                return int(10 ** math.ceil(math.log10(max_val)))
            else:
                return max_val*1.1

        # Compute failed values and replace NaN with failed.
        # TODO: it might be better to precompute the attribute wide max value once when loading the experiment data
        x_failed = get_failed(np.nanmax(self.experiment_data.data.loc[self.x_attribute.name].values), self.x_scale)
        y_failed = get_failed(np.nanmax(self.experiment_data.data.loc[self.x_attribute.name].values), self.y_scale)
        with pd.option_context('future.no_silent_downcasting', True):
            df_alt["x"] = df_alt["x"].fillna(x_failed)
        # yrel needs to be computed right here, i.e. after we replace the x NaN
        # values and before we replace the y NaN values. It ensures the value
        # for yrel will be yrel_failed if y failed, and x_failed/y if x failed
        # but y did not fail.
        df_alt["yrel"] = df_alt["y"].div(df_alt["x"])
        yrel_failed = get_failed(df_alt["yrel"].max(), self.y_scale)
        with pd.option_context('future.no_silent_downcasting', True):
            df_alt["y"] = df_alt["y"].fillna(y_failed)
            df_alt["yrel"] = df_alt["yrel"].fillna(yrel_failed)

        x="x"
        y="y"
        if self.relative:
            y = "yrel"
            y_failed = yrel_failed

        # Drop all non-positive coordinates if we have log axes.
        if self.x_scale == "log":
            df_alt = df_alt[~(df_alt[x] <= 0)]
        if self.y_scale == "log":
            df_alt = df_alt[~(df_alt[y] <= 0)]
        logger.info(f"dropped {len(self.df)-len(df_alt)} points with non-positive coordinates")

        self.plot.x_range = Range1d(df_alt[x].min()*0.9, df_alt[x].max()*1.1)
        self.plot.y_range = Range1d(df_alt[y].min()*0.9, df_alt[y].max()*1.1)

        indices = df_alt.index.get_level_values(0).unique()
        legend_items = []
        for i, index in enumerate(indices):
            p = self.plot.scatter(x=x, y=y, source=df_alt.loc[[index]].reset_index(),
                line_color=COLORS[i%len(COLORS)], marker=MARKERS[i%len(MARKERS)],
                fill_color=COLORS[i%len(COLORS)], fill_alpha=self.marker_fill_alpha,
                size=self.marker_size, muted_fill_alpha = min(0.1,self.marker_fill_alpha))
            legend_items.append(LegendItem(label=index, renderers = [self.plot.renderers[i]]))

        # helper lines
        self.plot.renderers.extend([Span(location=x_failed, dimension='height', line_color='red')])
        self.plot.renderers.extend([Span(location=y_failed, dimension='width', line_color='red')])
        self.plot.xaxis.major_label_overrides = {x_failed : "failed"}
        self.plot.yaxis.major_label_overrides = {y_failed : "failed"}
        if self.relative:
            self.plot.line(x=[df_alt[x].min()*0.9, x_failed], y=[1,1], color='black')
        else:
            min_max = [min(df_alt[x].min()*0.9, df_alt[y].min()*0.9), max(x_failed, y_failed)]
            self.plot.line(x=min_max, y=min_max, color='black')


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


    @param.depends("algorithm_pairs_selector.algorithm_pairs", watch=True)
    def set_aps_config(self):
        self.aps_config = self.algorithm_pairs_selector.get_params()


    def get_watchers_for_param_config(self):
        return [
            "x_attribute",
            "y_attribute",
            "aps_config",
            "x_scale",
            "y_scale",
            "relative",
            "group_by",
            "marker_size",
            "marker_fill_alpha",
            "legend_width"
        ]


    def get_param_config_dict(self):
        d = {}
        if type(self.x_attribute) is NumericAttribute:
            d['xattr'] = self.x_attribute.id
        if type(self.y_attribute) is NumericAttribute:
            d['yattr'] = self.y_attribute.id
        if self.aps_config != self.param.aps_config.default:
            d['aps_config'] = self.aps_config
        if self.x_scale != self.param.x_scale.default:
            d['xscale'] = self.x_scale
        if self.y_scale != self.param.y_scale.default:
            d['yscale'] = self.y_scale
        if self.relative != self.param.relative.default:
            d['rel'] = self.relative
        if self.group_by != self.param.group_by.default:
            d['group_by'] = self.group_by
        if self.marker_size != self.param.marker_size.default:
            d['m_size'] = self.marker_size
        if self.marker_fill_alpha != self.param.marker_fill_alpha.default:
            d['m_alpha'] = self.marker_fill_alpha
        if self.legend_width != self.param.legend_width.default:
            d['l_width'] = self.legend_width
        return d


    def set_params_from_param_config_dict(self, d):
        if "aps_config" in d:
            self.algorithm_pairs_selector.set_params(d["aps_config"])
        update = {}
        if "xattr" in d:
            update["x_attribute"] = self.experiment_data.get_numeric_attribute_by_id(d["xattr"])
        if "yattr" in d:
            update["y_attribute"] = self.experiment_data.get_numeric_attribute_by_id(d["yattr"])
        if "xscale" in d:
            update["x_scale"] = d["xscale"]
        if "yscale" in d:
            update["y_scale"] = d["yscale"]
        if "rel" in d:
            update["relative"] = d["rel"]
        if "group_by" in d:
            update["group_by"] = d["group_by"]
        if "m_size" in d:
            update["marker_size"] = d["m_size"]
        if "m_alpha" in d:
            update["marker_fill_alpha"] = d["m_alpha"]
        if "l_width" in d:
            update["legend_width"] = d["l_width"]
        self.param.update(update)