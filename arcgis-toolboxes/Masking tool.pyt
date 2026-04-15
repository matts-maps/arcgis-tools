# -*- coding: utf-8 -*-
import arcpy
import os

class Toolbox(object):
    def __init__(self):
        self.label = "Surrounding Area Mask Tools"
        self.alias = "masktools"
        self.tools = [GenerateMask]

class GenerateMask(object):
    def __init__(self):
        self.label = "Generate Surrounding Area Mask"
        self.description = (
            "Creates a surrounding area mask using the Erase tool. "
            "The only variable is the final name, determined by whether the AOI is an island."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []

        # AOI
        p0 = arcpy.Parameter(
            displayName="Area of Interest (AOI)",
            name="aoi",
            datatype="Feature Layer",
            parameterType="Required",
            direction="Input"
        )

        # Geoextent
        p1 = arcpy.Parameter(
            displayName="Geoextent",
            name="geoextent",
            datatype="String",
            parameterType="Required",
            direction="Input"
        )

        # Datasource
        p2 = arcpy.Parameter(
            displayName="Datasource",
            name="datasource",
            datatype="String",
            parameterType="Required",
            direction="Input"
        )

        # Output workspace
        p3 = arcpy.Parameter(
            displayName="Output Workspace (Folder or GDB)",
            name="out_ws",
            datatype="Workspace",
            parameterType="Required",
            direction="Input"
        )

        # Island checkbox
        p4 = arcpy.Parameter(
            displayName="AOI is an island",
            name="is_island",
            datatype="Boolean",
            parameterType="Required",
            direction="Input"
        )
        p4.value = False

        # Erase dataset
        p5 = arcpy.Parameter(
            displayName="Erase Dataset",
            name="erase_ds",
            datatype="Feature Layer",
            parameterType="Required",
            direction="Input"
        )

        return [p0, p1, p2, p3, p4, p5]

    def execute(self, params, messages):
        # Layer objects (not strings)
        aoi_layer = params[0].value
        geoextent = params[1].valueAsText
        datasource = params[2].valueAsText
        out_ws = params[3].valueAsText
        is_island = params[4].value
        erase_layer = params[5].value

        arcpy.env.overwriteOutput = True

        # ----------------------------------------------------
        # 1. Resolve AOI to a real feature class
        # ----------------------------------------------------
        try:
            aoi_path = arcpy.Describe(aoi_layer).catalogPath
        except:
            aoi_path = ""

        if aoi_path:
            aoi = aoi_path
        else:
            aoi = "in_memory\\aoi_resolved"
            arcpy.management.CopyFeatures(aoi_layer, aoi)
            messages.addMessage("AOI copied to in_memory for stability.")

        # ----------------------------------------------------
        # 2. Resolve erase dataset to a real feature class
        # ----------------------------------------------------
        try:
            erase_path = arcpy.Describe(erase_layer).catalogPath
        except:
            erase_path = ""

        if erase_path:
            erase_ds = erase_path
        else:
            erase_ds = "in_memory\\erase_resolved"
            arcpy.management.CopyFeatures(erase_layer, erase_ds)
            messages.addMessage("Erase dataset copied to in_memory for stability.")

        # ----------------------------------------------------
        # 3. Output name (only variable in the tool)
        # ----------------------------------------------------
        if is_island:
            out_name = f"{geoextent}_phys_ocn_py_s0_{datasource}_pp_ocean"
        else:
            out_name = f"{geoextent}_carto_msk_py_s0_{datasource}_pp_mask"

        out_fc = os.path.join(out_ws, out_name)

        # ----------------------------------------------------
        # 4. Erase (always the same operation)
        # ----------------------------------------------------
        messages.addMessage("Running Erase operation...")
        arcpy.analysis.Erase(erase_ds, aoi, out_fc)

        # ----------------------------------------------------
        # 5. Add output to map
        # ----------------------------------------------------
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        m = aprx.activeMap
        m.addDataFromPath(out_fc)

        messages.addMessage(f"Mask created: {out_fc}")
        messages.addMessage("Layer added to map.")