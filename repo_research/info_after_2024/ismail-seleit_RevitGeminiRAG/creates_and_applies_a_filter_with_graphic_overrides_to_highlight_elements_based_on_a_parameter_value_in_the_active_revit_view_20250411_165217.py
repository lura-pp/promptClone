# Purpose: This script creates and applies a filter with graphic overrides to highlight elements based on a parameter value in the active Revit view.

﻿# Import necessary classes
import clr
clr.AddReference('RevitAPI')
clr.AddReference('System.Collections')
from System.Collections.Generic import List

from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, ElementId, View,
    ParameterFilterElement, ParameterFilterRuleFactory, FilterRule, FilterStringRuleEvaluator, FilterStringContains,
    BuiltInParameter, OverrideGraphicSettings, Color, FillPatternElement, FillPatternTarget
)
from Autodesk.Revit.Exceptions import ArgumentException # Import for potential exception handling

# --- Helper function to find the Solid Fill pattern ---
def find_solid_fill_pattern(doc):
    """Finds the first solid fill pattern element."""
    fill_patterns = FilteredElementCollector(doc).OfClass(FillPatternElement).ToElements()
    for pattern_element in fill_patterns:
        if pattern_element is not None:
            try:
                pattern = pattern_element.GetFillPattern()
                # Check if pattern is not null and is solid fill and drafting type
                if pattern is not None and pattern.IsSolidFill and pattern.Target == FillPatternTarget.Drafting:
                    return pattern_element.Id
            except Exception:
                continue # Ignore patterns that cause errors
    return ElementId.InvalidElementId

# --- Main Script ---

# Get the active view
active_view = doc.ActiveView
if not active_view or not isinstance(active_view, View) or active_view.IsTemplate:
    print("# Error: Active view is not a valid project view or is a view template.")
else:
    # --- Filter Definition ---
    filter_name = "High Priority Walls"
    target_category_id = ElementId(BuiltInCategory.OST_Walls)
    categories = List[ElementId]()
    categories.Add(target_category_id)

    # Rule: Comments parameter contains "URGENT"
    # Use the 'Comments' instance parameter for Walls
    param_id = ElementId(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
    rule_value = "URGENT"
    case_sensitive = False # Typically 'Contains' rules are case-insensitive in Revit UI, mimic that

    # Create the filter rule
    filter_rule = None
    try:
        # Create a "contains" rule for strings
        string_evaluator = FilterStringContains()
        filter_rule = ParameterFilterRuleFactory.CreateRule(param_id, string_evaluator, rule_value)
        # Note: As of some Revit versions, CreateRule with FilterStringContains implicitly handles case-insensitivity.
        # If strict case sensitivity is needed and supported, use FilterStringRuleEvaluator(rule_value, False) or other methods if available.
        # This uses the simpler CreateRule which often defaults to case-insensitive for 'contains'.
    except ArgumentException as ae:
        print("# Error creating filter rule (ArgumentException): {{{{{{{{{{{{{{{{0}}}}}}}}}}}}}}}} - Ensure parameter '{{{{{{{{1}}}}}}}}' is valid for Walls.".format(ae.Message, "ALL_MODEL_INSTANCE_COMMENTS")) # Escaped format
    except Exception as e:
        print("# Error creating filter rule: {{{{{{{{{{{{{{{{0}}}}}}}}}}}}}}}}".format(e)) # Escaped format

    if filter_rule:
        filter_rules = List[FilterRule]() # Use the imported FilterRule base class
        filter_rules.Add(filter_rule)

        # Check if a filter with the same name already exists
        existing_filter = None
        filter_collector = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
        for f in filter_collector:
            if f.Name == filter_name:
                existing_filter = f
                break

        new_filter_id = ElementId.InvalidElementId
        try:
            # Transaction is handled externally
            if existing_filter:
                print("# Filter named '{{{{{{{{}}}}}}}}' already exists. Using existing filter.".format(filter_name)) # Escaped format
                new_filter_id = existing_filter.Id
                # Optional: Update existing filter's rules/categories if needed
                try:
                    existing_filter.SetCategories(categories)
                    existing_filter.SetRules(filter_rules)
                    print("# Updated existing filter '{{{{{{{{}}}}}}}}' categories and rules.".format(filter_name)) # Escaped format
                except Exception as update_e:
                    print("# Error updating existing filter '{{{{{{{{}}}}}}}}': {{{{{{{{}}}}}}}}".format(filter_name, update_e)) # Escaped format
                    new_filter_id = ElementId.InvalidElementId # Prevent proceeding if update fails
            else:
                # Create the Parameter Filter Element
                try:
                    new_filter = ParameterFilterElement.Create(doc, filter_name, categories, filter_rules)
                    new_filter_id = new_filter.Id
                    print("# Created new filter: '{{{{{{{{}}}}}}}}'".format(filter_name)) # Escaped format
                except Exception as create_e:
                    print("# Error creating ParameterFilterElement: {{{{{{{{}}}}}}}}".format(create_e)) # Escaped format

            if new_filter_id != ElementId.InvalidElementId:
                # --- Define Override Settings ---
                solid_fill_id = find_solid_fill_pattern(doc)
                if solid_fill_id == ElementId.InvalidElementId:
                    print("# Warning: Could not find a 'Solid fill' drafting pattern. Cut pattern override will not be applied.")

                # Define override color (Red)
                override_color = Color(255, 0, 0) # Red
                bold_line_weight = 5 # Use a value > 4 for boldness, adjust as needed

                ogs = OverrideGraphicSettings()

                # Apply color to projection lines
                ogs.SetProjectionLineColor(override_color)
                ogs.SetProjectionLineWeight(bold_line_weight)

                # Apply color to cut lines
                ogs.SetCutLineColor(override_color)
                ogs.SetCutLineWeight(bold_line_weight)

                # Apply color to cut pattern (if solid fill found)
                if solid_fill_id != ElementId.InvalidElementId:
                    ogs.SetCutForegroundPatternVisible(True)
                    ogs.SetCutForegroundPatternId(solid_fill_id)
                    ogs.SetCutForegroundPatternColor(override_color)
                else:
                    ogs.SetCutForegroundPatternVisible(False) # Ensure no pattern if not found

                # Optional: Apply color to surface pattern (if desired)
                # if solid_fill_id != ElementId.InvalidElementId:
                #     ogs.SetSurfaceForegroundPatternVisible(True)
                #     ogs.SetSurfaceForegroundPatternId(solid_fill_id)
                #     ogs.SetSurfaceForegroundPatternColor(override_color)
                # else:
                #     ogs.SetSurfaceForegroundPatternVisible(False)


                # --- Apply Filter and Overrides to Active View ---
                try:
                    # Check if filter is already applied to the view
                    applied_filters = active_view.GetFilters()
                    if new_filter_id not in applied_filters:
                        active_view.AddFilter(new_filter_id)
                        print("# Added filter '{{{{{{{{}}}}}}}}' to view '{{{{{{{{}}}}}}}}'.".format(filter_name, active_view.Name)) # Escaped format
                    else:
                        print("# Filter '{{{{{{{{}}}}}}}}' was already present in view '{{{{{{{{}}}}}}}}'.".format(filter_name, active_view.Name)) # Escaped format

                    # Set the overrides for the filter in the view
                    active_view.SetFilterOverrides(new_filter_id, ogs)
                    # Ensure the filter is enabled (visible)
                    active_view.SetFilterVisibility(new_filter_id, True)
                    print("# Applied graphic overrides for filter '{{{{{{{{}}}}}}}}' in view '{{{{{{{{}}}}}}}}'.".format(filter_name, active_view.Name)) # Escaped format

                except Exception as apply_e:
                    # Check for specific error related to V/G overrides support
                    if "View type does not support Visibility/Graphics Overrides" in str(apply_e):
                         print("# Error: The current view ('{{{{{{{{}}}}}}}}', type: {{{{{{{{}}}}}}}}) does not support Visibility/Graphics Overrides.".format(active_view.Name, active_view.ViewType)) # Escaped format
                    else:
                         print("# Error applying filter or overrides to view '{{{{{{{{}}}}}}}}': {{{{{{{{}}}}}}}}".format(active_view.Name, apply_e)) # Escaped format
        except Exception as outer_e:
            # Catch errors during filter creation/update or applying to view
            print("# An error occurred during filter processing: {{{{{{{{}}}}}}}}".format(outer_e)) # Escaped format
        finally:
            # Transaction commit/rollback handled externally
            pass
    else:
        # Error message already printed during rule creation attempt
        pass