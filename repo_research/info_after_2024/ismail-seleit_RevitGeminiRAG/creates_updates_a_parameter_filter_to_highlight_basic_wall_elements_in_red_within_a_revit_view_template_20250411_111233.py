# Purpose: This script creates/updates a parameter filter to highlight 'Basic Wall' elements in red within a Revit view template.

# Purpose: This script creates or updates a parameter filter and applies it to the active view's template, highlighting "Basic Wall" elements in red.

﻿# Import necessary classes
import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI') # Typically needed, though not strictly for this script's logic
clr.AddReference('System.Collections')
from System.Collections.Generic import List

from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, ElementId, View,
    ParameterFilterElement, ParameterFilterRuleFactory, FilterRule,
    BuiltInParameter, OverrideGraphicSettings, Color, FillPatternElement, FillPatternTarget
)
from Autodesk.Revit.Exceptions import ArgumentException # Import for potential exception handling

# --- Helper function to find the Solid Fill pattern ---
def find_solid_fill_pattern(doc):
    """Finds the first solid fill pattern element."""
    # Use FilteredElementCollector for efficiency
    fill_patterns = FilteredElementCollector(doc).OfClass(FillPatternElement).ToElements()
    for pattern_element in fill_patterns:
        if pattern_element is not None:
            try:
                pattern = pattern_element.GetFillPattern()
                # Check if pattern is not null and is solid fill and drafting type
                if pattern is not None and pattern.IsSolidFill and pattern.Target == FillPatternTarget.Drafting:
                    return pattern_element.Id
            except Exception:
                # Handle potential errors getting pattern details, though unlikely for standard patterns
                continue
    return ElementId.InvalidElementId

# --- Main Script ---

# Get the active view (already provided by the execution environment)
active_view = doc.ActiveView
# Corrected: Removed IsTemporaryViewmodeActive check which caused the error
if not active_view or not isinstance(active_view, View):
    print("# Error: No active graphical view found.")
else:
    # Check if the active view has a View Template applied
    template_id = active_view.ViewTemplateId
    if template_id == ElementId.InvalidElementId:
        print("# Error: The active view does not have a View Template applied.")
    else:
        # Get the View Template element (which is also a View)
        template_view = doc.GetElement(template_id)
        if not template_view or not isinstance(template_view, View):
            print("# Error: Could not retrieve the View Template element with ID: {{{{}}}}".format(template_id)) # Escaped format
        else:
            # --- Filter Definition ---
            filter_name = "Color Basic Walls"
            target_category_id = ElementId(BuiltInCategory.OST_Walls)
            categories = List[ElementId]()
            categories.Add(target_category_id)

            # Rule: Family Name equals "Basic Wall"
            # Using ALL_MODEL_FAMILY_NAME which is generally reliable for system families.
            param_id = ElementId(BuiltInParameter.ALL_MODEL_FAMILY_NAME)
            rule_value = "Basic Wall" # Case-sensitive value for the family name

            # Create the filter rule
            filter_rule = None
            try:
                # Use CreateEqualsRule for string comparison
                filter_rule = ParameterFilterRuleFactory.CreateEqualsRule(param_id, rule_value)
            except ArgumentException as ae:
                 print("# Error creating filter rule (ArgumentException): {{{{{{{{0}}}}}}}} - Ensure parameter '{{{{1}}}}' is valid for Walls.".format(ae.Message, "ALL_MODEL_FAMILY_NAME")) # Escaped format
            except Exception as e:
                 print("# Error creating filter rule: {{{{{{{{0}}}}}}}}".format(e)) # Escaped format

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
                t = None # Transaction object placeholder (managed externally)
                try:
                    # Transaction should wrap changes below (handled by external wrapper)
                    if existing_filter:
                        print("# Filter named '{{{{}}}}' already exists. Using existing filter.".format(filter_name)) # Escaped format
                        new_filter_id = existing_filter.Id
                        # Optional: Update existing filter's rules/categories if needed
                        try:
                            existing_filter.SetCategories(categories)
                            existing_filter.SetRules(filter_rules)
                            print("# Updated existing filter '{{{{}}}}' categories and rules.".format(filter_name)) # Escaped format
                        except Exception as update_e:
                            print("# Error updating existing filter '{{{{}}}}': {{{{}}}}".format(filter_name, update_e)) # Escaped format
                            new_filter_id = ElementId.InvalidElementId # Prevent proceeding if update fails
                    else:
                        # Create the Parameter Filter Element
                        try:
                            new_filter = ParameterFilterElement.Create(doc, filter_name, categories, filter_rules)
                            new_filter_id = new_filter.Id
                            print("# Created new filter: '{{{{}}}}'".format(filter_name)) # Escaped format
                        except Exception as create_e:
                            print("# Error creating ParameterFilterElement: {{{{}}}}".format(create_e)) # Escaped format

                    if new_filter_id != ElementId.InvalidElementId:
                        # --- Define Override Settings ---
                        solid_fill_id = find_solid_fill_pattern(doc)
                        if solid_fill_id == ElementId.InvalidElementId:
                            print("# Error: Could not find a 'Solid fill' drafting pattern. Overrides will not be applied.")
                        else:
                            # Define override color (e.g., Red)
                            override_color = Color(255, 0, 0) # Red

                            ogs = OverrideGraphicSettings()
                            # Apply color to surface pattern (projection)
                            ogs.SetSurfaceForegroundPatternVisible(True)
                            ogs.SetSurfaceForegroundPatternId(solid_fill_id)
                            ogs.SetSurfaceForegroundPatternColor(override_color)
                            # Apply color to cut pattern
                            ogs.SetCutForegroundPatternVisible(True)
                            ogs.SetCutForegroundPatternId(solid_fill_id)
                            ogs.SetCutForegroundPatternColor(override_color)
                            # Optional: Set transparency, line weights, etc.
                            # ogs.SetSurfaceTransparency(50) # Example: 50% transparent

                            # --- Apply Filter and Overrides to View Template ---
                            try:
                                # Check if filter is already applied to the template
                                applied_filters = template_view.GetFilters()
                                if new_filter_id not in applied_filters:
                                    template_view.AddFilter(new_filter_id)
                                    print("# Added filter '{{{{}}}}' to view template '{{{{}}}}'.".format(filter_name, template_view.Name)) # Escaped format
                                else:
                                    print("# Filter '{{{{}}}}' was already present in view template '{{{{}}}}'.".format(filter_name, template_view.Name)) # Escaped format

                                # Set the overrides for the filter in the template
                                template_view.SetFilterOverrides(new_filter_id, ogs)
                                # Ensure the filter is enabled (visible)
                                template_view.SetFilterVisibility(new_filter_id, True)
                                print("# Applied graphic overrides for filter '{{{{}}}}' in view template '{{{{}}}}'.".format(filter_name, template_view.Name)) # Escaped format

                            except Exception as apply_e:
                                print("# Error applying filter or overrides to view template '{{{{}}}}': {{{{}}}}".format(template_view.Name, apply_e)) # Escaped format
                except Exception as outer_e:
                    # Catch errors during filter creation/update or applying to template
                    print("# An error occurred during filter processing: {{{{}}}}".format(outer_e)) # Escaped format
                finally:
                    # Transaction commit/rollback handled externally
                    pass
            else:
                # Error message already printed during rule creation attempt
                pass