# -*- coding: utf-8 -*-
import arcpy
import os

class Toolbox(object):
    def __init__(self):
        self.label = "Clip and Rename World Data"
        self.alias = "clipworld"
        self.tools = [ClipWorld]


class ClipWorld(object):
    def __init__(self):
        self.label = "Clip and Rename World Data"
        self.description = (
            "Clips admin, elevation, and physical layers from a folder and "
            "renames them using a user-defined geoextent prefix. "
            "The physical layer is dissolved into a single feature. "
            "Outputs can optionally be added to the map."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        params = []

        # Input folder
        in_folder = arcpy.Parameter(
            displayName="Input Folder",
            name="in_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
        )
        in_folder.value = r"E:\world-data\admin\openstreetmap-land-sea-coastline"
        params.append(in_folder)

        # Geoextent (user-defined)
        geoextent = arcpy.Parameter(
            displayName="Geoextent Prefix",
            name="geoextent",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
        geoextent.value = "geoextent"
        params.append(geoextent)

        # Clip boundary (TOC layer or FC)
        p_clip = arcpy.Parameter(
            displayName="Clip Feature (Layer or Feature Class)",
            name="clip_feature",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )
        params.append(p_clip)

        # Output workspace
        out_ws = arcpy.Parameter(
            displayName="Output Workspace (Folder or GDB)",
            name="out_ws",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input"
        )
        params.append(out_ws)

        # Add to map?
        add_to_map = arcpy.Parameter(
            displayName="Add Outputs to Map",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        add_to_map.value = True
        params.append(add_to_map)

        return params

    def execute(self, params, messages):
        in_folder = params[0].valueAsText
        geoextent = params[1].valueAsText
        clip_fc = params[2].valueAsText
        out_ws = params[3].valueAsText
        add_to_map = params[4].value

        # Expected patterns
        patterns = {"admn": None, "elev": None, "phys": None}

        # Scan folder for matching files
        for fname in os.listdir(in_folder):
            lower = fname.lower()

            if not lower.endswith(".shp"):
                continue

            for key in patterns:
                if f"_{key}_" in lower:
                    patterns[key] = os.path.join(in_folder, fname)

        # Validate presence
        for key, path in patterns.items():
            if path is None:
                raise arcpy.ExecuteError(
                    f"Missing required file containing '_{key}_' in folder: {in_folder}"
                )

        # Process each file
        for key, fc_path in patterns.items():
            out_fc = self.process_fc(key, fc_path, clip_fc, out_ws, geoextent, messages)

            if add_to_map:
                self.add_to_map(out_fc, messages)

    def process_fc(self, key, fc, clip_fc, out_ws, geoextent, messages):
        base = os.path.basename(fc)
        name_no_ext = os.path.splitext(base)[0]

        tokens = name_no_ext.split("_")
        tokens[0] = geoextent  # user-defined prefix
        new_name = "_".join(tokens)

        out_path = os.path.join(out_ws, new_name)

        messages.addMessage(f"Clipping {base} → {new_name}")

        # Clip
        arcpy.analysis.Clip(
            in_features=fc,
            clip_features=clip_fc,
            out_feature_class=out_path
        )

        # Dissolve phys layer
        if key == "phys":
            messages.addMessage(f"Dissolving {new_name} into a single feature…")
            dissolved = out_path + "_dissolved"

            arcpy.management.Dissolve(
                in_features=out_path,
                out_feature_class=dissolved,
                dissolve_field=[],
                multi_part="SINGLE_PART"
            )

            arcpy.management.Delete(out_path)
            arcpy.management.Rename(dissolved, out_path)

            messages.addMessage(f"Dissolve complete → {out_path}")

        messages.addMessage(f"Saved: {out_path}")
        return out_path

    def add_to_map(self, fc_path, messages):
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        m = aprx.activeMap

        if m is None:
            messages.addWarningMessage("No active map found — cannot add output.")
            return

        m.addDataFromPath(fc_path)
        messages.addMessage(f"Added to map: {fc_path}")