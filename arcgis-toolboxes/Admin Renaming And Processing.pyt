# -*- coding: utf-8 -*-
import arcpy
import os

# ---------------------------------------------------------------------------
# TOOLBOX
# ---------------------------------------------------------------------------

class Toolbox(object):
    def __init__(self):
        self.label = "Admin Renaming And Processing Tools"
        self.alias = "adminrename"
        self.tools = [
            AdminGeometryProcessor
        ]


# ---------------------------------------------------------------------------
# MAIN TOOL: POLYGON + LINE + POINT SUPPORT
# ---------------------------------------------------------------------------

class AdminGeometryProcessor(object):
    def __init__(self):
        self.label = "Admin Renaming + Processing"
        self.description = (
            "Renames polygon, line, and point admin datasets using the naming convention:\n"
            "geoextent_admn_adlevel_geom_s0_source_pp<realname>\n\n"
            "If the input is a polygon, the tool can also generate:\n"
            "• Boundary lines (PolygonToLine) with LEFT_FID = -1 removed\n"
            "• Centroid points (FeatureToPoint, INSIDE)\n\n"
            "Lines and points are renamed only. Polygons may produce full derivatives."
        )
        self.canRunInBackground = False

    # -----------------------------------------------------------------------
    # PARAMETERS
    # -----------------------------------------------------------------------

    def getParameterInfo(self):
        params = []

        # 1. Value table: dataset | admin level | real name
        p_table = arcpy.Parameter(
            displayName="Input Datasets",
            name="rename_table",
            datatype="GPValueTable",
            parameterType="Optional",   # "Required" triggers strict row-level ValueList
                                        # validation (Error 000800) when rows are added
                                        # via TOC drag-and-drop. "Optional" keeps the
                                        # dropdown but skips that validation pass.
                                        # Required behaviour is enforced in updateMessages.
            direction="Input"
        )

        p_table.columns = [
            ["DEFeatureClass", "Dataset"],
            ["GPString", "Admin Level"],
            ["GPString", "Real Name"]
        ]

        # ValueList filter preserved — dropdown still appears in the UI
        p_table.filters[1].type = "ValueList"
        p_table.filters[1].list = [
            "Admin level 0",
            "Admin level 1",
            "Admin level 2",
            "Admin level 3",
            "Admin level 4",
            "Admin level 5",
            "All levels",
            "Regional",
            "Unknown"
        ]

        p_table.description = (
            "Provide one row per dataset. Polygons may generate lines and points. "
            "Lines and points will only be renamed."
        )
        params.append(p_table)

        # 2. Geoextent
        p_geoextent = arcpy.Parameter(
            displayName="Geoextent (shared)",
            name="geoextent",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
        params.append(p_geoextent)

        # 3. Source
        p_source = arcpy.Parameter(
            displayName="Source (shared)",
            name="source",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
        params.append(p_source)

        # 4. Output location
        p_out = arcpy.Parameter(
            displayName="Output Location (Folder or Geodatabase)",
            name="out_location",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input"
        )
        params.append(p_out)

        # 5. Generate lines?
        p_gen_lines = arcpy.Parameter(
            displayName="Generate Boundary Lines (Polygon Only)",
            name="generate_lines",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_gen_lines.value = False
        params.append(p_gen_lines)

        # 6. Generate points?
        p_gen_points = arcpy.Parameter(
            displayName="Generate Centroid Points (Polygon Only)",
            name="generate_points",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_gen_points.value = False
        params.append(p_gen_points)

        # 7. Add to map?
        p_addmap = arcpy.Parameter(
            displayName="Add Outputs to Map",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_addmap.value = True
        params.append(p_addmap)

        # 8. Preview table
        p_preview = arcpy.Parameter(
            displayName="Preview Table",
            name="preview",
            datatype="GPString",
            parameterType="Derived",
            direction="Output"
        )
        params.append(p_preview)

        return params

    # -----------------------------------------------------------------------
    # CONSTANTS
    # -----------------------------------------------------------------------

    ADMIN_MAP = {
        "Admin level 0": "ad0",
        "Admin level 1": "ad1",
        "Admin level 2": "ad2",
        "Admin level 3": "ad3",
        "Admin level 4": "ad4",
        "Admin level 5": "ad5",
        "All levels": "ad",
        "Regional": "reg",
        "Unknown": "ukn"
    }

    GEOM_MAP = {
        "polygon": "py",
        "polyline": "ln",
        "line": "ln",
        "point": "pt"
    }

    # -----------------------------------------------------------------------
    # LAYER RESOLVER
    # -----------------------------------------------------------------------

    def resolve_path(self, layer_or_path):
        """
        When a layer is dragged from the TOC, the value table stores only the
        layer's display name (e.g. 'pse_admin0'), not a file path.
        arcpy.Describe().catalogPath resolves any layer name or path to the
        true on-disk location that geoprocessing tools can consume.
        """
        try:
            return arcpy.Describe(layer_or_path).catalogPath
        except Exception:
            return layer_or_path

    # -----------------------------------------------------------------------
    # NAME BUILDER
    # -----------------------------------------------------------------------

    def build_name(self, geoextent, adlevel, geom_code, source, realname):
        """
        Applies final naming rules:
        - If admin level = All levels → realname = alladminlevels
        - If realname empty → final name ends with _pp
        """
        if adlevel == "ad":
            realname = "alladminlevels"

        base = f"{geoextent}_admn_{adlevel}_{geom_code}_s0_{source}_pp"

        if not realname:
            return base

        return f"{base}_{realname}"

    # -----------------------------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------------------------

    def updateMessages(self, params):
        """Re-enforce Required and validate Admin Level values."""
        table = params[0].values

        # Re-enforce Required (since parameterType is Optional to avoid 000800)
        if not table:
            params[0].setErrorMessage("Input Datasets is required. Add at least one row.")
            return
        else:
            params[0].clearMessage()

        # Warn on any unrecognised Admin Level value
        valid_lower = {k.lower() for k in self.ADMIN_MAP}
        bad_rows = []
        for i, row in enumerate(table):
            try:
                level = (row[1] or "").strip()
                if level and level.lower() not in valid_lower:
                    bad_rows.append(f"row {i + 1} ('{level}')")
            except Exception:
                pass

        if bad_rows:
            params[0].setWarningMessage(
                "Unrecognised Admin Level in " + ", ".join(bad_rows) + ". "
                "Valid values: " + " | ".join(self.ADMIN_MAP.keys())
            )

    # -----------------------------------------------------------------------
    # PREVIEW
    # -----------------------------------------------------------------------

    def updateParameters(self, params):
        table = params[0].values
        geoextent = params[1].valueAsText
        source = params[2].valueAsText
        gen_lines = params[4].value
        gen_points = params[5].value

        if not (table and geoextent and source):
            return

        rows = []
        rows.append("INPUT | GEOM | ADLEVEL | REALNAME | OUTPUTS")
        rows.append("-" * 140)

        for row in table:
            try:
                in_fc = self.resolve_path(row[0])   # resolve TOC name → catalogPath
                adlevel_label = row[1]
                realname = row[2]

                geom = arcpy.Describe(in_fc).shapeType.lower()
                geom_code = self.GEOM_MAP.get(geom, "xx")
                adlevel = self.ADMIN_MAP.get(adlevel_label, "ukn")

                base_name = self.build_name(geoextent, adlevel, geom_code, source, realname)

                outputs = [base_name]

                if geom == "polygon":
                    if gen_lines:
                        outputs.append(base_name.replace("_py_", "_ln_"))
                    if gen_points:
                        outputs.append(base_name.replace("_py_", "_pt_"))

                rows.append(
                    f"{os.path.basename(in_fc)} | {geom_code} | {adlevel} | {realname} | "
                    + ", ".join(outputs)
                )

            except:
                rows.append("ERROR PROCESSING ROW")

        params[7].value = "\n".join(rows)

    # -----------------------------------------------------------------------
    # EXECUTION
    # -----------------------------------------------------------------------

    def execute(self, params, messages):
        table = params[0].values
        geoextent = params[1].valueAsText
        source = params[2].valueAsText
        out_location = params[3].valueAsText
        gen_lines = params[4].value
        gen_points = params[5].value
        add_to_map = params[6].value

        desc = arcpy.Describe(out_location)
        is_folder = desc.workspaceType == "FileSystem"

        aprx = arcpy.mp.ArcGISProject("CURRENT") if add_to_map else None
        m = aprx.activeMap if add_to_map else None

        def out(name):
            return os.path.join(out_location, name + (".shp" if is_folder else ""))

        for row in table:
            in_fc = self.resolve_path(row[0])   # resolve TOC name → catalogPath
            adlevel_label = row[1]
            realname = row[2]

            geom = arcpy.Describe(in_fc).shapeType.lower()
            geom_code = self.GEOM_MAP.get(geom, "xx")
            adlevel = self.ADMIN_MAP.get(adlevel_label, "ukn")

            base_name = self.build_name(geoextent, adlevel, geom_code, source, realname)

            renamed_out = out(base_name)
            arcpy.management.CopyFeatures(in_fc, renamed_out)
            messages.addMessage(f"Created: {renamed_out}")

            if add_to_map:
                m.addDataFromPath(renamed_out)

            if geom == "polygon":

                if gen_lines:
                    line_name = base_name.replace("_py_", "_ln_")
                    line_out = out(line_name)

                    arcpy.management.PolygonToLine(renamed_out, line_out)
                    messages.addMessage(f"Created lines: {line_out}")

                    arcpy.management.MakeFeatureLayer(line_out, "tmp_lines")
                    arcpy.management.SelectLayerByAttribute("tmp_lines", "NEW_SELECTION", "LEFT_FID = -1")
                    arcpy.management.DeleteFeatures("tmp_lines")
                    messages.addMessage("Removed LEFT_FID = -1 lines")

                    if add_to_map:
                        m.addDataFromPath(line_out)

                if gen_points:
                    point_name = base_name.replace("_py_", "_pt_")
                    point_out = out(point_name)

                    arcpy.management.FeatureToPoint(renamed_out, point_out, "INSIDE")
                    messages.addMessage(f"Created points: {point_out}")

                    if add_to_map:
                        m.addDataFromPath(point_out)

        if add_to_map:
            messages.addMessage("All outputs added to map.")

    # -----------------------------------------------------------------------
    # HELP
    # -----------------------------------------------------------------------

    def getHelp(self):
        return (
            "This tool renames polygon, line, and point admin datasets using your "
            "standard naming convention.\n\n"
            "Polygons may also generate:\n"
            "• Boundary lines (LEFT_FID = -1 removed)\n"
            "• Centroid points (INSIDE)\n\n"
            "Lines and points are renamed only.\n\n"
            "Naming rules:\n"
            "• If real name is empty → final name ends with _pp\n"
            "• If admin level = All levels → real name = alladminlevels\n"
            "• Geometry code is based on actual geometry (py, ln, pt)\n"
        )
