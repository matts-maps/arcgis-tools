# -*- coding: utf-8 -*-
import arcpy
import os
from collections import defaultdict

class Toolbox(object):
    def __init__(self):
        self.label = "Geofabrik Tools"
        self.alias = "geofabrik_tools"

        self.description = (
            "Tools for preparing and standardizing Geofabrik OSM extracts.\n\n"
            "Includes:\n"
            "- Renaming files\n"
            "- Merging and renaming\n"
            "- Clipping to an area of interest and renaming the files\n"
            "- Merging files, then clipping to an area of interest and renaming the files.\n\n"
        )

        self.tools = [
            RenameGeofabrik,
            MergeRenameGeofabrik,
            ClipRenameGeofabrik,
            MergeClipRenameGeofabrik
        ]


# ---------------------------------------------------------
# HARD-CODED TEMPLATE MAP
# ---------------------------------------------------------
TEMPLATE_MAP = {
    "gis_osm_buildings_a_free_1": "{geoextent}_bldg_bld_py_s0_openstreetmap_pp_buildings",
    "gis_osm_landuse_a_free_1": "{geoextent}_land_lnd_py_s0_openstreetmap_pp_landuse",
    "gis_osm_natural_a_free_1": "{geoextent}_phys_nat_py_s0_openstreetmap_pp_natural",
    "gis_osm_natural_free_1": "{geoextent}_phys_nat_pt_s0_openstreetmap_pp_natural",
    "gis_osm_places_a_free_1": "{geoextent}_stle_stl_py_s0_openstreetmap_pp_settlements",
    "gis_osm_places_free_1": "{geoextent}_stle_stl_pt_s0_openstreetmap_pp_settlements",
    "gis_osm_pofw_a_free_1": "{geoextent}_pois_rel_py_s0_openstreetmap_pp_placeofworship",
    "gis_osm_pofw_free_1": "{geoextent}_pois_rel_pt_s0_openstreetmap_pp_placeofworship",
    "gis_osm_pois_a_free_1": "{geoextent}_pois_poi_py_s0_openstreetmap_pp_pointsofinterest",
    "gis_osm_pois_free_1": "{geoextent}_pois_poi_pt_s0_openstreetmap_pp_pointsofinterest",
    "gis_osm_railways_free_1": "{geoextent}_tran_rrd_ln_s0_openstreetmap_pp_railways",
    "gis_osm_roads_free_1": "{geoextent}_tran_rds_ln_s0_openstreetmap_pp_roads",
    "gis_osm_traffic_a_free_1": "{geoextent}_tran_trf_py_s0_openstreetmap_pp_traffic",
    "gis_osm_traffic_free_1": "{geoextent}_tran_trf_pt_s0_openstreetmap_pp_traffic",
    "gis_osm_transport_a_free_1": "{geoextent}_tran_trn_py_s0_openstreetmap_pp_transport",
    "gis_osm_transport_free_1": "{geoextent}_tran_trn_pt_s0_openstreetmap_pp_transport",
    "gis_osm_adminareas_a_free_1": "{geoextent}_admn_ad_py_s0_openstreetmap_pp_adminareas",
    "gis_osm_protected_areas_a_free_1": "{geoextent}_land_npk_py_openstreetmap_pp_protectedareas",
    "gis_osm_water_a_free_1": "{geoextent}_phys_wat_py_s0_openstreetmap_pp_waterbodies",
    "gis_osm_waterways_free_1": "{geoextent}_phys_riv_ln_s0_openstreetmap_pp_rivers"
}

def resolve_new_name(base, geoextent, full_name=None):
    """
    Return the correct output name for a dataset.

    1. Raw Geofabrik name (e.g. gis_osm_water_a_free_1):
       Look up in TEMPLATE_MAP and substitute the geoextent.
    2. Already in MapAction convention (e.g. nzl_phys_wat_py_s0_openstreetmap_pp_waterbodies):
       The first underscore-delimited token is the geoextent — replace it.
       full_name (from catalogPath) is checked first to avoid shapefile 13-char truncation.
    3. Unrecognised name: return unchanged.
    """
    # Case 1 - raw Geofabrik name
    if base in TEMPLATE_MAP:
        return TEMPLATE_MAP[base].format(geoextent=geoextent)

    # Case 2 - already in MapAction convention.
    # Use full_name (disk path stem) in preference to base, which may be
    # truncated to 13 chars for shapefiles.
    name_to_check = full_name if (full_name and full_name != base) else base
    parts = name_to_check.split("_", 1)
    if len(parts) == 2:
        # Validate it looks like a MapAction name by checking the remainder
        # contains the openstreetmap marker present in all template values
        if "openstreetmap" in parts[1]:
            arcpy.AddMessage(
                "Existing convention detected: '{}' -> '{}'".format(
                    name_to_check, geoextent + "_" + parts[1])
            )
            return geoextent + "_" + parts[1]

    # Case 3 - unknown, leave as-is
    arcpy.AddMessage("No convention match for '{}' - name unchanged".format(name_to_check))
    return base


# ---------------------------------------------------------
# SHARED HELPER FUNCTIONS
# ---------------------------------------------------------
def copy_to_destination(src, dest_ws, new_name):
    desc = arcpy.Describe(src)
    dest_path = os.path.join(dest_ws, new_name)

    if desc.dataType in ["FeatureClass", "ShapeFile"]:
        if dest_ws.lower().endswith(".gdb"):
            arcpy.management.CopyFeatures(src, dest_path)
        else:
            dest_path = dest_path + ".shp"
            arcpy.management.CopyFeatures(src, dest_path)

    elif desc.dataType == "RasterDataset":
        arcpy.management.CopyRaster(src, dest_path)

    elif desc.dataType == "Table":
        arcpy.management.CopyRows(src, dest_path)

    return dest_path


def add_path_to_map(path):
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        m = aprx.activeMap
        if m:
            m.addDataFromPath(path)
        else:
            arcpy.AddWarning("No active map found to add output layers.")
    except Exception as e:
        arcpy.AddWarning(f"Could not add {path} to map: {e}")


def build_field_mapping(target_fc, join_fc, selected_join_fields):
    """
    Build a FieldMappings object for SpatialJoin.
    All target fields are kept. From the join layer, only the fields in
    selected_join_fields are included (or all non-system fields if none selected).
    """
    fm = arcpy.FieldMappings()
    fm.addTable(target_fc)

    join_field_names = [
        f.name for f in arcpy.ListFields(join_fc)
        if f.type not in ("OID", "Geometry") and not f.required
    ]

    keep = [str(f).strip("'") for f in selected_join_fields] if selected_join_fields else join_field_names

    for fname in keep:
        if fname not in join_field_names:
            continue
        fmap = arcpy.FieldMap()
        fmap.addInputField(join_fc, fname)
        out_field = fmap.outputField
        out_field.name = fname
        out_field.aliasName = fname
        fmap.outputField = out_field
        fm.addFieldMap(fmap)

    return fm


def make_spatial_join_params(join_layer_idx):
    """
    Returns the four shared spatial-join parameters:
      p_do_join, p_join_layer, p_join_type, p_join_fields
    join_layer_idx is only used for documentation; enabling logic is handled
    per-tool in updateParameters.
    """
    p_do_join = arcpy.Parameter(
        displayName="Perform Spatial Join",
        name="do_spatial_join",
        datatype="GPBoolean",
        parameterType="Optional",
        direction="Input"
    )
    p_do_join.value = False

    p_join_layer = arcpy.Parameter(
        displayName="Join Layer",
        name="join_layer",
        datatype="GPFeatureLayer",
        parameterType="Optional",
        direction="Input"
    )
    p_join_layer.enabled = False

    p_join_type = arcpy.Parameter(
        displayName="Spatial Relationship",
        name="join_type",
        datatype="GPString",
        parameterType="Optional",
        direction="Input"
    )
    p_join_type.filter.list = [
        "INTERSECT", "WITHIN", "CONTAINS", "CROSSES", "OVERLAPS", "TOUCHES"
    ]
    p_join_type.enabled = False

    p_join_fields = arcpy.Parameter(
        displayName="Fields to Include from Join Layer",
        name="join_fields",
        datatype="GPString",
        parameterType="Optional",
        direction="Input",
        multiValue=True
    )
    p_join_fields.enabled = False

    return p_do_join, p_join_layer, p_join_type, p_join_fields


def update_spatial_join_params(params, do_join_idx, join_layer_idx,
                               join_type_idx, join_fields_idx):
    """Enable/disable spatial join params and refresh field list."""
    do_join = params[do_join_idx].value
    params[join_layer_idx].enabled = bool(do_join)
    params[join_type_idx].enabled = bool(do_join)
    params[join_fields_idx].enabled = bool(do_join)

    join_layer = params[join_layer_idx].valueAsText
    if bool(do_join) and join_layer and not params[join_layer_idx].hasBeenValidated:
        try:
            fields = [
                f.name for f in arcpy.ListFields(join_layer)
                if f.type not in ("OID", "Geometry") and not f.required
            ]
            params[join_fields_idx].filter.list = fields
        except Exception:
            params[join_fields_idx].filter.list = []


def run_spatial_join(working_fc, join_layer, join_type, join_fields_raw):
    """Run a spatial join and return the output feature class path."""
    fm = build_field_mapping(working_fc, join_layer, join_fields_raw)
    result = arcpy.analysis.SpatialJoin(
        target_features=working_fc,
        join_features=join_layer,
        out_feature_class=arcpy.CreateUniqueName("sj_tmp", arcpy.env.scratchGDB),
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        match_option=join_type,
        field_mapping=fm
    )[0]

    # Remove the auto-added spatial join bookkeeping fields
    existing = [f.name for f in arcpy.ListFields(result)]
    drop = [f for f in ("Join_Count", "TARGET_FID") if f in existing]
    if drop:
        arcpy.management.DeleteField(result, drop)

    return result


# ---------------------------------------------------------
# 1. RENAME TOOL
# ---------------------------------------------------------
class RenameGeofabrik(object):
    def __init__(self):
        self.label = "Rename Geofabrik Datasets"
        self.description = (
            "Renames all datasets in the selected folder using the MapAction-style "
            "template naming convention."
        )
        self.canRunInBackground = True

    def getParameterInfo(self):
        p_in = arcpy.Parameter(
            displayName="Original Folder",
            name="input_workspace",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input"
        )

        p_geo = arcpy.Parameter(
            displayName="Geoextent",
            name="geoextent",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )

        p_do_join, p_join_layer, p_join_type, p_join_fields = make_spatial_join_params(3)

        p_output = arcpy.Parameter(
            displayName="Output Location (Folder or Geodatabase)",
            name="output_location",
            datatype="DEWorkspace",
            parameterType="Optional",
            direction="Input"
        )

        p_add = arcpy.Parameter(
            displayName="Add output to map",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_add.value = True

        return [
            p_in,           # 0
            p_geo,          # 1
            p_do_join,      # 2
            p_join_layer,   # 3
            p_join_type,    # 4
            p_join_fields,  # 5
            p_output,       # 6
            p_add,          # 7
        ]

    def updateParameters(self, params):
        update_spatial_join_params(params, 2, 3, 4, 5)

    def execute(self, params, messages):
        input_ws      = params[0].valueAsText
        geoextent     = params[1].valueAsText
        do_join       = bool(params[2].value)
        join_layer    = params[3].valueAsText
        join_type     = params[4].valueAsText
        join_fields   = params[5].values
        output_loc    = params[6].valueAsText
        add_to_map    = bool(params[7].value)

        arcpy.env.workspace = input_ws

        datasets = (
            (arcpy.ListFeatureClasses() or []) +
            (arcpy.ListRasters() or []) +
            (arcpy.ListTables() or [])
        )

        for ds in datasets:
            desc = arcpy.Describe(ds)
            base      = desc.baseName
            src       = desc.catalogPath
            full_name = os.path.splitext(os.path.basename(src))[0]

            arcpy.AddMessage("DEBUG ds={!r}  base={!r}  full_name={!r}".format(ds, base, full_name))

            new_name = resolve_new_name(base, geoextent, full_name)

            working_src = src
            if do_join and join_layer and desc.dataType in ["FeatureClass", "ShapeFile"]:
                working_src = run_spatial_join(working_src, join_layer, join_type, join_fields)

            if output_loc:
                dest = copy_to_destination(working_src, output_loc, new_name)
                if add_to_map:
                    add_path_to_map(dest)


# ---------------------------------------------------------
# 2. MERGE + RENAME TOOL
# ---------------------------------------------------------
class MergeRenameGeofabrik(object):
    def __init__(self):
        self.label = "Merge + Rename Geofabrik Datasets"
        self.description = (
            "Merges datasets with matching names across multiple folders and renames them."
        )
        self.canRunInBackground = True

    def getParameterInfo(self):
        p_in_folders = arcpy.Parameter(
            displayName="Input Folders (Multiple)",
            name="input_folders",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input",
            multiValue=True
        )

        p_geo = arcpy.Parameter(
            displayName="Geoextent",
            name="geoextent",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )

        p_do_join, p_join_layer, p_join_type, p_join_fields = make_spatial_join_params(3)

        p_merged_folder = arcpy.Parameter(
            displayName="Merged Output Folder",
            name="merged_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
        )

        p_output = arcpy.Parameter(
            displayName="Output Location (Folder or Geodatabase)",
            name="output_location",
            datatype="DEWorkspace",
            parameterType="Optional",
            direction="Input"
        )

        p_add = arcpy.Parameter(
            displayName="Add output to map",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_add.value = True

        return [
            p_in_folders,   # 0
            p_geo,          # 1
            p_do_join,      # 2
            p_join_layer,   # 3
            p_join_type,    # 4
            p_join_fields,  # 5
            p_merged_folder,# 6
            p_output,       # 7
            p_add,          # 8
        ]

    def updateParameters(self, params):
        update_spatial_join_params(params, 2, 3, 4, 5)

    def execute(self, params, messages):
        input_folders  = params[0].values
        geoextent      = params[1].valueAsText
        do_join        = bool(params[2].value)
        join_layer     = params[3].valueAsText
        join_type      = params[4].valueAsText
        join_fields    = params[5].values
        merged_folder  = params[6].valueAsText
        output_loc     = params[7].valueAsText
        add_to_map     = bool(params[8].value)

        if not os.path.exists(merged_folder):
            os.makedirs(merged_folder)

        grouped = defaultdict(list)

        for folder in input_folders:
            arcpy.env.workspace = folder
            datasets = (
                (arcpy.ListFeatureClasses() or []) +
                (arcpy.ListRasters() or []) +
                (arcpy.ListTables() or [])
            )
            for ds in datasets:
                desc = arcpy.Describe(ds)
                grouped[desc.baseName].append(desc.catalogPath)

        for base, paths in grouped.items():
            full_name  = os.path.splitext(os.path.basename(paths[0]))[0]
            new_name   = resolve_new_name(base, geoextent, full_name)
            merged_shp = os.path.join(merged_folder, f"{base}_merged.shp")

            if len(paths) == 1:
                arcpy.management.CopyFeatures(paths[0], merged_shp)
            else:
                arcpy.management.Merge(paths, merged_shp)

            working_fc = merged_shp
            if do_join and join_layer:
                working_fc = run_spatial_join(working_fc, join_layer, join_type, join_fields)

            if output_loc:
                dest = copy_to_destination(working_fc, output_loc, new_name)
                if add_to_map:
                    add_path_to_map(dest)


# ---------------------------------------------------------
# 3. CLIP + RENAME TOOL
# ---------------------------------------------------------
class ClipRenameGeofabrik(object):
    def __init__(self):
        self.label = "Clip + Rename Geofabrik Datasets"
        self.description = (
            "Clips datasets to a polygon boundary and renames them."
        )
        self.canRunInBackground = True

    def getParameterInfo(self):
        p_in = arcpy.Parameter(
            displayName="Original Folder",
            name="input_workspace",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input"
        )

        p_geo = arcpy.Parameter(
            displayName="Geoextent",
            name="geoextent",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )

        p_clip = arcpy.Parameter(
            displayName="Clip Feature (Layer or Feature Class)",
            name="clip_feature",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        p_do_join, p_join_layer, p_join_type, p_join_fields = make_spatial_join_params(4)

        p_output = arcpy.Parameter(
            displayName="Output Location (Folder or Geodatabase)",
            name="output_location",
            datatype="DEWorkspace",
            parameterType="Optional",
            direction="Input"
        )

        p_add = arcpy.Parameter(
            displayName="Add output to map",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_add.value = True

        return [
            p_in,           # 0
            p_geo,          # 1
            p_clip,         # 2
            p_do_join,      # 3
            p_join_layer,   # 4
            p_join_type,    # 5
            p_join_fields,  # 6
            p_output,       # 7
            p_add,          # 8
        ]

    def updateParameters(self, params):
        update_spatial_join_params(params, 3, 4, 5, 6)

    def execute(self, params, messages):
        input_ws    = params[0].valueAsText
        geoextent   = params[1].valueAsText
        clip_fc     = params[2].valueAsText
        do_join     = bool(params[3].value)
        join_layer  = params[4].valueAsText
        join_type   = params[5].valueAsText
        join_fields = params[6].values
        output_loc  = params[7].valueAsText
        add_to_map  = bool(params[8].value)

        arcpy.env.workspace = input_ws

        datasets = (
            (arcpy.ListFeatureClasses() or []) +
            (arcpy.ListRasters() or []) +
            (arcpy.ListTables() or [])
        )

        for ds in datasets:
            desc = arcpy.Describe(ds)
            base      = desc.baseName
            src       = desc.catalogPath
            full_name = os.path.splitext(os.path.basename(src))[0]

            new_name = resolve_new_name(base, geoextent, full_name)

            clipped = arcpy.CreateUniqueName("clip_tmp", arcpy.env.scratchGDB)
            arcpy.analysis.Clip(src, clip_fc, clipped)

            working_fc = clipped
            if do_join and join_layer and desc.dataType in ["FeatureClass", "ShapeFile"]:
                working_fc = run_spatial_join(working_fc, join_layer, join_type, join_fields)

            if output_loc:
                dest = copy_to_destination(working_fc, output_loc, new_name)
                if add_to_map:
                    add_path_to_map(dest)


# ---------------------------------------------------------
# 4. MERGE → CLIP → RENAME TOOL
# ---------------------------------------------------------
class MergeClipRenameGeofabrik(object):
    def __init__(self):
        self.label = "Merge + Clip + Rename Geofabrik Datasets"
        self.description = (
            "Merges datasets across folders, clips them to a polygon, and renames them."
        )
        self.canRunInBackground = True

    def getParameterInfo(self):
        p_in_folders = arcpy.Parameter(
            displayName="Input Folders (Multiple)",
            name="input_folders",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input",
            multiValue=True
        )

        p_geo = arcpy.Parameter(
            displayName="Geoextent",
            name="geoextent",
            datatype="GPString",
            parameterType="Required",
            direction="Input"
        )

        p_merged_folder = arcpy.Parameter(
            displayName="Merged Output Folder",
            name="merged_folder",
            datatype="DEFolder",
            parameterType="Required",
            direction="Input"
        )

        p_clip = arcpy.Parameter(
            displayName="Clip Feature (Layer or Feature Class)",
            name="clip_feature",
            datatype="GPFeatureLayer",
            parameterType="Required",
            direction="Input"
        )

        p_do_join, p_join_layer, p_join_type, p_join_fields = make_spatial_join_params(5)

        p_output = arcpy.Parameter(
            displayName="Output Location (Folder or Geodatabase)",
            name="output_location",
            datatype="DEWorkspace",
            parameterType="Optional",
            direction="Input"
        )

        p_add = arcpy.Parameter(
            displayName="Add output to map",
            name="add_to_map",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input"
        )
        p_add.value = True

        return [
            p_in_folders,    # 0
            p_geo,           # 1
            p_merged_folder, # 2
            p_clip,          # 3
            p_do_join,       # 4
            p_join_layer,    # 5
            p_join_type,     # 6
            p_join_fields,   # 7
            p_output,        # 8
            p_add,           # 9
        ]

    def updateParameters(self, params):
        update_spatial_join_params(params, 4, 5, 6, 7)

    def execute(self, params, messages):
        input_folders  = params[0].values
        geoextent      = params[1].valueAsText
        merged_folder  = params[2].valueAsText
        clip_fc        = params[3].valueAsText
        do_join        = bool(params[4].value)
        join_layer     = params[5].valueAsText
        join_type      = params[6].valueAsText
        join_fields    = params[7].values
        output_loc     = params[8].valueAsText
        add_to_map     = bool(params[9].value)

        if not os.path.exists(merged_folder):
            os.makedirs(merged_folder)

        grouped = defaultdict(list)

        for folder in input_folders:
            arcpy.env.workspace = folder
            datasets = (
                (arcpy.ListFeatureClasses() or []) +
                (arcpy.ListRasters() or []) +
                (arcpy.ListTables() or [])
            )
            for ds in datasets:
                desc = arcpy.Describe(ds)
                grouped[desc.baseName].append(desc.catalogPath)

        for base, paths in grouped.items():
            full_name  = os.path.splitext(os.path.basename(paths[0]))[0]
            new_name   = resolve_new_name(base, geoextent, full_name)
            merged_shp = os.path.join(merged_folder, f"{base}_merged.shp")

            if len(paths) == 1:
                arcpy.management.CopyFeatures(paths[0], merged_shp)
            else:
                arcpy.management.Merge(paths, merged_shp)

            clipped = arcpy.CreateUniqueName("clip_tmp", arcpy.env.scratchGDB)
            arcpy.analysis.Clip(merged_shp, clip_fc, clipped)

            working_fc = clipped
            if do_join and join_layer:
                working_fc = run_spatial_join(working_fc, join_layer, join_type, join_fields)

            if output_loc:
                dest = copy_to_destination(working_fc, output_loc, new_name)
                if add_to_map:
                    add_path_to_map(dest)
