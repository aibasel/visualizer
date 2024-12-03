"""
GoldenTemplate based on the golden-layout library.
"""
from __future__ import annotations

import pathlib

from typing import Literal

import param

from panel.template.base import BasicTemplate
from panel.layout import ListLike

npm_cdn = "https://cdn.jsdelivr.net/npm"
CDN_DIST = f"https://cdn.holoviz.org/panel/1.4.4/dist/"
JS_URLS = {
    'jQuery': f'{CDN_DIST}bundled/jquery/jquery.slim.min.js',
    'bootstrap4': f'{CDN_DIST}bundled/bootstrap4/js/bootstrap.bundle.min.js',
    'bootstrap5': f'{CDN_DIST}bundled/bootstrap5/js/bootstrap.bundle.min.js'
}


class GoldenTemplate(BasicTemplate):
    """
    GoldenTemplate is built on top of golden-layout library.
    """

    sidebar_width = param.Integer(default=20, constant=True, doc="""
        The width of the sidebar in percent.""")

    _css = pathlib.Path(__file__).parent / 'golden.css'

    _template = pathlib.Path(__file__).parent / 'golden.html'


    _resources = {
        'css': {
            'goldenlayout': f"{npm_cdn}/golden-layout@1.5.9/src/css/goldenlayout-base.css",
            'golden-theme-dark': f"{npm_cdn}/golden-layout@1.5.9/src/css/goldenlayout-dark-theme.css",
            'golden-theme-light': f"{npm_cdn}/golden-layout@1.5.9/src/css/goldenlayout-light-theme.css"
        },
        'js': {
            'jquery': "https://cdn.holoviz.org/panel/1.4.4/dist/bundled/jquery/jquery.slim.min.js",
            'goldenlayout': "https://cdn.jsdelivr.net/npm/golden-layout@1.5.9/dist/goldenlayout.min.js"
        }



    }

    def _apply_root(self, name, model, tags):
        if 'main' in tags:
            model.margin = (10, 15, 10, 10)

    def resolve_resources(
        self,
        cdn: bool | Literal['auto'] = 'auto',
        extras: dict[str, dict[str, str]] | None = None
    ) -> ResourcesType:
        resources = super().resolve_resources(cdn=cdn, extras=extras)
        del_theme = 'dark' if self._design.theme._name =='default' else 'light'
        del resources['css'][f'golden-theme-{del_theme}']
        return resources