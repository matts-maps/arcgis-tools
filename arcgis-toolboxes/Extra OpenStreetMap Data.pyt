import arcpy
import urllib.request
import urllib.parse
import json
import os


class Toolbox(object):
    def __init__(self):
        self.label = "Extra OpenStreetMap Data"
        self.alias = "ExtraOpenStreetMapData"
        self.tools = [
            DownloadFerryRoutes,
            DownloadSurfaceTypes,
            DownloadMaritimeFeatures
        ]


# ============================================================
# Shared helpers
# ============================================================

def _safe_extent(geo_extent):
    return "".join(c if c.isalnum() or c == "_" else "" for c in geo_extent.strip().lower())


def _get_bbox(aoi, messages):
    desc = arcpy.Describe(aoi)
    ext = desc.extent
    sr_wgs84 = arcpy.SpatialReference(4326)
    if desc.spatialReference.factoryCode != 4326:
        env_geom = arcpy.Polygon(
            arcpy.Array([
                arcpy.Point(ext.XMin, ext.YMin),
                arcpy.Point(ext.XMax, ext.YMin),
                arcpy.Point(ext.XMax, ext.YMax),
                arcpy.Point(ext.XMin, ext.YMax),
            ]),
            desc.spatialReference
        )
        ext2 = env_geom.projectAs(sr_wgs84).extent
        return ext2.YMin, ext2.XMin, ext2.YMax, ext2.XMax
    else:
        return ext.YMin, ext.XMin, ext.YMax, ext.XMax


def _query_overpass(query, user_agent, messages):
    try:
        data = urllib.parse.urlencode({"data": query}).encode("utf-8")
        req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=data)
        req.add_header("User-Agent", user_agent)
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        messages.addErrorMessage(f"Failed to query Overpass API: {e}")
        raise arcpy.ExecuteError


def _validate_bbox(parameters):
    if not parameters[0].value and parameters[1].altered and parameters[1].value:
        parts = parameters[1].valueAsText.split(",")
        if len(parts) != 4:
            parameters[1].setErrorMessage(
                "Bounding box must have exactly 4 values: South, West, North, East"
            )
        else:
            try:
                c = [float(p.strip()) for p in parts]
                if c[0] >= c[2]:
                    parameters[1].setErrorMessage("South must be less than North.")
                elif c[1] >= c[3]:
                    parameters[1].setErrorMessage("West must be less than East.")
            except ValueError:
                parameters[1].setErrorMessage("All bounding box values must be numeric.")


def _update_common_parameters(parameters, auto_name_suffix):
    parameters[1].enabled = not bool(parameters[0].value)
    if parameters[3].altered and parameters[3].value:
        safe = _safe_extent(parameters[3].valueAsText)
        parameters[4].value = f"{safe}{auto_name_suffix}"
    do_join = parameters[6].value
    parameters[7].enabled = bool(do_join)
    parameters[8].enabled = bool(do_join) and bool(parameters[7].value)


def _update_common_messages(parameters):
    _validate_bbox(parameters)
    if parameters[6].value and not parameters[7].value:
        parameters[7].setWarningMessage("A target layer is required to perform a spatial join.")


def _build_parameters(join_target_name, name_example, name_convention):
    """Build the 10 shared parameters with full help text."""

    param_aoi = arcpy.Parameter(
        displayName="Area of Interest (optional)",
        name="aoi",
        datatype=["GPFeatureLayer", "DEFeatureClass", "DEShapefile"],
        parameterType="Optional",
        direction="Input"
    )
    param_aoi.description = (
        "Optional polygon layer used to define the download area. The bounding box "
        "of this layer will be used to query OpenStreetMap. Drag from the Contents "
        "pane or browse to the file. If left empty, the Manual Bounding Box will be "
        "used instead."
    )

    param_bbox = arcpy.Parameter(
        displayName="Manual Bounding Box (South, West, North, East) — used if no AOI",
        name="bbox",
        datatype="GPString",
        parameterType="Optional",
        direction="Input"
    )
    param_bbox.value = "-90,-180,90,180"
    param_bbox.description = (
        "Bounding box used to define the download area when no Area of Interest layer "
        "is provided. Enter four comma-separated decimal degree values in the order: "
        "South, West, North, East. For example, 49.9,-6.4,60.9,1.8 covers Great Britain. "
        "Coordinates must be in WGS84 (EPSG:4326). This parameter is disabled when an "
        "Area of Interest layer is provided."
    )

    param_output = arcpy.Parameter(
        displayName="Output Location (Folder or Geodatabase)",
        name="output_location",
        datatype=["DEWorkspace", "DEFolder"],
        parameterType="Required",
        direction="Input"
    )
    param_output.description = (
        "The folder or geodatabase where the output feature class will be saved. "
        "Both file geodatabases (.gdb) and folders (producing shapefiles) are supported."
    )

    param_geo_extent = arcpy.Parameter(
        displayName="Geographic Extent Tag (e.g. usa, can, gbr)",
        name="geo_extent",
        datatype="GPString",
        parameterType="Required",
        direction="Input"
    )
    param_geo_extent.description = (
        "A short lowercase tag identifying the geographic coverage of the data. This is "
        "used to build the standardised output feature class name. For example, entering "
        f"'gbr' will produce: {name_example}. "
        "Use lowercase letters only, with no spaces or special characters (e.g. usa, can, gbr, aus)."
    )

    param_name = arcpy.Parameter(
        displayName="Output Feature Class Name (auto-generated)",
        name="output_name",
        datatype="GPString",
        parameterType="Derived",
        direction="Output"
    )
    param_name.description = (
        "The output feature class name is automatically generated from the Geographic "
        f"Extent Tag using the project naming convention: {name_convention}. "
        "This field updates as you type the extent tag and cannot be edited directly."
    )

    param_add_to_map = arcpy.Parameter(
        displayName="Add output to map",
        name="add_to_map",
        datatype="GPBoolean",
        parameterType="Optional",
        direction="Input"
    )
    param_add_to_map.value = True
    param_add_to_map.description = (
        "When checked, the output feature class will be automatically added to the "
        "active map after the tool completes successfully."
    )

    param_do_join = arcpy.Parameter(
        displayName="Perform Spatial Join",
        name="perform_spatial_join",
        datatype="GPBoolean",
        parameterType="Optional",
        direction="Input"
    )
    param_do_join.value = False
    param_do_join.description = (
        "When checked, a spatial join will be performed between the downloaded features "
        "and a target layer. The joined output is saved as a separate feature class with "
        "'_SpatialJoin' appended to the name. TARGET_FID and Join_Count are always "
        "included in the output regardless of field selection."
    )

    param_join_target = arcpy.Parameter(
        displayName="Spatial Join — Target Layer",
        name=join_target_name,
        datatype=["GPFeatureLayer", "DEFeatureClass", "DEShapefile"],
        parameterType="Optional",
        direction="Input"
    )
    param_join_target.enabled = False
    param_join_target.description = (
        "The layer to spatially join against the downloaded features. This layer acts "
        "as the join features in the spatial join. Drag from the Contents pane or browse "
        "to the file. Only available when Perform Spatial Join is checked."
    )

    param_join_fields = arcpy.Parameter(
        displayName="Spatial Join — Fields to Include from Target",
        name="join_fields",
        datatype="Field",
        parameterType="Optional",
        direction="Input",
        multiValue=True
    )
    param_join_fields.parameterDependencies = [param_join_target.name]
    param_join_fields.enabled = False
    param_join_fields.description = (
        "Select which fields from the Target Layer to carry through into the spatial join "
        "output. Multiple fields can be selected. TARGET_FID and Join_Count are always "
        "retained in the output regardless of this selection. Leave empty to include no "
        "additional fields from the target layer."
    )

    param_out_fc = arcpy.Parameter(
        displayName="Output Feature Class",
        name="out_fc",
        datatype="DEFeatureClass",
        parameterType="Derived",
        direction="Output"
    )
    param_out_fc.description = (
        "The path to the output feature class created by the tool. If a spatial join was "
        "performed, this points to the joined output."
    )

    return [
        param_aoi,         # 0
        param_bbox,        # 1
        param_output,      # 2
        param_geo_extent,  # 3
        param_name,        # 4
        param_add_to_map,  # 5
        param_do_join,     # 6
        param_join_target, # 7
        param_join_fields, # 8
        param_out_fc       # 9
    ]


def _run_spatial_join(out_fc, output_loc, output_name, join_target, join_fields, messages):
    messages.addMessage("Performing spatial join...")
    sj_name = output_name + "_SpatialJoin"
    sj_fc = os.path.join(output_loc, sj_name)
    if arcpy.Exists(sj_fc):
        arcpy.management.Delete(sj_fc)

    fm = arcpy.FieldMappings()
    fm.addTable(out_fc)
    fm.addTable(join_target)

    keep_fields   = set(f.strip() for f in join_fields.split(";") if f.strip()) if join_fields else set()
    always_keep   = {"TARGET_FID", "Join_Count"}
    target_fields = {f.name for f in arcpy.ListFields(join_target)}
    osm_fields    = {f.name for f in arcpy.ListFields(out_fc)}

    for i in range(fm.fieldCount - 1, -1, -1):
        fname = fm.getFieldMap(i).outputField.name
        if fname in target_fields and fname not in osm_fields:
            if fname not in keep_fields and fname not in always_keep:
                fm.removeFieldMap(i)

    arcpy.analysis.SpatialJoin(
        target_features=out_fc,
        join_features=join_target,
        out_feature_class=sj_fc,
        join_operation="JOIN_ONE_TO_ONE",
        join_type="KEEP_ALL",
        field_mapping=fm
    )
    sj_count = int(arcpy.management.GetCount(sj_fc)[0])
    messages.addMessage(f"Spatial join complete: {sj_fc} with {sj_count} features.")
    return sj_fc


def _add_to_map(out_fc, messages):
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        active_map = aprx.activeMap
        if active_map:
            active_map.addDataFromPath(out_fc)
            messages.addMessage("Layer added to the active map.")
        else:
            messages.addWarningMessage("No active map found. Layer was not added to the map.")
    except Exception as e:
        messages.addWarningMessage(f"Could not add layer to map: {e}")


# ============================================================
# Tool 1 — Ferry Routes
# ============================================================

class DownloadFerryRoutes(object):
    def __init__(self):
        self.label = "Download Ferry Routes"
        self.description = (
            "Downloads ferry routes from OpenStreetMap (OSM) using the Overpass API "
            "and saves them as a polyline feature class.\n\n"
            "Ferry routes are tagged in OSM as route=ferry. They represent scheduled "
            "passenger and vehicle ferry services crossing bodies of water, including "
            "river crossings, inter-island services and coastal routes.\n\n"
            "Attributes captured:\n"
            "  - name: The name of the ferry route or service.\n"
            "  - from_loc: The origin terminal or location.\n"
            "  - to_loc: The destination terminal or location.\n\n"
            "Output is a polyline feature class in WGS84 (EPSG:4326)."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        return _build_parameters(
            join_target_name="join_target_fer",
            name_example="gbr_tran_fer_ln_s0_openstreetmap_pp_ferryroutes",
            name_convention="{geoextent}_tran_fer_ln_s0_openstreetmap_pp_ferryroutes"
        )

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        _update_common_parameters(parameters, "_tran_fer_ln_s0_openstreetmap_pp_ferryroutes")

    def updateMessages(self, parameters):
        _update_common_messages(parameters)

    def execute(self, parameters, messages):
        aoi         = parameters[0].value
        bbox_str    = parameters[1].valueAsText
        output_loc  = parameters[2].valueAsText
        geo_extent  = parameters[3].valueAsText.strip().lower()
        add_to_map  = parameters[5].value
        do_join     = parameters[6].value
        join_target = parameters[7].valueAsText
        join_fields = parameters[8].valueAsText

        safe = _safe_extent(geo_extent)
        output_name = f"{safe}_tran_fer_ln_s0_openstreetmap_pp_ferryroutes"
        messages.addMessage(f"Output will be saved as: {output_name}")

        sr_wgs84 = arcpy.SpatialReference(4326)
        if aoi:
            messages.addMessage("Calculating bounding box from AOI layer...")
            south, west, north, east = _get_bbox(aoi, messages)
        else:
            parts = [float(x.strip()) for x in bbox_str.split(",")]
            south, west, north, east = parts[0], parts[1], parts[2], parts[3]
        messages.addMessage(f"Bounding box: South={south}, West={west}, North={north}, East={east}")

        query = f"""
[out:json][timeout:90];
(
  way["route"="ferry"]({south},{west},{north},{east});
  relation["route"="ferry"]({south},{west},{north},{east});
);
out geom;
"""
        messages.addMessage("Querying Overpass API for ferry routes...")
        osm_data = _query_overpass(query, "ArcGIS-OSM-FerryTool/1.0", messages)
        elements = osm_data.get("elements", [])
        messages.addMessage(f"Received {len(elements)} OSM elements.")
        if not elements:
            messages.addWarningMessage("No ferry routes found in the specified area.")
            return

        rows = []
        for elem in elements:
            etype = elem.get("type")
            tags  = elem.get("tags", {})
            if etype == "way":
                nodes = elem.get("geometry", [])
                if len(nodes) >= 2:
                    pts = arcpy.Array([arcpy.Point(n["lon"], n["lat"]) for n in nodes])
                    rows.append((arcpy.Polyline(pts, sr_wgs84), tags))
            elif etype == "relation":
                for member in elem.get("members", []):
                    if member.get("type") == "way":
                        nodes = member.get("geometry", [])
                        if len(nodes) >= 2:
                            pts = arcpy.Array([arcpy.Point(n["lon"], n["lat"]) for n in nodes])
                            rows.append((arcpy.Polyline(pts, sr_wgs84), tags))

        if not rows:
            messages.addWarningMessage("No valid polyline geometry could be built.")
            return
        messages.addMessage(f"Built {len(rows)} polyline features.")

        out_fc = os.path.join(output_loc, output_name)
        if arcpy.Exists(out_fc):
            arcpy.management.Delete(out_fc)
        arcpy.management.CreateFeatureclass(output_loc, output_name, "POLYLINE", spatial_reference=sr_wgs84)
        arcpy.management.AddField(out_fc, "name",     "TEXT", field_length=255, field_alias="Name")
        arcpy.management.AddField(out_fc, "from_loc", "TEXT", field_length=255, field_alias="From")
        arcpy.management.AddField(out_fc, "to_loc",   "TEXT", field_length=255, field_alias="To")

        def _t(tags, key, n=255):
            v = tags.get(key, "")
            return str(v)[:n] if v else ""

        with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "name", "from_loc", "to_loc"]) as cur:
            for (geom, tags) in rows:
                cur.insertRow((geom, _t(tags, "name"), _t(tags, "from"), _t(tags, "to")))

        count = int(arcpy.management.GetCount(out_fc)[0])
        messages.addMessage(f"Successfully created: {out_fc} with {count} features.")

        if do_join and join_target:
            out_fc = _run_spatial_join(out_fc, output_loc, output_name, join_target, join_fields, messages)

        parameters[9].value = out_fc
        if add_to_map:
            _add_to_map(out_fc, messages)


# ============================================================
# Tool 2 — Surface Types
# ============================================================

class DownloadSurfaceTypes(object):
    def __init__(self):
        self.label = "Download Surface Types"
        self.description = (
            "Downloads bare rock, rock, mud and sand surface polygons from "
            "OpenStreetMap (OSM) using the Overpass API and saves them as a single "
            "polygon feature class.\n\n"
            "These features are mapped in OSM using the natural= tag:\n"
            "  - bare_rock: Exposed rock with no soil or vegetation, such as cliff "
            "faces, rocky outcrops and glacially scoured bedrock.\n"
            "  - rock: Rocky terrain including boulder fields, scree slopes and "
            "areas of broken rock.\n"
            "  - mud: Mudflats, tidal mud and fine wet sediment, commonly found in "
            "estuaries and along tidal shores.\n"
            "  - sand: Sand surfaces including beaches, dunes, sandflats and "
            "desert sand areas.\n\n"
            "All four types are combined into one feature class. The fclass field "
            "records the surface type for each feature.\n\n"
            "Output is a polygon feature class in WGS84 (EPSG:4326)."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        return _build_parameters(
            join_target_name="join_target_sur",
            name_example="gbr_phys_sur_py_s0_openstreetmap_pp_surfacetypes",
            name_convention="{geoextent}_phys_sur_py_s0_openstreetmap_pp_surfacetypes"
        )

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        _update_common_parameters(parameters, "_phys_sur_py_s0_openstreetmap_pp_surfacetypes")

    def updateMessages(self, parameters):
        _update_common_messages(parameters)

    def execute(self, parameters, messages):
        aoi         = parameters[0].value
        bbox_str    = parameters[1].valueAsText
        output_loc  = parameters[2].valueAsText
        geo_extent  = parameters[3].valueAsText.strip().lower()
        add_to_map  = parameters[5].value
        do_join     = parameters[6].value
        join_target = parameters[7].valueAsText
        join_fields = parameters[8].valueAsText

        safe = _safe_extent(geo_extent)
        output_name = f"{safe}_phys_sur_py_s0_openstreetmap_pp_surfacetypes"
        messages.addMessage(f"Output will be saved as: {output_name}")

        feature_types = ["bare_rock", "rock", "mud", "sand"]

        sr_wgs84 = arcpy.SpatialReference(4326)
        if aoi:
            messages.addMessage("Calculating bounding box from AOI layer...")
            south, west, north, east = _get_bbox(aoi, messages)
        else:
            parts = [float(x.strip()) for x in bbox_str.split(",")]
            south, west, north, east = parts[0], parts[1], parts[2], parts[3]
        messages.addMessage(f"Bounding box: South={south}, West={west}, North={north}, East={east}")

        way_q = "\n".join([f'  way["natural"="{ft}"]({south},{west},{north},{east});' for ft in feature_types])
        rel_q = "\n".join([f'  relation["natural"="{ft}"]({south},{west},{north},{east});' for ft in feature_types])
        query = f"[out:json][timeout:90];\n(\n{way_q}\n{rel_q}\n);\nout geom;\n"

        messages.addMessage("Querying Overpass API for surface types (bare_rock, rock, mud, sand)...")
        osm_data = _query_overpass(query, "ArcGIS-OSM-SurfaceTypesTool/1.0", messages)
        elements = osm_data.get("elements", [])
        messages.addMessage(f"Received {len(elements)} OSM elements.")
        if not elements:
            messages.addWarningMessage("No surface type features found in the specified area.")
            return

        rows = []
        for elem in elements:
            etype  = elem.get("type")
            tags   = elem.get("tags", {})
            fclass = tags.get("natural", "")
            name   = tags.get("name", "")
            if etype == "way":
                nodes = elem.get("geometry", [])
                if len(nodes) >= 3:
                    pts = arcpy.Array([arcpy.Point(n["lon"], n["lat"]) for n in nodes])
                    rows.append((arcpy.Polygon(pts, sr_wgs84), fclass, name))
            elif etype == "relation":
                for member in elem.get("members", []):
                    if member.get("type") == "way" and member.get("role") == "outer":
                        nodes = member.get("geometry", [])
                        if len(nodes) >= 3:
                            pts = arcpy.Array([arcpy.Point(n["lon"], n["lat"]) for n in nodes])
                            rows.append((arcpy.Polygon(pts, sr_wgs84), fclass, name))

        if not rows:
            messages.addWarningMessage("No valid polygon geometry could be built.")
            return

        for ft in feature_types:
            messages.addMessage(f"  {ft}: {sum(1 for r in rows if r[1] == ft)} features")
        messages.addMessage(f"Total polygon features built: {len(rows)}")

        out_fc = os.path.join(output_loc, output_name)
        if arcpy.Exists(out_fc):
            arcpy.management.Delete(out_fc)
        arcpy.management.CreateFeatureclass(output_loc, output_name, "POLYGON", spatial_reference=sr_wgs84)
        arcpy.management.AddField(out_fc, "fclass", "TEXT", field_length=50,  field_alias="Surface Type")
        arcpy.management.AddField(out_fc, "name",   "TEXT", field_length=255, field_alias="Name")

        with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "fclass", "name"]) as cur:
            for (geom, fclass, name) in rows:
                cur.insertRow((geom, fclass[:50] if fclass else "", name[:255] if name else ""))

        count = int(arcpy.management.GetCount(out_fc)[0])
        messages.addMessage(f"Successfully created: {out_fc} with {count} features.")

        if do_join and join_target:
            out_fc = _run_spatial_join(out_fc, output_loc, output_name, join_target, join_fields, messages)

        parameters[9].value = out_fc
        if add_to_map:
            _add_to_map(out_fc, messages)


# ============================================================
# Tool 3 — Maritime Features
# ============================================================

class DownloadMaritimeFeatures(object):
    def __init__(self):
        self.label = "Download Maritime Features"
        self.description = (
            "Downloads tidal channel, basin, bay, cape and strait polygons from "
            "OpenStreetMap (OSM) using the Overpass API and saves them as a single "
            "polygon feature class.\n\n"
            "These features are mapped in OSM using the natural= tag:\n"
            "  - tidal_channel: Channels in tidal areas that fill and drain with the "
            "tide, typically found in estuaries, saltmarshes and mudflats.\n"
            "  - basin: An enclosed or semi-enclosed body of water such as a harbour "
            "basin, tidal basin or inland water body.\n"
            "  - bay: A body of water partially enclosed by land, forming an indentation "
            "in the coastline, smaller than a gulf.\n"
            "  - cape: A headland or promontory extending into a body of water, often "
            "used as a navigational landmark.\n"
            "  - strait: A narrow passage of water connecting two larger bodies of "
            "water, such as the Strait of Dover or the Bosphorus.\n\n"
            "All five types are combined into one feature class. The fclass field "
            "records the feature type for each polygon.\n\n"
            "Output is a polygon feature class in WGS84 (EPSG:4326)."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        return _build_parameters(
            join_target_name="join_target_mar",
            name_example="gbr_phys_mar_py_s0_openstreetmap_pp_maritimefeatures",
            name_convention="{geoextent}_phys_mar_py_s0_openstreetmap_pp_maritimefeatures"
        )

    def isLicensed(self):
        return True

    def updateParameters(self, parameters):
        _update_common_parameters(parameters, "_phys_mar_py_s0_openstreetmap_pp_maritimefeatures")

    def updateMessages(self, parameters):
        _update_common_messages(parameters)

    def execute(self, parameters, messages):
        aoi         = parameters[0].value
        bbox_str    = parameters[1].valueAsText
        output_loc  = parameters[2].valueAsText
        geo_extent  = parameters[3].valueAsText.strip().lower()
        add_to_map  = parameters[5].value
        do_join     = parameters[6].value
        join_target = parameters[7].valueAsText
        join_fields = parameters[8].valueAsText

        safe = _safe_extent(geo_extent)
        output_name = f"{safe}_phys_mar_py_s0_openstreetmap_pp_maritimefeatures"
        messages.addMessage(f"Output will be saved as: {output_name}")

        feature_types = ["tidal_channel", "basin", "bay", "cape", "strait"]

        sr_wgs84 = arcpy.SpatialReference(4326)
        if aoi:
            messages.addMessage("Calculating bounding box from AOI layer...")
            south, west, north, east = _get_bbox(aoi, messages)
        else:
            parts = [float(x.strip()) for x in bbox_str.split(",")]
            south, west, north, east = parts[0], parts[1], parts[2], parts[3]
        messages.addMessage(f"Bounding box: South={south}, West={west}, North={north}, East={east}")

        way_q = "\n".join([f'  way["natural"="{ft}"]({south},{west},{north},{east});' for ft in feature_types])
        rel_q = "\n".join([f'  relation["natural"="{ft}"]({south},{west},{north},{east});' for ft in feature_types])
        query = f"[out:json][timeout:90];\n(\n{way_q}\n{rel_q}\n);\nout geom;\n"

        messages.addMessage("Querying Overpass API for maritime features (tidal_channel, basin, bay, cape, strait)...")
        osm_data = _query_overpass(query, "ArcGIS-OSM-MaritimeFeaturesTool/1.0", messages)
        elements = osm_data.get("elements", [])
        messages.addMessage(f"Received {len(elements)} OSM elements.")
        if not elements:
            messages.addWarningMessage("No maritime features found in the specified area.")
            return

        rows = []
        for elem in elements:
            etype  = elem.get("type")
            tags   = elem.get("tags", {})
            fclass = tags.get("natural", "")
            name   = tags.get("name", "")
            if etype == "way":
                nodes = elem.get("geometry", [])
                if len(nodes) >= 3:
                    pts = arcpy.Array([arcpy.Point(n["lon"], n["lat"]) for n in nodes])
                    rows.append((arcpy.Polygon(pts, sr_wgs84), fclass, name))
            elif etype == "relation":
                for member in elem.get("members", []):
                    if member.get("type") == "way" and member.get("role") == "outer":
                        nodes = member.get("geometry", [])
                        if len(nodes) >= 3:
                            pts = arcpy.Array([arcpy.Point(n["lon"], n["lat"]) for n in nodes])
                            rows.append((arcpy.Polygon(pts, sr_wgs84), fclass, name))

        if not rows:
            messages.addWarningMessage("No valid polygon geometry could be built.")
            return

        for ft in feature_types:
            messages.addMessage(f"  {ft}: {sum(1 for r in rows if r[1] == ft)} features")
        messages.addMessage(f"Total polygon features built: {len(rows)}")

        out_fc = os.path.join(output_loc, output_name)
        if arcpy.Exists(out_fc):
            arcpy.management.Delete(out_fc)
        arcpy.management.CreateFeatureclass(output_loc, output_name, "POLYGON", spatial_reference=sr_wgs84)
        arcpy.management.AddField(out_fc, "fclass", "TEXT", field_length=50,  field_alias="Feature Type")
        arcpy.management.AddField(out_fc, "name",   "TEXT", field_length=255, field_alias="Name")

        with arcpy.da.InsertCursor(out_fc, ["SHAPE@", "fclass", "name"]) as cur:
            for (geom, fclass, name) in rows:
                cur.insertRow((geom, fclass[:50] if fclass else "", name[:255] if name else ""))

        count = int(arcpy.management.GetCount(out_fc)[0])
        messages.addMessage(f"Successfully created: {out_fc} with {count} features.")

        if do_join and join_target:
            out_fc = _run_spatial_join(out_fc, output_loc, output_name, join_target, join_fields, messages)

        parameters[9].value = out_fc
        if add_to_map:
            _add_to_map(out_fc, messages)
