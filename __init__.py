# -*- coding: utf-8 -*-
def classFactory(iface):
    from .sample_design import SampleDesign
    return SampleDesign(iface)
