import base64 #for encoding the compressed json parameter dict as url
import json #for dumping the parameter dict as json
import panel as pn
from panel.viewable import Viewer
import param
import zlib #for compressing the json parameter dict

from custom_logging import logging, custom_formatter
from experiment_data import ExperimentData
from scatter import ScatterReport

logger = logging.getLogger("visualizer")


custom_template_def = """
{% extends golden %}

{% block contents %}
<header class="app-bar" id="header">
  <div style="display: contents;">
    <div class="app-header">
      {% if app_logo %}<a href="{{ site_url }}"><img src="{{ app_logo }}" class="app-logo"></a>{% endif %}
      {% if site_title %}<a class="title" href="{{ site_url }}" >{{ site_title }}</a>{% endif %}
      {% if site_title and app_title%}<span class="title">-</span>{% endif %}
      {% if app_title %}<a class="title" href="">{{ app_title }}</a>{% endif %}
    </div>
    <section class="header-contents">
      {% for doc in docs %}
      {% for root in doc.roots %}
      {% if "header" in root.tags %}
      {{ embed(root) }}
      {% endif %}
      {% endfor %}
      {% endfor %}
    </section>
    {% if busy %}
    <div class="pn-busy-container">
      {{ embed(roots.busy_indicator) | indent(6) }}
    </div>
    {% endif %}
  </div>
</header>

<div class="main-area header-adjust" id="main">
  <main class="main-content" id="main-content"></main>
  <div id="pn-Modal" class="pn-modal header-adjust">
    <div class="pn-modal-content">
      <span class="pn-modalclose" id="pn-closeModal">&times;</span>
      {% for doc in docs %}
      {% for root in doc.roots %}
      {% if "modal" in root.tags %}
      {{ embed(root) | indent(6) }}
      {% endif %}
      {% endfor %}
      {% endfor %}
    </div>
  </div>
</div>

<script type="text/javascript">
  var config = {
    content: [
      {
        type: 'row',
        content: [
	  {% if nav %}
          {
            type: 'component',
            componentName: 'view',
            componentState: {
              title: "Sidebar",
              model: '<div class="sidebar-contents">{% for doc in docs %}{% for root in doc.roots %}{% if "nav" in root.tags %} {{ embed(root) }} {% endif %}{% endfor %}{% endfor %}</div>'
            },
            width: {{ sidebar_width }},
            isClosable: false
          },
	  {% endif %}
          {
            type: 'stack',
            width: {% if nav %}100-{{ sidebar_width }}{% else %}100{% endif %},
            content: [
              {% for doc in docs %}
              {% for root in doc.roots %}
              {% if "main" in root.tags %}
              {
                type: 'component',
                componentName: 'view',
                componentState: {
                  model: '{{ embed(root) }}',
                  title: "{{ root_labels[root.name] }}"
                },
                isClosable: false
              },
              {% endif %}
              {% endfor %}
              {% endfor %}
            ]
          }
        ]
      }
    ],
    settings: {
      showPopoutIcon: false
    }
  };

  var myLayout = new GoldenLayout(config, $('#main-content'));
  var resizing = false;
  var resize_dispatcher = () => {
    resizing = true;
    window.dispatchEvent(new Event("resize"))
    resizing = false;
  }

  myLayout.registerComponent('view', function( container, componentState ) {
    const {width, css_classes} = componentState
    if (width) {
      container.on('open', () => container.setSize(width, container.height))
    }
    if (css_classes) {
      css_classes.map((item) => container.getElement().addClass(item))
    }
    container.setTitle(componentState.title)
    container.getElement().html(componentState.model);
    container.on("resize", resize_dispatcher)
  })


  myLayout.init()
  window.addEventListener('resize', (event) => {
    if (!resizing) {
      myLayout.updateSize($('#main-content').width(), $('#main-content').height())
    }
  });

  var modal = document.getElementById("pn-Modal");
  var span = document.getElementById("pn-closeModal");

  span.onclick = function() {
    modal.style.display = "none";
  }

  window.onclick = function(event) {
    if (event.target == modal) {
      modal.style.display = "none";
    }
  }
</script>

{% block state_roots %}
{{ super() }}
{% endblock %}

{% endblock %}
"""


class FullViewer(Viewer):

    selected_report = param.Selector(label="Report Type")
    experiment_data = param.Parameter(precedence=-1)
    param_config = param.String(precedence=-1) #encodes all relevant parameter information in a string that is passed to the url


    def __init__(self, **params):
        super().__init__(**params)

        self.experiment_data = ExperimentData()
        self.reports = [
            ScatterReport(name="A", experiment_data=self.experiment_data),
            ScatterReport(name="B", experiment_data=self.experiment_data),
            ScatterReport(name="C", experiment_data=self.experiment_data),
        ]
        self.param.selected_report.objects = self.reports

        # set up terminal for logger output
        terminal_options = {
            "disableStdin": True,
            "cursorBlink": False,
            "cursorInactiveStyle": "none",
            "cursorStyle": "bar"
        }
        self.terminal = pn.widgets.Terminal(height=150, options=terminal_options,
                                       sizing_mode='stretch_width')
        stream_handler = logging.StreamHandler(self.terminal)
        stream_handler.terminator = "  \n"
        stream_handler.setFormatter(custom_formatter)
        stream_handler.setLevel(logging.INFO)
        logger.addHandler(stream_handler)

        self.report_param_views = pn.Column(*[x.param_view for x in self.reports])
        self.report_data_views = pn.Column(*self.reports)


    def __panel__(self):
        template = pn.template.GoldenTemplate(
            title='Visualizer',
            sidebar=pn.Column(
                pn.Param(self.param.selected_report, expand_button=False),
                self.experiment_data.param_view,
                *self.report_param_views,
                sizing_mode="stretch_both",
                scroll=True
            )
        )
        template.main.append(pn.Column(
            *self.report_data_views,
            self.terminal,
            sizing_mode="stretch_both",
            scroll=True,
        ))
        print(template.config.__dir__())
        return template

    @param.depends("selected_report", watch=True)
    def report_selected(self):
        for i, report in enumerate(self.reports):
            logger.debug("changing report views visibility")
            self.report_param_views[i].visible = bool(self.selected_report == report)
            self.report_data_views[i].visible = bool(self.selected_report == report)


    # will load the parameters from the url or set a default if url contains no information
    def load_params(self):
        logger.debug("loading parameters from url")
        if not self.param_config:
            self.selected_report = self.reports[0]
            return
        params = json.loads(zlib.decompress(
            base64.urlsafe_b64decode(self.param_config.encode())))
        logger.debug("loading selected report")
        self.selected_report = self.reports[params["repidx"]]
        logger.debug("loading experiment data params")
        self.experiment_data.set_params_from_param_config_dict(params["expdata"])
        logger.debug("loading selected report params")
        self.selected_report.set_params_from_param_config_dict(params["report"])


    def setup_param_config_watchers(self):
        # TODO: it might be inefficient to watch *all* parameters, we could also let each class decide
        self.param.watch(self.set_param_config, ["selected_report"])
        self.experiment_data.param.watch(
            self.set_param_config,
            list(self.experiment_data.param.values().keys())
        )
        for report in self.reports:
            report.param.watch(
                self.set_param_config,
                list(report.param.values().keys())
            )


    # sets a url based on the current parameter values
    def set_param_config(self, *events):
        logger.debug("setting param config string")
        # we only want to set an url if the properties file was passed by url
        if self.experiment_data.properties_mode == "file":
            self.param_config = ""
            return

        params = {
            "repidx" : self.reports.index(self.selected_report),
            "expdata": self.experiment_data.get_param_config_dict(),
            "report" : self.selected_report.get_param_config_dict()
        }
        self.param_config = base64.urlsafe_b64encode(zlib.compress(json.dumps(params).encode())).decode()



overall_view = FullViewer()
pn.state.location.sync(overall_view, { "param_config" : "c" })
overall_view.load_params()
overall_view.setup_param_config_watchers()
overall_view.servable()
