from io import BytesIO # for reading in bytestrings for file upload
import pandas as pd
import panel as pn
import param

from custom_logging import logging

logger = logging.getLogger("visualizer.experiment_data")


class ExperimentData(param.Parameterized):

    properties_url = param.String()
    properties_file = param.FileSelector()
    properties_mode = param.Selector(objects=["file", "url"], default="url",
        doc="whether the properties file should be uploaded as file or specified as url")

    data = param.DataFrame(precedence=-1)

    def __init__(self, **params):
        super().__init__(**params)

        self.param_view = pn.WidgetBox("## Experiment Data Options",
            pn.Row(
                pn.pane.HTML(
                    "<label>Properties</label>",
                    margin=(10, 0, 0, 20)
                ),
                pn.widgets.TooltipIcon(
                    margin=(10, 0, 0, 0), value=
                    "Expects a json file or an archive containing a json "
                    "file. It can either be uploaded or linked by url. "
                    "If url is used, you can share your current report "
                    "view by copying the link in the address bar."
                )
            ),
            pn.Param(self.param.properties_mode,
                widgets={'properties_mode': {
                    'widget_type': pn.widgets.RadioBoxGroup,
                    'inline': True}},
                margin=(0, 0, -8, 10),
            ),
            pn.Param(self.param.properties_url, margin=(0, 10),
                visible = (self.param.properties_mode.rx() == "url")
            ),
            pn.Param(self.param.properties_file,
                widgets={'properties_file': pn.widgets.FileInput},
                margin=(0, 10),
                visible=(self.param.properties_mode.rx() == "file"),
            )
        )


    @param.depends("properties_mode", watch=True)
    def switch_properties_mode(self):
        logger.debug("start method switch properties mode")
        if self.properties_mode == "url":
            self.properties_file = None
        else:
            self.properties_url = ""


    @param.depends("properties_url", "properties_file", watch=True)
    def set_data(self):
        logger.debug("start method set data")
        properties = None
        if self.properties_mode == "url" and self.properties_url != "":
            properties = self.properties_url
        elif self.properties_file is not None:
            properties = BytesIO(self.properties_file)

        if properties is None: #empty input
            self.data = pd.DataFrame()
        else:
            prop_from = "file" if self.properties_mode == "file" else properties
            logger.info("reading in properties from " + prop_from)
            try:
                self.data = pd.read_json(properties, orient="index")
                logger.info("done reading in properties")
            except Exception as e:
                self.data = pd.DataFrame()
                logger.warning("Could not read properties")

        print(self.data)


    # returns a dict containing all information needed for recreating the current view
    def get_param_config_dict(self):
        relevant_params = [
            "properties_url",
        ]
        return { key: self.param.values()[key] for key in relevant_params }


    # sets parameters based on the param_config_dict
    def set_params_from_param_config_dict(self, param_config_dict):
        self.param.update(param_config_dict)
