# -*- coding: utf-8 -*-
"""
NaturalEarth.pyt
ArcGIS Pro Python Toolbox for renaming and clipping Natural Earth data.

Naming convention:
  <prefix>_admn_ad0_py_10m_naturaleathdata_pp_countries
  └──────┘ └────────────────────────────────────────────┘
  user input        looked up from NE_LOOKUP table

Tools:
  1. Rename Natural Earth Data
  2. Clip and Rename Natural Earth Data
"""

import arcpy
import os
import re

# ---------------------------------------------------------------------------
# Full lookup table  {input_basename_lower: output_middle_section}
# The user-supplied prefix is prepended at runtime.
# ---------------------------------------------------------------------------
NE_LOOKUP = {
    # ── 10m admin 0 ──────────────────────────────────────────────────────────
    "ne_10m_admin_0_antarctic_claims":                          "admn_ad0_py_10m_naturaleathdata_pp_antarctic_claims",
    "ne_10m_admin_0_antarctic_claim_limit_lines":               "admn_ad0_ln_10m_naturaleathdata_pp_antarctic_claim_limits",
    "ne_10m_admin_0_boundary_lines_disputed_areas":             "admn_ad0_ln_10m_naturaleathdata_pp_disputed_areas",
    "ne_10m_admin_0_boundary_lines_land":                       "admn_ad0_ln_10m_naturaleathdata_pp_borders",
    "ne_10m_admin_0_boundary_lines_map_units":                  "admn_ad0_ln_10m_naturaleathdata_pp_map_units",
    "ne_10m_admin_0_boundary_lines_maritime_indicator":         "admn_ad0_ln_10m_naturaleathdata_pp_maritime_indicator",
    "ne_10m_admin_0_boundary_lines_maritime_indicator_chn":     "admn_ad0_ln_10m_naturaleathdata_pp_maritime_indicator_chn",
    "ne_10m_admin_0_countries":                                 "admn_ad0_py_10m_naturaleathdata_pp_countries",
    "ne_10m_admin_0_countries_arg":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_arg",
    "ne_10m_admin_0_countries_bdg":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_bdg",
    "ne_10m_admin_0_countries_bra":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_bra",
    "ne_10m_admin_0_countries_chn":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_chn",
    "ne_10m_admin_0_countries_deu":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_deu",
    "ne_10m_admin_0_countries_egy":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_egy",
    "ne_10m_admin_0_countries_esp":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_esp",
    "ne_10m_admin_0_countries_fra":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_fra",
    "ne_10m_admin_0_countries_gbr":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_gbr",
    "ne_10m_admin_0_countries_grc":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_grc",
    "ne_10m_admin_0_countries_idn":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_idn",
    "ne_10m_admin_0_countries_ind":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_ind",
    "ne_10m_admin_0_countries_iso":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_iso",
    "ne_10m_admin_0_countries_isr":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_isr",
    "ne_10m_admin_0_countries_ita":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_ita",
    "ne_10m_admin_0_countries_jpn":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_jpn",
    "ne_10m_admin_0_countries_kor":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_kor",
    "ne_10m_admin_0_countries_lakes":                           "admn_ad0_py_10m_naturaleathdata_pp_countries_lakes",
    "ne_10m_admin_0_countries_mar":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_mar",
    "ne_10m_admin_0_countries_nep":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_nep",
    "ne_10m_admin_0_countries_nld":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_nld",
    "ne_10m_admin_0_countries_pak":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_pak",
    "ne_10m_admin_0_countries_pol":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_pol",
    "ne_10m_admin_0_countries_prt":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_prt",
    "ne_10m_admin_0_countries_pse":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_pse",
    "ne_10m_admin_0_countries_rus":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_rus",
    "ne_10m_admin_0_countries_sau":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_sau",
    "ne_10m_admin_0_countries_swe":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_swe",
    "ne_10m_admin_0_countries_tlc":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_tlc",
    "ne_10m_admin_0_countries_tur":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_tur",
    "ne_10m_admin_0_countries_twn":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_twn",
    "ne_10m_admin_0_countries_ukr":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_ukr",
    "ne_10m_admin_0_countries_usa":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_usa",
    "ne_10m_admin_0_countries_vnm":                             "admn_ad0_py_10m_naturaleathdata_pp_countries_vnm",
    "ne_10m_admin_0_disputed_areas":                            "admn_ad0_py_10m_naturaleathdata_pp_disputed_areas",
    "ne_10m_admin_0_disputed_areas_scale_rank_minor_islands":   "admn_ad0_py_10m_naturaleathdata_pp_disputed_areas_scale_rank_minor_islands",
    "ne_10m_admin_0_label_points":                              "admn_ad0_py_10m_naturaleathdata_pp_labels",
    "ne_10m_admin_0_map_subunits":                              "admn_ad0_py_10m_naturaleathdata_pp_map_subunits",
    "ne_10m_admin_0_map_units":                                 "admn_ad0_py_10m_naturaleathdata_pp_map_units",
    "ne_10m_admin_0_names":                                     "admn_ad0_py_10m_naturaleathdata_pp_names",
    "ne_10m_admin_0_pacific_groupings":                         "admn_ad0_py_10m_naturaleathdata_pp_pacific_groupings",
    "ne_10m_admin_0_scale_rank":                                "admn_ad0_py_10m_naturaleathdata_pp_scale_rank",
    "ne_10m_admin_0_scale_rank_minor_islands":                  "admn_ad0_py_10m_naturaleathdata_pp_scale_rank_minor_islands",
    "ne_10m_admin_0_seams":                                     "admn_ad0_py_10m_naturaleathdata_pp_seams",
    "ne_10m_admin_0_sovereignty":                               "admn_ad0_py_10m_naturaleathdata_pp_sovereignty",
    # ── 10m admin 1 ──────────────────────────────────────────────────────────
    "ne_10m_admin_1_label_points":                              "admn_ad1_pt_10m_naturaleathdata_pp_labels",
    "ne_10m_admin_1_label_points_details":                      "admn_ad1_pt_10m_naturaleathdata_pp_labels_details",
    "ne_10m_admin_1_seams":                                     "admn_ad1_py_10m_naturaleathdata_pp_seams",
    "ne_10m_admin_1_states_provinces":                          "admn_ad1_py_10m_naturaleathdata_pp_states_provinces",
    "ne_10m_admin_1_states_provinces_lakes":                    "admn_ad1_py_10m_naturaleathdata_pp_states_provinces_lakes",
    "ne_10m_admin_1_states_provinces_lines":                    "admn_ad1_ln_10m_naturaleathdata_pp_states_provinces_lines",
    "ne_10m_admin_1_states_provinces_scale_rank":               "admn_ad1_py_10m_naturaleathdata_pp_states_provinces_scale_rank",
    "ne_10m_admin_1_states_provinces_scale_rank_minor_islands": "admn_ad1_py_10m_naturaleathdata_pp_states_provinces_scale_rank_minor_islands",
    # ── 10m admin 2 ──────────────────────────────────────────────────────────
    "ne_10m_admin_2_counties":                                  "admn_ad2_py_10m_naturaleathdata_pp_counties",
    "ne_10m_admin_2_counties_lakes":                            "admn_ad2_py_10m_naturaleathdata_pp_counties_lakes",
    "ne_10m_admin_2_counties_lines":                            "admn_ad2_ln_10m_naturaleathdata_pp_counties_lines",
    "ne_10m_admin_2_counties_scale_rank":                       "admn_ad2_py_10m_naturaleathdata_pp_counties_scale_rank",
    "ne_10m_admin_2_counties_scale_rank_minor_islands":         "admn_ad2_py_10m_naturaleathdata_pp_counties_scale_rank_minor_islands",
    "ne_10m_admin_2_counties_to_match":                         "admn_ad2_py_10m_naturaleathdata_pp_counties_to_match",
    "ne_10m_admin_2_label_points":                              "admn_ad2_pt_10m_naturaleathdata_pp_labels",
    "ne_10m_admin_2_label_points_details":                      "admn_ad2_pt_10m_naturaleathdata_pp_labels_details",
    # ── 10m transport / cultural ─────────────────────────────────────────────
    "ne_10m_airports":                                          "trans_air_pt_10m_naturaleathdata_pp_airports",
    "ne_10m_parks_and_protected_lands_area":                    "land_res_py_10m_naturaleathdata_pp_parks_and_protected_lands",
    "ne_10m_parks_and_protected_lands_line":                    "land_res_ln_10m_naturaleathdata_pp_parks_and_protected_lands",
    "ne_10m_parks_and_protected_lands_point":                   "land_res_pt_10m_naturaleathdata_pp_parks_and_protected_lands",
    "ne_10m_parks_and_protected_lands_scale_rank":              "land_res_py_10m_naturaleathdata_pp_parks_and_protected_lands_scale_rank",
    "ne_10m_populated_places":                                  "stle_ste_pt_10m_naturaleathdata_pp_populated_places",
    "ne_10m_populated_places_simple":                           "stle_ste_pt_10m_naturaleathdata_pp_populated_places_simple",
    "ne_10m_ports":                                             "tran_sea_pt_10m_naturaleathdata_pp_ports",
    "ne_10m_railroads":                                         "tran_rrd_ln_10m_naturaleathdata_pp_railroads",
    "ne_10m_railroads_north_america":                           "tran_rrd_ln_10m_naturaleathdata_pp_railroads_north_america",
    "ne_10m_roads":                                             "tran_rds_ln_10m_naturaleathdata_pp_roads",
    "ne_10m_roads_north_america":                               "tran_rds_ln_10m_naturaleathdata_pp_roads_north_america",
    "ne_10m_time_zones":                                        "land_tzn_py_10m_naturaleathdata_pp_time_zones",
    "ne_10m_urban_areas":                                       "land_urb_py_10m_naturaleathdata_pp_urbans",
    "ne_10m_urban_areas_landscan":                              "land_urb_py_10m_naturaleathdata_pp_urbans_landscan",
    # ── 10m physical ─────────────────────────────────────────────────────────
    "ne_10m_antarctic_ice_shelves_lines":                       "phys_ice_ln_10m_naturaleathdata_pp_antarctic_ice_shelves",
    "ne_10m_antarctic_ice_shelves_polys":                       "phys_ice_py_10m_naturaleathdata_pp_antarctic_ice_shelves",
    "ne_10m_coastline":                                         "elev_cst_ln_10m_naturaleathdata_pp_coastline",
    "ne_10m_geographic_lines":                                  "carto_equ_ln_10m_naturaleathdata_pp_geographic",
    "ne_10m_geography_marine_polys":                            "phys_ocn_py_10m_naturaleathdata_pp_geography_marine",
    "ne_10m_geography_regions_elevation_points":                "elev_pek_pt_10m_naturaleathdata_pp_geography_regions_elevation",
    "ne_10m_geography_regions_points":                          "phys_reg_pt_10m_naturaleathdata_pp_geography_regions",
    "ne_10m_glaciated_areas":                                   "phys_ice_py_10m_naturaleathdata_pp_glaciated_areas",
    "ne_10m_lakes":                                             "phys_wat_py_10m_naturaleathdata_pp_lakes",
    "ne_10m_lakes_australia":                                   "phys_wat_py_10m_naturaleathdata_pp_lakes_australia",
    "ne_10m_lakes_europe":                                      "phys_wat_py_10m_naturaleathdata_pp_lakes_europe",
    "ne_10m_lakes_historic":                                    "phys_wat_py_10m_naturaleathdata_pp_lakes_historic",
    "ne_10m_lakes_north_america":                               "phys_wat_py_10m_naturaleathdata_pp_lakes_north_america",
    "ne_10m_lakes_pluvial":                                     "phys_wat_py_10m_naturaleathdata_pp_lakes_pluvial",
    "ne_10m_land":                                              "admn_reg_py_10m_naturaleathdata_pp_land",
    "ne_10m_land_ocean_label_points":                           "phys_ocn_pt_10m_naturaleathdata_pp_land_ocean_labels",
    "ne_10m_land_ocean_seams":                                  "phys_ocn_py_10m_naturaleathdata_pp_land_ocean_seams",
    "ne_10m_land_scale_rank":                                   "admn_reg_py_10m_naturaleathdata_pp_land_scale_rank",
    "ne_10m_land_scale_rank2":                                  "admn_reg_py_10m_naturaleathdata_pp_land_scale_rank2",
    "ne_10m_minor_islands":                                     "admn_isl_py_10m_naturaleathdata_pp_minor_islands",
    "ne_10m_minor_islands2":                                    "admn_isl_py_10m_naturaleathdata_pp_minor_islands2",
    "ne_10m_minor_islands_coastline":                           "elev_cst_ln_10m_naturaleathdata_pp_minor_islands_coastline",
    "ne_10m_minor_islands_label_points":                        "admn_isl_pt_10m_naturaleathdata_pp_minor_islands_labels",
    "ne_10m_ocean":                                             "phys_ocn_py_10m_naturaleathdata_pp_ocean",
    "ne_10m_ocean_scale_rank":                                  "phys_ocn_py_10m_naturaleathdata_pp_ocean_scale_rank",
    "ne_10m_playas":                                            "phys_ply_py_10m_naturaleathdata_pp_playas",
    "ne_10m_reefs":                                             "phys_ref_py_10m_naturaleathdata_pp_reefs",
    "ne_10m_rivers_australia":                                  "phys_riv_ln_10m_naturaleathdata_pp_rivers_australia",
    "ne_10m_rivers_europe":                                     "phys_riv_ln_10m_naturaleathdata_pp_rivers_europe",
    "ne_10m_rivers_lake_centerlines":                           "phys_riv_ln_10m_naturaleathdata_pp_rivers_lake_centerlines",
    "ne_10m_rivers_lake_centerlines_scale_rank":                "phys_riv_ln_10m_naturaleathdata_pp_rivers_lake_centerlines_scale_rank",
    "ne_10m_rivers_north_america":                              "phys_riv_ln_10m_naturaleathdata_pp_rivers_north_america",
    # ── 10m bathymetry ───────────────────────────────────────────────────────
    "ne_10m_bathymetry_a_10000":                                "elev_bat_py_10m_naturaleathdata_pp_bathymetry_a_10000",
    "ne_10m_bathymetry_b_9000":                                 "elev_bat_py_10m_naturaleathdata_pp_bathymetry_b_9000",
    "ne_10m_bathymetry_c_8000":                                 "elev_bat_py_10m_naturaleathdata_pp_bathymetry_c_8000",
    "ne_10m_bathymetry_d_7000":                                 "elev_bat_py_10m_naturaleathdata_pp_bathymetry_d_7000",
    "ne_10m_bathymetry_e_6000":                                 "elev_bat_py_10m_naturaleathdata_pp_bathymetry_e_6000",
    "ne_10m_bathymetry_f_5000":                                 "elev_bat_py_10m_naturaleathdata_pp_bathymetry_f_5000",
    "ne_10m_bathymetry_g_4000":                                 "elev_bat_py_10m_naturaleathdata_pp_bathymetry_g_4000",
    "ne_10m_bathymetry_h_3000":                                 "elev_bat_py_10m_naturaleathdata_pp_bathymetry_h_3000",
    "ne_10m_bathymetry_i_2000":                                 "elev_bat_py_10m_naturaleathdata_pp_bathymetry_i_2000",
    "ne_10m_bathymetry_j_1000":                                 "elev_bat_py_10m_naturaleathdata_pp_bathymetry_j_1000",
    "ne_10m_bathymetry_k_200":                                  "elev_bat_py_10m_naturaleathdata_pp_bathymetry_k_200",
    "ne_10m_bathymetry_l_0":                                    "elev_bat_py_10m_naturaleathdata_pp_bathymetry_l_0",
    # ── 10m graticules / cartographic ────────────────────────────────────────
    "ne_10m_graticules_1":                                      "carto_grt_py_10m_naturaleathdata_pp_graticules_1",
    "ne_10m_graticules_5":                                      "carto_grt_py_10m_naturaleathdata_pp_graticules_5",
    "ne_10m_graticules_10":                                     "carto_grt_py_10m_naturaleathdata_pp_graticules_10",
    "ne_10m_graticules_15":                                     "carto_grt_py_10m_naturaleathdata_pp_graticules_15",
    "ne_10m_graticules_20":                                     "carto_grt_py_10m_naturaleathdata_pp_graticules_20",
    "ne_10m_graticules_30":                                     "carto_grt_py_10m_naturaleathdata_pp_graticules_30",
    "ne_10m_wgs84_bounding_box":                                "carto_grt_py_10m_naturaleathdata_pp_wgs84_bounding_box",
    # ── 110m ─────────────────────────────────────────────────────────────────
    "ne_110m_admin_0_boundary_lines_land":                      "admn_ad0_ln_110m_naturaleathdata_pp_boundary_lines_land",
    "ne_110m_admin_0_countries":                                "admn_ad0_py_110m_naturaleathdata_pp_countries",
    "ne_110m_admin_0_countries_lakes":                          "admn_ad0_py_110m_naturaleathdata_pp_countries_lakes",
    "ne_110m_admin_0_map_units":                                "admn_ad0_py_110m_naturaleathdata_pp_map_units",
    "ne_110m_admin_0_pacific_groupings":                        "admn_ad0_py_110m_naturaleathdata_pp_pacific_groupings",
    "ne_110m_admin_0_scale_rank":                               "admn_ad0_py_110m_naturaleathdata_pp_scale_rank",
    "ne_110m_admin_0_sovereignty":                              "admn_ad0_py_110m_naturaleathdata_pp_sovereignty",
    "ne_110m_admin_0_tiny_countries":                           "admn_ad0_py_110m_naturaleathdata_pp_tiny_countries",
    "ne_110m_admin_1_states_provinces":                         "admn_ad1_py_110m_naturaleathdata_pp_states_provinces",
    "ne_110m_admin_1_states_provinces_lakes":                   "admn_ad1_py_110m_naturaleathdata_pp_states_provinces_lakes",
    "ne_110m_admin_1_states_provinces_lines":                   "admn_ad1_ln_110m_naturaleathdata_pp_states_provinces_lines",
    "ne_110m_admin_1_states_provinces_scale_rank":              "admn_ad1_py_110m_naturaleathdata_pp_states_provinces_scale_rank",
    "ne_110m_populated_places":                                 "stle_ste_pt_110m_naturaleathdata_pp_populated_places",
    "ne_110m_populated_places_simple":                          "stle_ste_pt_110m_naturaleathdata_pp_populated_places_simple",
    "ne_110m_coastline":                                        "elev_cst_ln_110m_naturaleathdata_pp_coastline",
    "ne_110m_geographic_lines":                                 "carto_equ_ln_110m_naturaleathdata_pp_geographic",
    "ne_110m_geography_marine_polys":                           "phys_ocn_py_110m_naturaleathdata_pp_geography_marine",
    "ne_110m_geography_regions_elevation_points":               "elev_pek_ln_110m_naturaleathdata_pp_geography_regions_elevation",
    "ne_110m_geography_regions_points":                         "land_reg_pt_110m_naturaleathdata_pp_geography_regions",
    "ne_110m_geography_regions_polys":                          "land_reg_py_110m_naturaleathdata_pp_geography_regions",
    "ne_110m_glaciated_areas":                                  "phys_ice_py_110m_naturaleathdata_pp_glaciated_areas",
    "ne_110m_lakes":                                            "phys_wat_py_110m_naturaleathdata_pp_lakes",
    "ne_110m_land":                                             "admn_reg_py_110m_naturaleathdata_pp_land",
    "ne_110m_ocean":                                            "phys_wat_py_110m_naturaleathdata_pp_ocean",
    "ne_110m_rivers_lake_centerlines":                          "phys_riv_ln_110m_naturaleathdata_pp_rivers_lake_centerlines",
    "ne_110m_graticules_all":                                   "carto_grt_ln_110m_naturaleathdata_pp_graticules_all",
    "ne_110m_graticules_1":                                     "carto_grt_ln_110m_naturaleathdata_pp_graticules_1",
    "ne_110m_graticules_5":                                     "carto_grt_ln_110m_naturaleathdata_pp_graticules_5",
    "ne_110m_graticules_10":                                    "carto_grt_ln_110m_naturaleathdata_pp_graticules_10",
    "ne_110m_graticules_15":                                    "carto_grt_ln_110m_naturaleathdata_pp_graticules_15",
    "ne_110m_graticules_20":                                    "carto_grt_ln_110m_naturaleathdata_pp_graticules_20",
    "ne_110m_graticules_30":                                    "carto_grt_ln_110m_naturaleathdata_pp_graticules_30",
    "ne_110m_wgs84_bounding_box":                               "carto_grt_ln_110m_naturaleathdata_pp_wgs84_bounding_box",
    # ── 50m ──────────────────────────────────────────────────────────────────
    "ne_50m_admin_0_boundary_lines_disputed_areas":             "admn_ad0_ln_50m_naturaleathdata_pp_disputed_areas",
    "ne_50m_admin_0_boundary_lines_land":                       "admn_ad0_ln_50m_naturaleathdata_pp_borders",
    "ne_50m_admin_0_boundary_lines_maritime_indicator":         "admn_ad0_ln_50m_naturaleathdata_pp_maritime_indicator",
    "ne_50m_admin_0_boundary_lines_maritime_indicator_chn":     "admn_ad0_ln_50m_naturaleathdata_pp_maritime_indicator_chn",
    "ne_50m_admin_0_boundary_map_units":                        "admn_ad0_py_50m_naturaleathdata_pp_map_units",
    "ne_50m_admin_0_breakaway_disputed_areas":                  "admn_ad0_py_50m_naturaleathdata_pp_disputed_areas",
    "ne_50m_admin_0_breakaway_disputed_areas_scale_rank":       "admn_ad0_py_50m_naturaleathdata_pp_disputed_areas_scale_rank",
    "ne_50m_admin_0_countries":                                 "admn_ad0_py_50m_naturaleathdata_pp_countries",
    "ne_50m_admin_0_countries_lakes":                           "admn_ad0_py_50m_naturaleathdata_pp_countries_lakes",
    "ne_50m_admin_0_disputed_areas":                            "admn_ad0_py_50m_naturaleathdata_pp_disputed_areas",
    "ne_50m_admin_0_map_subunits":                              "admn_ad0_py_50m_naturaleathdata_pp_map_subunits",
    "ne_50m_admin_0_map_units":                                 "admn_ad0_py_50m_naturaleathdata_pp_map_units",
    "ne_50m_admin_0_pacific_groupings":                         "admn_ad0_py_50m_naturaleathdata_pp_pacific_groupings",
    "ne_50m_admin_0_scale_rank":                                "admn_ad0_py_50m_naturaleathdata_pp_scale_rank",
    "ne_50m_admin_0_sovereignty":                               "admn_ad0_py_50m_naturaleathdata_pp_sovereignty",
    "ne_50m_admin_0_tiny_countries":                            "admn_ad0_py_50m_naturaleathdata_pp_tiny_countries",
    "ne_50m_admin_0_tiny_countries_scale_rank":                 "admn_ad0_py_50m_naturaleathdata_pp_tiny_countries_scale_rank",
    "ne_50m_admin_1_seams":                                     "admn_ad1_py_50m_naturaleathdata_pp_seams",
    "ne_50m_admin_1_states_provinces":                          "admn_ad1_py_50m_naturaleathdata_pp_states_provinces",
    "ne_50m_admin_1_states_provinces_lakes":                    "admn_ad1_py_50m_naturaleathdata_pp_states_provinces_lakes",
    "ne_50m_admin_1_states_provinces_lines":                    "admn_ad1_ln_50m_naturaleathdata_pp_states_provinces_lines",
    "ne_50m_admin_1_states_provinces_scale_rank":               "admn_ad1_py_50m_naturaleathdata_pp_states_provinces_scale_rank",
    "ne_50m_airports":                                          "tran_air_pt_50m_naturaleathdata_pp_airports",
    "ne_50m_populated_places":                                  "stle_ste_pt_50m_naturaleathdata_pp_populated_places",
    "ne_50m_populated_places_simple":                           "stle_ste_pt_50m_naturaleathdata_pp_populated_places_simple",
    "ne_50m_ports":                                             "tran_sea_pt_50m_naturaleathdata_pp_ports",
    "ne_50m_urban_areas":                                       "land_urb_py_50m_naturaleathdata_pp_urban_areas",
    "ne_50m_antarctic_ice_shelves_lines":                       "phys_ice_ln_50m_naturaleathdata_pp_antarctic_ice_shelves_lines",
    "ne_50m_antarctic_ice_shelves_polys":                       "phys_ice_py_50m_naturaleathdata_pp_antarctic_ice_shelves_polys",
    "ne_50m_coastline":                                         "elev_cst_ln_50m_naturaleathdata_pp_coastline",
    "ne_50m_geographic_lines":                                  "carto_equ_ln_50m_naturaleathdata_pp_geographic_lines",
    "ne_50m_geography_marine_polys":                            "phys_ocn_py_50m_naturaleathdata_pp_marine_polys",
    "ne_50m_geography_regions_elevation_points":                "phys_pek_pt_50m_naturaleathdata_pp_regions_elevation_points",
    "ne_50m_geography_regions_points":                          "land_reg_pt_50m_naturaleathdata_pp_regions_points",
    "ne_50m_geography_regions_polys":                           "land_reg_py_50m_naturaleathdata_pp_regions_polys",
    "ne_50m_glaciated_areas":                                   "phys_ice_py_50m_naturaleathdata_pp_glaciated_areas",
    "ne_50m_lakes":                                             "phys_wat_py_50m_naturaleathdata_pp_lakes",
    "ne_50m_lakes_historic":                                    "phys_wat_py_50m_naturaleathdata_pp_lakes_historic",
    "ne_50m_land":                                              "admn_reg_py_50m_naturaleathdata_pp_land",
    "ne_50m_ocean":                                             "phys_ocn_py_50m_naturaleathdata_pp_ocean",
    "ne_50m_playas":                                            "phys_ply_py_50m_naturaleathdata_pp_playas",
    "ne_50m_rivers_lake_centerlines":                           "phys_riv_ln_50m_naturaleathdata_pp_rivers_lake_centerlines",
    "ne_50m_rivers_lake_centerlines_scale_rank":                "phys_riv_ln_50m_naturaleathdata_pp_rivers_lake_centerlines_scale_rank",
    "ne_50m_graticules_1":                                      "carto_grt_ln_50m_naturaleathdata_pp_graticules_1",
    "ne_50m_graticules_5":                                      "carto_grt_ln_50m_naturaleathdata_pp_graticules_5",
    "ne_50m_graticules_10":                                     "carto_grt_ln_50m_naturaleathdata_pp_graticules_10",
    "ne_50m_graticules_15":                                     "carto_grt_ln_50m_naturaleathdata_pp_graticules_15",
    "ne_50m_graticules_20":                                     "carto_grt_ln_50m_naturaleathdata_pp_graticules_20",
    "ne_50m_graticules_30":                                     "carto_grt_ln_50m_naturaleathdata_pp_graticules_30",
    "ne_50m_wgs84_bounding_box":                                "carto_grt_ln_50m_naturaleathdata_pp_wgs84_bounding_box",
    # ── 7m (vector tiles / large-scale) ──────────────────────────────────────
    "admin0-lines":         "admn_ad0_ln_7m_naturaleathdata_pp_admin0_lines",
    "admin0-polygons":      "admn_ad0_py_7m_naturaleathdata_pp_admin0_polygons",
    "admin1-lines":         "admn_ad1_ln_7m_naturaleathdata_pp_admin1_lines",
    "admin1-polygons":      "admn_ad1_py_7m_naturaleathdata_pp_admin1_polygons",
    "airports":             "tran_air_pt_7m_naturaleathdata_pp_airports",
    "bounding-box":         "carto_bdb_py_7m_naturaleathdata_pp_bounding_box",
    "coast":                "elev_cst_pt_7m_naturaleathdata_pp_coast",
    "coral-reefs":          "phys_ref_py_7m_naturaleathdata_pp_coral_reefs",
    "elev-points-conus":    "elev_pek_pt_7m_naturaleathdata_pp_elev_points_conus",
    "elev-points-world":    "elev_pek_pt_7m_naturaleathdata_pp_elev_points_world",
    "glaciers":             "phys_ice_py_7m_naturaleathdata_pp_glaciers",
    "ice-shelf-area":       "phys_ice_py_7m_naturaleathdata_pp_ice_shelf_area",
    "ice-shelf-line":       "phys_ice_ln_7m_naturaleathdata_pp_ice_shelf_line",
    "lakes":                "phys_wat_py_7m_naturaleathdata_pp_lakes",
    "land":                 "admn_reg_py_7m_naturaleathdata_pp_land",
    "ocean":                "phys_ocn_py_7m_naturaleathdata_pp_ocean",
    "railroads-beta2":      "tran_rrd_ln_7m_naturaleathdata_pp_railroads_beta2",
    "rivers":               "phys_riv_ln_7m_naturaleathdata_pp_rivers",
    "road_ferries-beta2":   "tran_rds_ln_7m_naturaleathdata_pp_road_ferries_beta2",
    "small-islands":        "admn_isl_py_7m_naturaleathdata_pp_small_islands",
    "urban-areas":          "land_urb_py_7m_naturaleathdata_pp_urban_areas",
    "wetlands":             "phys_wet_py_7m_naturaleathdata_pp_wetlands",
    "bathymetry-0m":        "elev_bat_py_7m_naturaleathdata_pp_bathymetry_0m",
    "bathymetry-200m":      "elev_bat_py_7m_naturaleathdata_pp_bathymetry_200m",
    "bathymetry-1000m":     "elev_bat_py_7m_naturaleathdata_pp_bathymetry_1000m",
    "bathymetry-2000m":     "elev_bat_py_7m_naturaleathdata_pp_bathymetry_2000m",
    "bathymetry-3000m":     "elev_bat_py_7m_naturaleathdata_pp_bathymetry_3000m",
    "bathymetry-4000m":     "elev_bat_py_7m_naturaleathdata_pp_bathymetry_4000m",
    "bathymetry-5000m":     "elev_bat_py_7m_naturaleathdata_pp_bathymetry_5000m",
    "bathymetry-6000m":     "elev_bat_py_7m_naturaleathdata_pp_bathymetry_6000m",
    "bathymetry-7000m":     "elev_bat_py_7m_naturaleathdata_pp_bathymetry_7000m",
    "bathymetry-8000m":     "elev_bat_py_7m_naturaleathdata_pp_bathymetry_8000m",
    "bathymetry-9000m":     "elev_bat_py_7m_naturaleathdata_pp_bathymetry_9000m",
    "bathymetry-10000m":    "elev_bat_py_7m_naturaleathdata_pp_bathymetry_10000m",
}

DEFAULT_PREFIX = "geoextent"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def lookup_output_name(input_path, prefix):
    """
    Return (full_output_name, found_in_lookup).
    Strips extension and lowercases before lookup.
    Falls back to a sanitised version of the original basename if not found.
    """
    basename = os.path.splitext(os.path.basename(input_path))[0]
    key      = basename.lower()
    middle   = NE_LOOKUP.get(key)
    if middle:
        return f"{prefix}_{middle}", True
    safe = re.sub(r"[^a-z0-9_]", "_", key).strip("_")
    return f"{prefix}_{safe}", False



def detect_prefix(input_path):
    """
    If the input file already follows the naming convention
    (<prefix>_<middle_section>) return the prefix, otherwise return None.
    e.g. "middle_admn_ad0_py_10m_naturaleathdata_pp_countries" -> "middle"
    """
    basename = os.path.splitext(os.path.basename(input_path))[0].lower()
    # Try splitting off increasingly long prefixes until the remainder
    # matches a known middle section
    for i, ch in enumerate(basename):
        if ch == "_" and i > 0:
            candidate_middle = basename[i+1:]
            if candidate_middle in NE_LOOKUP.values():
                return basename[:i]
    return None

def is_folder_workspace(workspace):
    try:
        return arcpy.Describe(workspace).dataType == "Folder"
    except Exception:
        return False


def resolve_out_path(out_workspace, out_name, folder_ws):
    if folder_ws:
        return os.path.join(out_workspace, out_name + ".shp")
    return os.path.join(out_workspace, out_name)


def try_add_to_map(path):
    try:
        aprx = arcpy.mp.ArcGISProject("CURRENT")
        m    = aprx.activeMap
        if m:
            m.addDataFromPath(path)
            arcpy.AddMessage("  Added to active map.")
    except Exception as e:
        arcpy.AddWarning(f"  Could not add to map: {e}")


def process_layers(in_layers, out_workspace, prefix, add_to_map, clip_boundary=None):
    """
    Core loop shared by both tools.
    If clip_boundary is provided, clips then renames; otherwise copies and renames.
    Returns (success_count, total_count).
    """
    folder_ws = is_folder_workspace(out_workspace)
    total     = len(in_layers)
    success   = 0

    for i, lyr in enumerate(in_layers, 1):
        lyr_path = lyr.value if hasattr(lyr, "value") else str(lyr)
        arcpy.AddMessage(f"[{i}/{total}] {os.path.basename(lyr_path)}")

        try:
            desc     = arcpy.Describe(lyr_path)
            out_name, found = lookup_output_name(desc.catalogPath, prefix)

            if not found:
                arcpy.AddWarning(
                    f"  '{os.path.basename(lyr_path)}' not in lookup table — "
                    f"fallback name: {out_name}"
                )

            out_path = resolve_out_path(out_workspace, out_name, folder_ws)

            if clip_boundary:
                arcpy.analysis.Clip(
                    in_features       = lyr_path,
                    clip_features     = clip_boundary,
                    out_feature_class = out_path,
                )
            else:
                arcpy.management.CopyFeatures(
                    in_features       = lyr_path,
                    out_feature_class = out_path,
                )

            arcpy.AddMessage(f"  → {out_path}")

            if add_to_map:
                try_add_to_map(out_path)

            success += 1

        except Exception as e:
            arcpy.AddWarning(f"  ✗ Failed: {e}")

    return success, total


# ---------------------------------------------------------------------------
# Toolbox
# ---------------------------------------------------------------------------

class Toolbox:
    def __init__(self):
        self.label       = "Natural Earth Toolbox"
        self.alias       = "NaturalEarth"
        self.description = (
            "Rename or clip-and-rename Natural Earth datasets using a "
            "controlled naming convention. The output prefix (e.g. "
            "'geoextent') is supplied by the user. Both tools accept "
            "a single layer or multiple layers."
        )
        self.tools = [RenameNaturalEarth, ClipRenameNaturalEarth]


# ---------------------------------------------------------------------------
# Shared parameter builders
# ---------------------------------------------------------------------------

def _p_layers(label="Input Natural Earth Layer(s)"):
    p = arcpy.Parameter(
        displayName   = label,
        name          = "in_layers",
        datatype      = ["GPFeatureLayer", "DEFeatureClass"],
        parameterType = "Required",
        direction     = "Input",
        multiValue    = True,
    )
    return p


def _p_prefix():
    p = arcpy.Parameter(
        displayName   = "Output Name Prefix  (e.g. geoextent)",
        name          = "prefix",
        datatype      = "GPString",
        parameterType = "Required",
        direction     = "Input",
    )
    p.value = DEFAULT_PREFIX
    return p


def _p_workspace():
    p = arcpy.Parameter(
        displayName   = "Output Workspace  (folder or geodatabase)",
        name          = "out_workspace",
        datatype      = ["DEWorkspace", "DEFolder"],
        parameterType = "Required",
        direction     = "Input",
    )
    return p


def _p_workspace_derived():
    p = arcpy.Parameter(
        displayName   = "Output Workspace (result)",
        name          = "out_workspace_result",
        datatype      = ["DEWorkspace", "DEFolder"],
        parameterType = "Derived",
        direction     = "Output",
    )
    return p


def _p_add_to_map():
    p = arcpy.Parameter(
        displayName   = "Add Output(s) to Map",
        name          = "add_to_map",
        datatype      = "GPBoolean",
        parameterType = "Optional",
        direction     = "Input",
    )
    p.value = True
    return p


# ---------------------------------------------------------------------------
# Tool 1 – Rename Natural Earth Data
# ---------------------------------------------------------------------------

class RenameNaturalEarth:
    def __init__(self):
        self.label       = "Rename Natural Earth Data"
        self.description = (
            "Copies one or more Natural Earth feature classes to an output "
            "workspace, renaming each using the standard naming convention. "
            "No clipping is performed."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        # 0  input layers
        # 1  prefix
        # 2  output workspace
        # 3  derived output workspace
        # 4  add to map
        return [
            _p_layers(),
            _p_prefix(),
            _p_workspace(),
            _p_workspace_derived(),
            _p_add_to_map(),
        ]

    def updateParameters(self, parameters):
        in_layers = parameters[0]
        prefix    = parameters[1]
        # Only auto-detect when prefix hasn't been manually altered
        if in_layers.value and not prefix.altered:
            try:
                vals = in_layers.values
                if vals:
                    first = vals[0]
                    lyr_path = first.value if hasattr(first, "value") else str(first)
                    desc = arcpy.Describe(lyr_path)
                    detected = detect_prefix(desc.catalogPath)
                    if detected:
                        prefix.value = detected
            except Exception:
                pass
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        in_layers     = parameters[0].values
        prefix        = (parameters[1].valueAsText or DEFAULT_PREFIX).strip()
        out_workspace = parameters[2].valueAsText
        add_to_map    = parameters[4].value

        success, total = process_layers(
            in_layers     = in_layers,
            out_workspace = out_workspace,
            prefix        = prefix,
            add_to_map    = add_to_map,
            clip_boundary = None,
        )

        parameters[3].value = out_workspace
        arcpy.AddMessage(
            f"\nDone: {success}/{total} layer(s) renamed successfully."
        )

    def postExecute(self, parameters):
        return


# ---------------------------------------------------------------------------
# Tool 2 – Clip and Rename Natural Earth Data
# ---------------------------------------------------------------------------

class ClipRenameNaturalEarth:
    def __init__(self):
        self.label       = "Clip and Rename Natural Earth Data"
        self.description = (
            "Clips one or more Natural Earth feature classes to a boundary "
            "polygon and saves each with the standard naming convention."
        )
        self.canRunInBackground = False

    def getParameterInfo(self):
        # 0  input layers
        # 1  clip boundary
        # 2  prefix
        # 3  output workspace
        # 4  derived output workspace
        # 5  add to map

        p_boundary = arcpy.Parameter(
            displayName   = "Clip Boundary",
            name          = "clip_boundary",
            datatype      = ["GPFeatureLayer", "DEFeatureClass"],
            parameterType = "Required",
            direction     = "Input",
        )

        return [
            _p_layers(),
            p_boundary,
            _p_prefix(),
            _p_workspace(),
            _p_workspace_derived(),
            _p_add_to_map(),
        ]

    def updateParameters(self, parameters):
        in_layers = parameters[0]
        prefix    = parameters[2]
        # Only auto-detect when prefix hasn't been manually altered
        if in_layers.value and not prefix.altered:
            try:
                vals = in_layers.values
                if vals:
                    first = vals[0]
                    lyr_path = first.value if hasattr(first, "value") else str(first)
                    desc = arcpy.Describe(lyr_path)
                    detected = detect_prefix(desc.catalogPath)
                    if detected:
                        prefix.value = detected
            except Exception:
                pass
        return

    def updateMessages(self, parameters):
        return

    def execute(self, parameters, messages):
        in_layers     = parameters[0].values
        clip_boundary = parameters[1].valueAsText
        prefix        = (parameters[2].valueAsText or DEFAULT_PREFIX).strip()
        out_workspace = parameters[3].valueAsText
        add_to_map    = parameters[5].value

        success, total = process_layers(
            in_layers     = in_layers,
            out_workspace = out_workspace,
            prefix        = prefix,
            add_to_map    = add_to_map,
            clip_boundary = clip_boundary,
        )

        parameters[4].value = out_workspace
        arcpy.AddMessage(
            f"\nDone: {success}/{total} layer(s) clipped and renamed successfully."
        )

    def postExecute(self, parameters):
        return
