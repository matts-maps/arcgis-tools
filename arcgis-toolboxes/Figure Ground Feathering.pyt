# -*- coding: utf-8 -*-
# FigureGroundFeathering.pyt
# ArcGIS Pro Python Toolbox
#
# Implements the figure-ground feathering technique exactly as described by
# Aileen Buckley, Esri Mapping Center:
# https://www.esri.com/arcgis-blog/products/arcgis/mapping/figure-ground-feathering
#
# Steps:
#   1. Build global background polygon (180W–180E, 90S–90N)
#   2. Multiple Ring Buffer — outside only, dissolved between barriers
#   3. Union of buffers with global background -> Temp
#   4. Erase the original figure polygon from Temp -> FeatheringEffect
#   5. Add field Xpar (Long Integer); calculate (100 * !FromBufDst!) / max_dist
#      The universe polygon row (FromBufDst = NULL / 0) is set to Xpar = 100
#
# Usage:
#   Catalog pane > Toolboxes > Add Toolbox > select this .pyt file

import arcpy
import os


def _to_metres(value, unit):
    """Convert a distance value to metres for abbreviation purposes."""
    factors = {
        "Meters": 1,
        "Kilometers": 1000,
        "Feet": 0.3048,
        "Miles": 1609.344,
        "NauticalMiles": 1852,
        "Yards": 0.9144,
    }
    return value * factors.get(unit, 1)


def _distance_abbrev(metres):
    """
    Produce a compact distance label.
    Exact multiples of 1000 m use 'k' suffix (e.g. 2000 -> '2k').
    Otherwise express in metres as an integer (e.g. 200 -> '200m').
    """
    if metres >= 1000 and metres % 1000 == 0:
        return f"{int(metres // 1000)}k"
    return f"{int(round(metres))}m"


class Toolbox:
    def __init__(self):
        self.label = "Figure-Ground Feathering"
        self.alias = "FigureGroundFeathering"
        self.tools = [FigureGroundFeather]


class FigureGroundFeather:
    def __init__(self):
        self.label = "Figure-Ground Feather"
        self.description = (
            "Creates a figure-ground feathering (vignette) effect.\n\n"
            "Follows the method by Aileen Buckley, Esri Mapping Center:\n"
            "https://www.esri.com/arcgis-blog/products/arcgis/mapping/figure-ground-feathering\n\n"
            "Steps:\n"
            "  1. Multiple Ring Buffer (outside only, dissolved between barriers)\n"
            "  2. Union of buffers with global_background -> Temp\n"
            "  3. Erase figure polygon from Temp -> FeatheringEffect\n"
            "  4. Add Xpar field (Long Integer); calculate (100 * FromBufDst) / max_dist\n"
            "     Universe polygon row set to Xpar = 100"
        )
        self.canRunInBackground = False

    def getParameterInfo(self):

        # Figure polygon — the area of interest
        p0 = arcpy.Parameter(
            displayName="Figure Polygon",
            name="figure_polygon",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input",
        )
        p0.filter.list = ["Polygon"]

        # Number of buffer rings (10–20 recommended per the article)
        p1 = arcpy.Parameter(
            displayName="Number of Rings",
            name="num_rings",
            datatype="GPLong",
            parameterType="Required",
            direction="Input",
        )
        p1.value = 15
        p1.filter.type = "Range"
        p1.filter.list = [1, 100]

        # Distance between rings
        p2 = arcpy.Parameter(
            displayName="Distance Between Rings",
            name="ring_width",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input",
        )
        p2.value = 1000.0

        # Distance unit
        p3 = arcpy.Parameter(
            displayName="Distance Unit",
            name="distance_unit",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        p3.filter.type = "ValueList"
        p3.filter.list = [
            "Meters", "Kilometers", "Feet", "Miles", "NauticalMiles", "Yards"
        ]
        p3.value = "Meters"

        # Geographic extent code (e.g. 'sin' for Singapore)
        p4 = arcpy.Parameter(
            displayName="Geographic Extent Code",
            name="geo_extent",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )

        # Data source code (e.g. 'gadm')
        p5 = arcpy.Parameter(
            displayName="Data Source Code",
            name="datasource",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )

        # Output geodatabase — filename is auto-generated
        p6 = arcpy.Parameter(
            displayName="Output Geodatabase",
            name="out_gdb",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input",
        )
        p6.filter.list = ["Local Database", "Remote Database"]

        # Output feature class (derived, auto-named)
        p7 = arcpy.Parameter(
            displayName="Output Feature Class",
            name="out_feathering_effect",
            datatype="DEFeatureClass",
            parameterType="Derived",
            direction="Output",
        )

        return [p0, p1, p2, p3, p4, p5, p6, p7]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        figure_polygon = parameters[0].valueAsText
        num_rings      = int(parameters[1].value)
        ring_width     = float(parameters[2].value)
        distance_unit  = parameters[3].valueAsText
        geo_extent     = parameters[4].valueAsText.strip().lower()
        datasource     = parameters[5].valueAsText.strip().lower()
        out_gdb        = parameters[6].valueAsText

        # Build output filename:
        # {geo_extent}_cart_fea_py_s0_{datasource}_pp_feather{distance_abbrev}
        # Distance abbreviation: multiples of 1000 use 'k' (e.g. 2000m -> 2k),
        # otherwise use the value + unit initial (e.g. 200m -> 200m, 0.5km -> 500m)
        total_metres = _to_metres(ring_width * num_rings, distance_unit)
        dist_abbrev  = _distance_abbrev(total_metres)
        fc_name = (
            f"{geo_extent}_cart_fea_py_s0_{datasource}_pp_feather{dist_abbrev}"
        )
        out_fc = os.path.join(out_gdb, fc_name)
        messages.addMessage(f"Output filename: {fc_name}")
        parameters[7].value = out_fc

        arcpy.env.overwriteOutput = True
        scratch = arcpy.env.scratchGDB

        temp_buffer     = os.path.join(scratch, "tmp_buffer")
        temp_background = os.path.join(scratch, "tmp_global_background")
        temp_union      = os.path.join(scratch, "Temp")

        # Build the global background polygon (world extent: 180W–180E, 90S–90N)
        # using the same spatial reference as the figure polygon so the Union
        # and Erase operations work without projection mismatches.
        messages.addMessage("Building global background polygon (180W–180E, 90S–90N)...")
        sr = arcpy.Describe(figure_polygon).spatialReference
        world_coords = arcpy.Array([
            arcpy.Point(-180, -90),
            arcpy.Point(-180,  90),
            arcpy.Point( 180,  90),
            arcpy.Point( 180, -90),
            arcpy.Point(-180, -90),
        ])
        world_polygon = arcpy.Polygon(world_coords, arcpy.SpatialReference(4326))
        arcpy.management.CopyFeatures([world_polygon], temp_background)
        # Re-project to match the figure polygon's spatial reference if needed
        if sr.factoryCode != 4326 and sr.factoryCode != 0:
            temp_background_proj = os.path.join(scratch, "tmp_global_background_proj")
            arcpy.management.Project(temp_background, temp_background_proj, sr)
            arcpy.management.Delete(temp_background)
            temp_background = temp_background_proj
        global_background = temp_background
        messages.addMessage(f"  Done: {global_background}")

        # ── Step 1: Multiple Ring Buffer ────────────────────────────
        # Outside only; dissolved between barriers
        # Field name FromBufDst is the default produced by Buffer Wizard /
        # Multiple Ring Buffer when Field_Name is set to "FromBufDst"
        messages.addMessage("Step 1: Multiple Ring Buffer...")

        distances = [round(ring_width * (i + 1), 4) for i in range(num_rings)]
        messages.addMessage(
            f"  {num_rings} rings, {ring_width} {distance_unit} apart "
            f"(outermost ring at {distances[-1]} {distance_unit})"
        )

        arcpy.analysis.MultipleRingBuffer(
            Input_Features=figure_polygon,
            Output_Feature_class=temp_buffer,
            Distances=distances,
            Buffer_Unit=distance_unit,
            Field_Name="FromBufDst",
            Dissolve_Option="ALL",          # dissolve buffers between barriers
            Outside_Polygons_Only="OUTSIDE_ONLY",
            Method="PLANAR",
        )
        messages.addMessage(f"  Done: {temp_buffer}")

        # ── Step 2: Union buffers + global_background -> Temp ───────
        messages.addMessage("Step 2: Union (buffers + global background) -> Temp...")

        arcpy.analysis.Union(
            in_features=[temp_buffer, global_background],
            out_feature_class=temp_union,
            join_attributes="ALL",
            gaps="NO_GAPS",
        )
        messages.addMessage(f"  Done: {temp_union}")

        # ── Step 3: Erase figure polygon from Temp -> FeatheringEffect
        messages.addMessage("Step 3: Erase figure polygon from Temp -> FeatheringEffect...")

        arcpy.analysis.Erase(
            in_features=temp_union,
            erase_features=figure_polygon,
            out_feature_class=out_fc,
        )
        messages.addMessage(f"  Done: {out_fc}")

        # ── Step 4: Add and calculate Xpar (Long Integer) ───────────
        # Formula from the article: (100 * [FromBufDst]) / max(FromBufDst)
        # Universe polygon row (FromBufDst NULL or 0) -> Xpar = 0
        messages.addMessage("Step 4: Adding and calculating Xpar field...")

        # Stop any active edit session before schema edits.
        # ArcGIS Pro raises ERROR 000496 ("Table is being edited") if an edit
        # session is open on the workspace when AddField is called.
        try:
            edit = arcpy.da.Editor(os.path.dirname(out_fc))
            if edit.isEditing:
                edit.stopEditing(save_changes=True)
        except Exception:
            pass  # No edit session active — safe to continue

        arcpy.management.AddField(out_fc, "Xpar", "LONG")

        # Find the FromBufDst field (may be renamed by Union to FromBufDst_1 etc.)
        dist_field = None
        for f in arcpy.ListFields(out_fc):
            if f.name.lower().startswith("frombufdst"):
                dist_field = f.name
                break

        if dist_field is None:
            arcpy.management.CalculateField(out_fc, "Xpar", "0", "PYTHON3")
            messages.addWarning(
                "  'FromBufDst' field not found in output. Xpar set to 0. "
                "Recalculate manually: (100 * !FromBufDst!) / <max_value>"
            )
        else:
            max_dist = distances[-1]
            messages.addMessage(
                f"  Using field '{dist_field}', max distance = {max_dist} {distance_unit}"
            )
            messages.addMessage(
                f"  Formula: (100 * !{dist_field}!) / {max_dist}"
            )

            with arcpy.da.UpdateCursor(out_fc, [dist_field, "Xpar"]) as cursor:
                for row in cursor:
                    d = row[0]
                    if d is None or d <= 0:
                        # Universe polygon — set Xpar = 100 (fully transparent)
                        row[1] = 100
                    else:
                        row[1] = int(round((100 * d) / max_dist))
                    cursor.updateRow(row)

            messages.addMessage("  Xpar calculated.")

        # ── Cleanup ─────────────────────────────────────────────────
        for tmp in [temp_buffer, temp_background, temp_union]:
            if arcpy.Exists(tmp):
                arcpy.management.Delete(tmp)

        messages.addMessage("\nComplete.")
        messages.addMessage(f"Output: {out_fc}")
        messages.addMessage(
            "To finish: add FeatheringEffect to your map above all other layers, "
            "set fill to White, outline to No Color, and vary transparency "
            "by the Xpar field (Symbology > Vary by Attribute > Transparency)."
        )

    def postExecute(self, parameters):
        return
