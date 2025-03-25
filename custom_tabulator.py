import panel as pn

class CustomTabulator(pn.widgets.Tabulator):
    def _update_style(self, recompute=True):
        super()._update_style(recompute=True)
        self.selection = []
        # We don't need to restore the actual selection since this seems to
        # trigger automatically after styling
