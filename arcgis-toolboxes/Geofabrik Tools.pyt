# -*- coding: utf-8 -*-
import arcpy
import os
from collections import defaultdict

class Toolbox(object):
    def __init__(self):
        self.label = "Geofabrik Tools"
        self.alias = "geofabrik_tools"
        self.description = "Standardize Geofabrik OSM data with exact TOC ordering and grouping."
        self.tools = [RenameGeofabrik, MergeRenameGeofabrik, ClipRenameGeofabrik, MergeClipRenameGeofabrik]

# ---------------------------------------------------------
# FINAL MAPPING TABLE: (Output Template, Group, Layer Order)
# ---------------------------------------------------------
LAYER_CONFIG = {
    "gis_osm_places_free": ("{geoextent}_stle_stl_pt_s0_openstreetmap_pp_settlements", "Settlements", 1),
    "gis_osm_pois_free": ("{geoextent}_pois_poi_pt_s0_openstreetmap_pp_pointsofinterest", "POIs", 2),
    "gis_osm_pofw_free": ("{geoextent}_pois_rel_pt_s0_openstreetmap_pp_placeofworship", "POIs", 3),
    "gis_osm_transport_free": ("{geoextent}_tran_trn_pt_s0_openstreetmap_pp_transport", "Transport", 4),
    "gis_osm_traffic_free": ("{geoextent}_tran_trf_pt_s0_openstreetmap_pp_traffic", "Transport", 5),
    "gis_osm_roads_free": ("{geoextent}_tran_rds_ln_s0_openstreetmap_pp_roads", "Transport", 6),
    "gis_osm_railways_free": ("{geoextent}_tran_rrd_ln_s0_openstreetmap_pp_railways", "Transport", 7),
    "gis_osm_natural_free": ("{geoextent}_phys_nat_pt_s0_openstreetmap_pp_natural", "Physical", 8),
    "gis_osm_water_a_free": ("{geoextent}_phys_wat_py_s0_openstreetmap_pp_waterbodies", "Physical", 9),
    "gis_osm_waterways_free": ("{geoextent}_phys_riv_ln_s0_openstreetmap_pp_rivers", "Physical", 10),
    "gis_osm_buildings_a_free": ("{geoextent}_bldg_bld_py_s0_openstreetmap_pp_buildings", "Landuse", 11),
    "gis_osm_protected_areas_a_free": ("{geoextent}_land_npk_py_openstreetmap_pp_protectedareas", "Landuse", 12),
    "gis_osm_pois_a_free": ("{geoextent}_pois_poi_py_s0_openstreetmap_pp_pointsofinterest", "Landuse", 13),
    "gis_osm_pofw_a_free": ("{geoextent}_pois_rel_py_s0_openstreetmap_pp_placeofworship", "Landuse", 14),
    "gis_osm_transport_a_free": ("{geoextent}_tran_trn_py_s0_openstreetmap_pp_transport", "Landuse", 15),
    "gis_osm_traffic_a_free": ("{geoextent}_tran_trf_py_s0_openstreetmap_pp_traffic", "Landuse", 16),
    "gis_osm_natural_a_free": ("{geoextent}_phys_nat_py_s0_openstreetmap_pp_natural", "Landuse", 17),
    "gis_osm_landuse_a_free": ("{geoextent}_land_lnd_py_s0_openstreetmap_pp_landuse", "Landuse", 18),
    "gis_osm_places_a_free": ("{geoextent}_stle_stl_py_s0_openstreetmap_pp_settlements", "Admin areas", 19),
    "gis_osm_adminareas_a_free": ("{geoextent}_admn_ad_py_s0_openstreetmap_pp_adminareas", "Admin areas", 20),
}

def resolve_mapping(internal_name):
    """Normalizes Geopackage/Shapefile names and retrieves config."""
    clean = internal_name.replace("main.", "").strip()
    if clean.endswith("_1"): 
        clean = clean[:-2]
    if "_free" not in clean and "_free" in internal_name:
        clean = clean + "_free"
    return LAYER_CONFIG.get(clean, (None, None, 99))

# ---------------------------------------------------------
# CORE LOGIC
# ---------------------------------------------------------
def copy_and_group(src, dest_ws, new_name, group_name, add_to_map):
    desc = arcpy.Describe(src)
    is_container = dest_ws.lower().endswith((".gdb", ".gpkg"))
    clean_name = arcpy.ValidateTableName(new_name, dest_ws)
    dest_path = os.path.join(dest_ws, clean_name)
    
    # Data Copy
    if desc.dataType in ["FeatureClass", "ShapeFile"]:
        if not is_container: dest_path += ".shp"
        arcpy.management.CopyFeatures(src, dest_path)
    elif desc.dataType == "RasterDataset":
        arcpy.management.CopyRaster(src, dest_path)
    
    # Mapping Logic
    if add_to_map:
        try:
            aprx = arcpy.mp.ArcGISProject("CURRENT")
            m = aprx.activeMap
            if m:
                # 1. Find or create the group layer
                target_group = next((g for g in m.listLayers(group_name) if g.isGroupLayer), None)
                if not target_group:
                    target_group = m.createGroupLayer(group_name)
                
                # Ensure group is expanded
                target_group.expanded = True
                
                # 2. Add layer to the map
                new_lyr = m.addDataFromPath(dest_path)
                
                # 3. Move into group (Adding to TOP ensures Layer 1 ends up on top after sorted processing)
                m.addLayerToGroup(target_group, new_lyr, "TOP")
                m.removeLayer(new_lyr)
        except Exception as e:
            arcpy.AddWarning("TOC Error: {}".format(e))
    return dest_path

def run_sj(working, lyr, typ, flds):
    fm = arcpy.FieldMappings()
    fm.addTable(working)
    if flds:
        for f in flds:
            fmap = arcpy.FieldMap()
            fmap.addInputField(lyr, f)
            fm.addFieldMap(fmap)
    out = arcpy.CreateUniqueName("sj_tmp", arcpy.env.scratchGDB)
    return arcpy.analysis.SpatialJoin(working, lyr, out, "JOIN_ONE_TO_ONE", "KEEP_ALL", fm, typ)[0]

def make_sj_params():
    p1 = arcpy.Parameter(name="do_sj", displayName="Spatial Join", datatype="GPBoolean", parameterType="Optional", direction="Input")
    p2 = arcpy.Parameter(name="sj_lyr", displayName="Join Layer", datatype="GPFeatureLayer", parameterType="Optional", direction="Input")
    p3 = arcpy.Parameter(name="sj_typ", displayName="Relationship", datatype="GPString", parameterType="Optional", direction="Input")
    p3.filter.list = ["INTERSECT", "WITHIN", "CONTAINS", "TOUCHES"]
    p4 = arcpy.Parameter(name="sj_fld", displayName="Join Fields", datatype="GPString", parameterType="Optional", direction="Input", multiValue=True)
    p2.enabled = p3.enabled = p4.enabled = False
    return p1, p2, p3, p4

def make_common():
    p1 = arcpy.Parameter(name="add_map", displayName="Add to Map", datatype="GPBoolean", parameterType="Optional", direction="Input")
    p1.value = False
    p2 = arcpy.Parameter(name="out_ws", displayName="Output Workspace", datatype="DEWorkspace", parameterType="Required", direction="Input")
    return p1, p2

# ---------------------------------------------------------
# TOOLS
# ---------------------------------------------------------
class RenameGeofabrik(object):
    def __init__(self): self.label = "1. Rename Geofabrik"
    def getParameterInfo(self):
        return [arcpy.Parameter(name="in_ws", displayName="Input Workspace", datatype="DEWorkspace", parameterType="Required", direction="Input"),
                arcpy.Parameter(name="geo", displayName="Geoextent", datatype="GPString", parameterType="Required", direction="Input")] + list(make_sj_params()) + list(make_common())
    def updateParameters(self, params):
        params[3].enabled = params[4].enabled = params[5].enabled = bool(params[2].value)
    def execute(self, params, messages):
        in_ws, geo, out_ws, add_map = params[0].valueAsText, params[1].valueAsText, params[7].valueAsText, params[6].value
        arcpy.env.workspace = in_ws
        fcs = sorted(arcpy.ListFeatureClasses() or [], key=lambda x: resolve_mapping(x)[2], reverse=True)
        for ds in fcs:
            template, group, l_order = resolve_mapping(ds)
            if template:
                new_name = template.format(geoextent=geo)
                working = os.path.join(in_ws, ds)
                if params[2].value: 
                    working = run_sj(working, params[3].valueAsText, params[4].valueAsText, params[5].values)
                copy_and_group(working, out_ws, new_name, group, add_map)

class MergeRenameGeofabrik(object):
    def __init__(self): self.label = "2. Merge + Rename Geofabrik"
    def getParameterInfo(self):
        return [arcpy.Parameter(name="in_ws", displayName="Input Workspaces", datatype="DEWorkspace", parameterType="Required", direction="Input", multiValue=True),
                arcpy.Parameter(name="geo", displayName="Geoextent", datatype="GPString", parameterType="Required", direction="Input")] + list(make_sj_params()) + list(make_common())
    def updateParameters(self, params):
        params[3].enabled = params[4].enabled = params[5].enabled = bool(params[2].value)
    def execute(self, params, messages):
        in_wss, geo, out_ws, add_map = params[0].values, params[1].valueAsText, params[7].valueAsText, params[6].value
        groups_dict = defaultdict(list)
        for ws in in_wss:
            arcpy.env.workspace = ws
            for fc in arcpy.ListFeatureClasses() or []:
                key = fc.replace("main.", "").replace("_1", "")
                if "_free" not in key and "_free" in fc: key += "_free"
                groups_dict[key].append(os.path.join(ws, fc))
        
        sorted_keys = sorted(groups_dict.keys(), key=lambda k: resolve_mapping(k)[2], reverse=True)
        for key in sorted_keys:
            template, group, l_order = resolve_mapping(key)
            if template:
                new_name = template.format(geoextent=geo)
                merged = arcpy.management.Merge(groups_dict[key], arcpy.CreateUniqueName("m", arcpy.env.scratchGDB))
                working = merged
                if params[2].value: 
                    working = run_sj(working, params[3].valueAsText, params[4].valueAsText, params[5].values)
                copy_and_group(working, out_ws, new_name, group, add_map)

class ClipRenameGeofabrik(object):
    def __init__(self): self.label = "3. Clip + Rename Geofabrik"
    def getParameterInfo(self):
        return [arcpy.Parameter(name="in_ws", displayName="Input Workspace", datatype="DEWorkspace", parameterType="Required", direction="Input"),
                arcpy.Parameter(name="geo", displayName="Geoextent", datatype="GPString", parameterType="Required", direction="Input"),
                arcpy.Parameter(name="clip", displayName="Clip Feature", datatype="GPFeatureLayer", parameterType="Required", direction="Input")] + list(make_sj_params()) + list(make_common())
    def updateParameters(self, params):
        params[4].enabled = params[5].enabled = params[6].enabled = bool(params[3].value)
    def execute(self, params, messages):
        in_ws, geo, clip_fc, out_ws, add_map = params[0].valueAsText, params[1].valueAsText, params[2].valueAsText, params[8].valueAsText, params[7].value
        arcpy.env.workspace = in_ws
        fcs = sorted(arcpy.ListFeatureClasses() or [], key=lambda x: resolve_mapping(x)[2], reverse=True)
        for fc in fcs:
            template, group, l_order = resolve_mapping(fc)
            if template:
                new_name = template.format(geoextent=geo)
                clipped = arcpy.analysis.Clip(os.path.join(in_ws, fc), clip_fc, arcpy.CreateUniqueName("c", arcpy.env.scratchGDB))
                working = clipped
                if params[3].value: 
                    working = run_sj(working, params[4].valueAsText, params[5].valueAsText, params[6].values)
                copy_and_group(working, out_ws, new_name, group, add_map)

class MergeClipRenameGeofabrik(object):
    def __init__(self): self.label = "4. Merge + Clip + Rename Geofabrik"
    def getParameterInfo(self):
        return [arcpy.Parameter(name="in_ws", displayName="Input Workspaces", datatype="DEWorkspace", parameterType="Required", direction="Input", multiValue=True),
                arcpy.Parameter(name="geo", displayName="Geoextent", datatype="GPString", parameterType="Required", direction="Input"),
                arcpy.Parameter(name="clip", displayName="Clip Feature", datatype="GPFeatureLayer", parameterType="Required", direction="Input")] + list(make_sj_params()) + list(make_common())
    def updateParameters(self, params):
        params[4].enabled = params[5].enabled = params[6].enabled = bool(params[3].value)
    def execute(self, params, messages):
        in_wss, geo, clip_fc, out_ws, add_map = params[0].values, params[1].valueAsText, params[2].valueAsText, params[8].valueAsText, params[7].value
        groups_dict = defaultdict(list)
        for ws in in_wss:
            arcpy.env.workspace = ws
            for fc in arcpy.ListFeatureClasses() or []:
                key = fc.replace("main.", "").replace("_1", "")
                if "_free" not in key and "_free" in fc: key += "_free"
                groups_dict[key].append(os.path.join(ws, fc))
        
        sorted_keys = sorted(groups_dict.keys(), key=lambda k: resolve_mapping(k)[2], reverse=True)
        for key in sorted_keys:
            template, group, l_order = resolve_mapping(key)
            if template:
                new_name = template.format(geoextent=geo)
                merged = arcpy.management.Merge(groups_dict[key], arcpy.CreateUniqueName("m", arcpy.env.scratchGDB))
                clipped = arcpy.analysis.Clip(merged, clip_fc, arcpy.CreateUniqueName("c", arcpy.env.scratchGDB))
                working = clipped
                if params[3].value: 
                    working = run_sj(working, params[4].valueAsText, params[5].valueAsText, params[6].values)
                copy_and_group(working, out_ws, new_name, group, add_map)