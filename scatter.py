from bokeh.plotting import figure
from bokeh.models import HoverTool, TapTool, Legend, LegendItem, Span, Range1d
from functools import partial # used for calling on_click_callback
import logging
import math
import numpy as np
import pandas as pd
import panel as pn
import param

from algorithm_pairs_selector import AlgorithmPairsSelector
from experiment_data import NumericAttribute, Algorithm
from problem_table import ProblemTable
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
    replace_zero = param.Number(label="Replace 0 with", default=0, doc="Replace all 0 values with the given values (useful for log plots).")
    marker_size = param.Integer(label="Marker Size", default = 7, bounds = (2,50))
    marker_fill_alpha = param.Number(label="Marker Fill Alpha", default = 0.0, bounds=(0.0,1.0))
    legend_width = param.Integer(label="Legend Width", default = 1500, bounds = (200,5000))

    # internal parameters
    df = param.Parameter(precedence=-1)

    # config string parameters
    aps_config = param.List(default=[], precedence=-1)

    def __init__(self, experiment_data, **params):
        super().__init__(experiment_data, **params)

        self.algorithm_pairs_selector = AlgorithmPairsSelector(self.experiment_data)

        self.data_view = pn.Column(sizing_mode="stretch_both")
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
            pn.widgets.FloatInput.from_param(
                self.param.replace_zero,
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
        

    def on_click_callback(self, attr, old, new, df, source):
        if new:
            dom = df.iloc[new[0]]['domain']
            prob = df.iloc[new[0]]['problem']
            algs = [self.experiment_data.get_algorithm_by_id(x) for x in df.iloc[new[0]]['algs']]
            source.selected.indices = []
            problem_report = ProblemTable(self.experiment_data,
                sizing_mode = "stretch_width", domain=dom, problem=prob, algorithms=algs)
            self.add_popup(problem_report, name=f"{dom} - {prob}")


    @param.depends("x_attribute", "y_attribute",  "algorithm_pairs_selector.algorithm_pairs", "group_by", watch=True)
    def update_data(self):
        logger.debug("start updating data")
        if (type(self.x_attribute) is not NumericAttribute or
            type(self.y_attribute)  is not NumericAttribute):
            self.df = None
            logger.debug("end updating data (empty)")
            return

        frames = []
        # TODO: resetting the index leads to alphabetical order even for order by algorithm pair
        index_order = ['name', 'domain', 'problem'] if self.group_by == 'name' else ['domain', 'problem', 'name']
        for (xalg, yalg) in self.algorithm_pairs_selector.algorithm_pairs:
            xcol = self.experiment_data.get_data(self.x_attribute, xalg).droplevel(0)[xalg.get_name()] # get_data returns a dataframe, but we only want the xalg column
            ycol = self.experiment_data.get_data(self.y_attribute, yalg).droplevel(0)[yalg.get_name()]
            xalg_name = xalg.get_name()
            yalg_name = yalg.get_name()
            name = xalg_name if xalg == yalg else f"{xalg_name} vs {yalg_name}"
            algs = [xalg.id] if xalg == yalg else [xalg.id, yalg.id]
            new_frame = pd.DataFrame({'x':xcol, 'y':ycol, 'name':name, 'algs': [algs]*len(xcol)}).reset_index().set_index(index_order)
            frames.append(new_frame)

        if len(frames) == 0:
            self.df = None
        else:
            overall_frame = pd.concat(frames).sort_index(level=0)
            overall_frame['yrel'] = overall_frame.y.div(overall_frame.x.replace(0,  np.nan))
            self.df = overall_frame
        logger.debug("end updating data")


    @param.depends("df", "x_scale", "y_scale", "relative", "marker_size", "marker_fill_alpha", "legend_width", watch=True)
    def update_data_view(self):
        logger.debug("start updating data view")
        plot = figure(
            active_scroll = "wheel_zoom", sizing_mode="stretch_both",
            x_axis_type = self.x_scale, y_axis_type = self.y_scale)
        if self.df is None:
            logger.debug("end updating data view (empty)")
            self.data_view.objects = []
            return

        df_copy = self.df.copy()
        df_copy = df_copy.replace(0.0, self.replace_zero)


        # Compute axis labels
        def get_axis_label(dim):
            other = "y" if dim == "x" else "x"
            attribute = self.x_attribute if dim == "x" else self.y_attribute
            df_inf = df_copy.replace(np.nan, np.inf)
            dim_failed = df_inf[(df_inf[dim] == np.inf)]
            dim_failed_other_succ = dim_failed[(dim_failed[other] != np.inf)]
            dim_less = df_inf[(df_inf[dim]-df_inf[other] < 0)]
            dim_less_other_succ = dim_less[(dim_less[other] != np.inf)]
            return (f"{attribute.name}\n"
                    f"{dim}<{other}: {len(dim_less)}      "
                    f"{dim}<{other}, {other} not failed: {len(dim_less_other_succ)}      "
                    f"{dim} failed: {len(dim_failed)}      "
                    f"{dim} failed,{other} not failed: {len(dim_failed_other_succ)}")
        plot.xaxis.axis_label = get_axis_label("x")
        plot.yaxis.axis_label = get_axis_label("y")

        # Compute failed values and replace NaN with failed.
        def get_failed(df, scale):
            max_val = np.nanmax(df.replace(np.inf, np.nan).values)
            if scale == "log":
                return int(10 ** math.ceil(math.log10(max_val)))
            else:
                return max_val*1.1
        # TODO: it might be better to precompute the attribute wide max value once when loading the experiment data
        x_failed_val = get_failed(self.experiment_data.data.loc[self.x_attribute.name], self.x_scale)
        y_failed_val = get_failed(self.experiment_data.data.loc[self.y_attribute.name], self.y_scale)
        df_copy["x"] = df_copy["x"].fillna(x_failed_val)
        # yrel needs to be computed right here, i.e. after we replace the x NaN
        # values and before we replace the y NaN values. It ensures the value
        # for yrel will be yrel_failed_val if y failed, and x_failed_val/y if x failed
        # but y did not fail.
        df_copy["yrel"] = df_copy["y"].astype("float64").div(df_copy["x"].astype("float64"))
        yrel_failed_val = get_failed(df_copy["yrel"], self.y_scale)
        df_copy["y"] = df_copy["y"].fillna(y_failed_val)
        df_copy["yrel"] = df_copy["yrel"].fillna(yrel_failed_val)

        x="x"
        y="y"
        if self.relative:
            y = "yrel"
            y_failed_val = yrel_failed_val

        # Drop all non-positive coordinates if we have log axes.
        if self.x_scale == "log":
            df_copy = df_copy[~(df_copy[x] <= 0)]
        if self.y_scale == "log":
            df_copy = df_copy[~(df_copy[y] <= 0)]
        # Drop all points where y_rel is infinity if we plot yrel.
        if y == "yrel":
            df_copy = df_copy[~(df_copy[y] != np.inf)]
        size_diff = len(self.df)-len(df_copy)
        if len(df_copy) == 0:
            self.user_logger.log(logging.WARNING,
                "All points have been dropped due to non-positive values in log "
                "plots or infinite values in relative y.")
            self.data_view.objects = []
            return
        elif size_diff > 0:
            self.user_logger.log(logging.INFO,
                f"Dropped {size_diff} points due to non-positive values in log "
                "plots or infinite values in relative y.")

        plot.x_range = Range1d(df_copy[x].min()*0.9, df_copy[x].max()*1.1)
        plot.y_range = Range1d(df_copy[y].min()*0.9, df_copy[y].max()*1.1)

        indices = df_copy.index.get_level_values(0).unique()
        legend_items = []
        for i, index in enumerate(indices):
            p_df = df_copy.loc[[index]].reset_index()
            p = plot.scatter(x=x, y=y, source=p_df,
                line_color=COLORS[i%len(COLORS)], marker=MARKERS[i%len(MARKERS)],
                fill_color=COLORS[i%len(COLORS)], fill_alpha=self.marker_fill_alpha,
                size=self.marker_size, muted_fill_alpha = min(0.1,self.marker_fill_alpha))
            p.data_source.selected.on_change('indices', partial(self.on_click_callback, df=p_df, source=p.data_source))
            legend_items.append(LegendItem(label=index, renderers = [plot.renderers[i]]))

        # helper lines
        plot.renderers.extend([Span(location=x_failed_val, dimension='height', line_color='red')])
        plot.renderers.extend([Span(location=y_failed_val, dimension='width', line_color='red')])
        plot.xaxis.major_label_overrides = {x_failed_val : "failed"}
        plot.yaxis.major_label_overrides = {y_failed_val : "failed"}
        if self.relative:
            plot.line(x=[df_copy[x].min()*0.9, x_failed_val], y=[1,1], color='black')
        else:
            min_max = [min(df_copy[x].min()*0.9, df_copy[y].min()*0.9), max(x_failed_val, y_failed_val)]
            plot.line(x=min_max, y=min_max, color='black')


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
        logger.debug("end __panel__")
        self.data_view.objects = [plot]


    # TODO: figure out if we can do this more directly
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
