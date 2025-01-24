import logging
import panel as pn
from panel.viewable import Viewer, Viewable
import param
import time

logging.basicConfig(format='%(asctime)s [%(name)s %(levelname)s]: %(message)s', force=True)
logging.getLogger("visualizer").setLevel(logging.DEBUG)

class UserLogger(Viewer):

    messages = param.String(default="")

    def __init__(self, **params):
        super().__init__(**params)
        self.logger = logging.getLogger("visualizer.user")
        self.view = pn.pane.Str(self.param.messages)

    def log(self, level, message):
        self.logger.log(level, message)
        t = time.strftime("%H:%M:%S", time.localtime())
        self.messages = f"{t} [{logging.getLevelName(level)}]: {message}\n" + self.messages

    def __panel__(self):
        return pn.pane.Str(self.param.messages)
