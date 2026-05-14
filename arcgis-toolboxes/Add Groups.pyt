import arcpy

class Toolbox(object):
    def __init__(self):
        self.label = "Custom TOC Tools"
        self.alias = "toctools"
        self.tools = [CreateGroups]

class CreateGroups(object):
    def __init__(self):
        self.label = "Create Group Layers"
        self.description = "Creates group layers with full visibility (no scrolling)."

    def getParameterInfo(self):

        params = []

        def make_param(display, name, default):
            p = arcpy.Parameter(
                displayName=display,
                name=name,
                datatype="GPBoolean",
                parameterType="Optional",
                direction="Input"
            )
            p.value = default
            return p

        params.append(make_param("Settlements", "settlements", True))
        params.append(make_param("Borders", "borders", True))
        params.append(make_param("Cartography", "cartography", True))
        params.append(make_param("Point of Interest", "poi", True))
        params.append(make_param("Situational", "situational", False))
        params.append(make_param("Transport", "transport", True))
        params.append(make_param("Physical", "physical", True))
        params.append(make_param("Landuse", "landuse", True))
        params.append(make_param("Population", "population", False))
        params.append(make_param("Elevation", "elevation", True))
        params.append(make_param("Admin areas", "admin_areas", True))
        params.append(make_param("Processing", "processing", True))

        return params

    def execute(self, parameters, messages):

        group_list = [
            "Settlements",
            "Borders",
            "Cartography",
            "Point of Interest",
            "Situational",
            "Transport",
            "Physical",
            "Landuse",
            "Population",
            "Elevation",
            "Admin areas",
            "Processing"
        ]

        selected_groups = [
            group_list[i] for i, p in enumerate(parameters) if bool(p.value)
        ]

        aprx = arcpy.mp.ArcGISProject("CURRENT")
        m = aprx.activeMap

        for name in reversed(selected_groups):
            m.createGroupLayer(name)
            messages.addMessage(f"Created group: {name}")

        aprx.save()