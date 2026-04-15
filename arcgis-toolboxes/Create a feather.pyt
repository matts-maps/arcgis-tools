# -*- coding: utf-8 -*-
import arcpy
import os


# ---------------------------------------------------------------------------
# Toolbox Definition
# ---------------------------------------------------------------------------
class Toolbox(object):
    def __init__(self):
        self.label = "Create a feather"
        self.alias = "vignette"
        self.tools = [CreateVignette]


# ---------------------------------------------------------------------------
# Create Vignette Tool
# ---------------------------------------------------------------------------
class CreateVignette(object):
    def __init__(self):
        self.label = "Create Vignette Feathering"
        self.description = (
            "Creates a vignette-style feathering effect around a polygon using "
            "multiple buffers, a global universe polygon, and a transparency field. "
            "Geometry is automatically repaired and sanitized before processing."
        )
        self.canRunInBackground = True

    # ----------------------------------------------------------------------
    # Parameters
    # ----------------------------------------------------------------------
    def getParameterInfo(self):
        params = []

        # 0 — Figure polygon
        p_in_fc = arcpy.Parameter(
            displayName="Figure polygon (feature class or layer)",
            name="in_figure_fc",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )
        p_in_fc.filter.list = ["Polygon"]

        # 1 — Geoextent
        p_geoextent = arcpy.Parameter(
            displayName="Geoextent name",
            name="geoextent",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )

        # 2 — Datasource
        p_datasource = arcpy.Parameter(
            displayName="Datasource name",
            name="datasource",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )

        # 3 — Number of rings
        p_num_rings = arcpy.Parameter(
            displayName="Number of buffer rings",
            name="num_rings",
            datatype="GPLong",
            parameterType="Required",
            direction="Input"
        )
        p_num_rings.value = 15

        # 4 — Distance between rings
        p_ring_dist = arcpy.Parameter(
            displayName="Distance between rings",
            name="ring_distance",
            datatype="GPDouble",
            parameterType="Required",
            direction="Input"
        )
        p_ring_dist.value = 10.0

        # 5 — Distance units
        p_units = arcpy.Parameter(
            displayName="Distance units",
            name="distance_units",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )
        p_units.filter.type = "ValueList"
        p_units.filter.list = ["Meters", "Kilometers", "Feet", "Miles"]
        p_units.value = "Kilometers"

        # 6 — Output workspace
        p_out_ws = arcpy.Parameter(
            displayName="Output workspace (folder or geodatabase)",
            name="out_workspace",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input"
        )

        return [
            p_in_fc,
            p_geoextent,
            p_datasource,
            p_num_rings,
            p_ring_dist,
            p_units,
            p_out_ws
        ]

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        return

    def updateMessages(self, parameters):
        return

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    def _unit_suffix(self, units):
        if units == "Meters":
            return "m"
        if units == "Kilometers":
            return "k"
        return "u"

    def _safe_name(self, s):
        return s.replace(" ", "_")

    # ----------------------------------------------------------------------
    # Execute
    # ----------------------------------------------------------------------
    def execute(self, parameters, messages):
        arcpy.env.overwriteOutput = True

        # Inputs
        in_fc = parameters[0].valueAsText
        geoextent = parameters[1].valueAsText.strip()
        datasource = parameters[2].valueAsText.strip()
        num_rings = int(parameters[3].value)
        ring_dist = float(parameters[4].value)
        units = parameters[5].value
        out_ws = parameters[6].valueAsText

        messages.addMessage(f"Figure polygon: {in_fc}")
        messages.addMessage(f"Geoextent: {geoextent}")
        messages.addMessage(f"Datasource: {datasource}")
        messages.addMessage(f"Rings: {num_rings}, distance between rings: {ring_dist} {units}")

        # ------------------------------------------------------------------
        # Resolve layer → temp FC
        # ------------------------------------------------------------------
        desc = arcpy.Describe(in_fc)
        if desc.dataType == "FeatureLayer":
            messages.addMessage("Copying layer to temporary feature class...")
            in_fc = arcpy.CopyFeatures_management(
                in_fc,
                os.path.join(arcpy.env.scratchGDB, "_figure_temp")
            ).getOutput(0)

        scratch = arcpy.env.scratchGDB

        # ------------------------------------------------------------------
        # Geometry Repair Pipeline
        # ------------------------------------------------------------------
        messages.addMessage("Repairing geometry...")
        arcpy.management.RepairGeometry(in_fc, "DELETE_NULL")

        messages.addMessage("Converting multipart polygons to singlepart...")
        single_fc = os.path.join(scratch, "figure_single")
        arcpy.management.MultipartToSinglepart(in_fc, single_fc)

        messages.addMessage("Eliminating tiny polygon parts...")
        elim_fc = os.path.join(scratch, "figure_elim")
        arcpy.management.EliminatePolygonPart(
            in_features=single_fc,
            out_feature_class=elim_fc,
            condition="AREA",
            part_area="0 SquareMeters",
            part_area_percent="",
            part_option="ANY"
        )

        messages.addMessage("Removing empty or zero-area geometries...")
        nonempty_fc = os.path.join(scratch, "figure_nonempty")
        # Use Shape_Area if present; otherwise fall back to NOT Shape IS NULL
        has_area = any(f.name.lower() == "shape_area" for f in arcpy.ListFields(elim_fc))
        if has_area:
            where_clause = "NOT Shape IS NULL AND Shape_Area > 0"
        else:
            where_clause = "NOT Shape IS NULL"
        arcpy.management.MakeFeatureLayer(elim_fc, "elim_lyr", where_clause)
        arcpy.management.CopyFeatures("elim_lyr", nonempty_fc)

        messages.addMessage("Fixing topology using Buffer(0)...")
        fixed_fc = os.path.join(scratch, "figure_fixed")
        arcpy.analysis.Buffer(
            in_features=nonempty_fc,
            out_feature_class=fixed_fc,
            buffer_distance_or_field="0 Meters",
            line_side="FULL",
            line_end_type="ROUND",
            dissolve_option="NONE"
        )

        # ------------------------------------------------------------------
        # Multiple Ring Buffer
        # ------------------------------------------------------------------
        distances = ["{} {}".format(ring_dist * i, units) for i in range(1, num_rings + 1)]
        buf_fc = os.path.join(scratch, "vignette_buffers")

        messages.addMessage("Creating multiple ring buffers...")
        arcpy.MultipleRingBuffer_analysis(
            fixed_fc,
            buf_fc,
            distances,
            units,
            "FromBufDst",
            "ALL",
            "OUTSIDE_ONLY"
        )

        # ------------------------------------------------------------------
        # Global Universe Polygon
        # ------------------------------------------------------------------
        messages.addMessage("Creating global universe polygon...")

        wgs84 = arcpy.SpatialReference(4326)
        global_arr = arcpy.Array([
            arcpy.Point(-180, -90),
            arcpy.Point(-180,  90),
            arcpy.Point( 180,  90),
            arcpy.Point( 180, -90),
            arcpy.Point(-180, -90)
        ])
        global_poly = arcpy.Polygon(global_arr, wgs84)

        fig_sr = arcpy.Describe(in_fc).spatialReference
        universe_fc = os.path.join(scratch, "vignette_universe")
        arcpy.Project_management(global_poly, universe_fc, fig_sr)

        # ------------------------------------------------------------------
        # Union
        # ------------------------------------------------------------------
        messages.addMessage("Unioning buffers with global universe polygon...")
        union_fc = os.path.join(scratch, "vignette_union")
        arcpy.Union_analysis([buf_fc, universe_fc], union_fc, "ALL", "#", "NO_GAPS")

        # ------------------------------------------------------------------
        # Erase inner figure
        # ------------------------------------------------------------------
        messages.addMessage("Erasing inner figure polygon...")
        erase_fc = os.path.join(scratch, "vignette_erase")
        arcpy.Erase_analysis(union_fc, in_fc, erase_fc)

        # ------------------------------------------------------------------
        # Add Xpar
        # ------------------------------------------------------------------
        messages.addMessage("Adding and calculating transparency field (Xpar)...")
        if "Xpar" not in [f.name for f in arcpy.ListFields(erase_fc)]:
            arcpy.AddField_management(erase_fc, "Xpar", "LONG")

        # Find distance field
        dist_field = None
        for f in arcpy.ListFields(erase_fc):
            if f.name.lower() == "frombufdst":
                dist_field = f.name
                break

        if not dist_field:
            raise arcpy.ExecuteError("Expected field 'FromBufDst' not found.")

        # Max distance
        max_dist = 0.0
        with arcpy.da.SearchCursor(erase_fc, [dist_field]) as scur:
            for (d,) in scur:
                if d is not None and d > max_dist:
                    max_dist = d

        if max_dist == 0:
            raise arcpy.ExecuteError("Maximum buffer distance is zero.")

        # Xpar logic
        with arcpy.da.UpdateCursor(
            erase_fc,
            ["FID_vignette_buffers", dist_field, "Xpar"]
        ) as ucur:
            for fid_buf, d, x in ucur:
                if fid_buf == -1:
                    ucur.updateRow([fid_buf, d, 100])
                else:
                    xpar = int(round((100.0 * float(d)) / float(max_dist)))
                    ucur.updateRow([fid_buf, d, xpar])

        # ------------------------------------------------------------------
        # Build output name
        # ------------------------------------------------------------------
        total_distance = num_rings * ring_dist
        unit_suffix = self._unit_suffix(units)
        distance_str = f"{int(total_distance)}{unit_suffix}"

        out_name = (
            f"{self._safe_name(geoextent)}_cart_fea_py_s0_"
            f"{self._safe_name(datasource)}_pp_{distance_str}"
        )
        out_fc = os.path.join(out_ws, out_name)

        messages.addMessage(f"Output name: {out_name}")
        messages.addMessage("Saving final vignette feature class...")
        arcpy.CopyFeatures_management(erase_fc, out_fc)

        # ------------------------------------------------------------------
        # Add to active map
        # ------------------------------------------------------------------
        messages.addMessage("Adding output to the active map...")
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        active_map = aprx.activeMap
        if active_map:
            active_map.addDataFromPath(out_fc)
            messages.addMessage("Output added to the active map.")
        else:
            messages.addWarningMessage("No active map found — output not added.")

        messages.addMessage("Done. Symbolize with a single fill and drive transparency from Xpar.")