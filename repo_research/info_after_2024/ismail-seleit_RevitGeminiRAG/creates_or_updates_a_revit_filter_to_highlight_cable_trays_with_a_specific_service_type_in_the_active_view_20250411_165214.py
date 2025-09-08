# Purpose: This script creates or updates a Revit filter to highlight cable trays with a specific service type in the active view.

﻿# -*- coding: utf-8 -*-
import clr
clr.AddReference('RevitAPI')
clr.AddReference('RevitAPIUI')
clr.AddReference('System.Collections')
from System.Collections.Generic import List

from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, ElementId, View,
    ParameterFilterElement, ParameterFilterRuleFactory, FilterRule, FilterStringRule, FilterStringEquals,
    BuiltInParameter, OverrideGraphicSettings, Color, FillPatternElement, FillPatternTarget,
    ElementParameterFilter, LogicalAndFilter, Element # Added Element for robust name getting
)
from Autodesk.Revit.Exceptions import ArgumentException

# --- Helper function to find the Solid Fill pattern ---
def find_solid_fill_pattern(doc):
    """Finds the first solid fill drafting pattern element."""
    fill_patterns = FilteredElementCollector(doc).OfClass(FillPatternElement).ToElements()
    for pattern_element in fill_patterns:
        if pattern_element is not None:
            try:
                pattern = pattern_element.GetFillPattern()
                # Check if pattern is valid, IsSolidFill is True, and target is Drafting
                if pattern and pattern.IsSolidFill and pattern.Target == FillPatternTarget.Drafting:
                    return pattern_element.Id
            except Exception:
                # Handle potential errors getting pattern details
                continue
    return ElementId.InvalidElementId

# --- Main Script ---

# Filter Definition
filter_name = "Cable Trays - High Voltage"
# Target category: Cable Trays
target_category_id = ElementId(BuiltInCategory.OST_CableTray)
# Target parameter: Service Type (Assuming BuiltInParameter.RBS_SERVICE_TYPE_PARAM is used as a text parameter)
# If this fails, it might be a shared parameter or RBS_SYSTEM_CLASSIFICATION_PARAM (which requires ElementId comparison)
# Using RBS_SERVICE_TYPE_PARAM as it's often text-based for service type.
target_parameter_id = ElementId(BuiltInParameter.RBS_SERVICE_TYPE_PARAM)
# Target value: "High Voltage" (case-sensitive)
parameter_value = "High Voltage"
# Override color: Bright Red
override_color = Color(255, 0, 0)

# Get the active view
active_view = doc.ActiveView
if not active_view or not isinstance(active_view, View) or active_view.IsTemplate or not active_view.AreGraphicsOverridesAllowed():
    print("# Error: Active view is not valid, is a template, or does not support Visibility/Graphics Overrides.")
else:
    # Prepare categories list
    categories = List[ElementId]()
    categories.Add(target_category_id)

    # Create the filter rule
    filter_rule = None
    rule_error = None
    try:
        # Create a rule: Service Type equals "High Voltage" (case-sensitive string)
        str_evaluator = FilterStringEquals()
        # Use CreateFilterRule for string comparison
        filter_rule = ParameterFilterRuleFactory.CreateFilterRule(target_parameter_id, str_evaluator, parameter_value)

    except ArgumentException as ae:
         # Provide more specific guidance if rule creation fails
         rule_error = "# Error creating filter rule (ArgumentException): {{0}} - Ensure parameter 'Service Type' (BIP {1}) exists, is type Text, and is applicable to Cable Trays.".format(ae.Message, target_parameter_id.IntegerValue)
    except Exception as e:
         rule_error = "# Error creating filter rule: {{0}}".format(e)

    if rule_error:
        print(rule_error)
        # Add a hint about potentially different parameters
        if target_parameter_id.IntegerValue == BuiltInParameter.RBS_SERVICE_TYPE_PARAM.value__:
            print("# Note: If 'Service Type' is not the correct parameter or not Text type, identify the correct parameter (possibly a shared parameter or RBS_SYSTEM_CLASSIFICATION_PARAM).")
            print("# If using RBS_SYSTEM_CLASSIFICATION_PARAM, the rule must compare ElementIds, not strings.")

    if filter_rule:
        filter_rules = List[FilterRule]()
        filter_rules.Add(filter_rule)

        # Check if a filter with the same name already exists
        existing_filter = None
        filter_collector = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
        for f in filter_collector:
             # Use Element.Name.GetValue for robustness against potential null names or errors
             try:
                 f_name = Element.Name.GetValue(f)
                 if f_name == filter_name:
                     existing_filter = f
                     break
             except:
                 pass # Ignore elements where name retrieval fails or throws

        new_filter_id = ElementId.InvalidElementId
        try:
            # Transaction managed externally (by C# wrapper)
            if existing_filter:
                print("# Filter named '{{0}}' already exists. Using existing filter.".format(filter_name))
                new_filter_id = existing_filter.Id
                # Optional: Update existing filter's rules/categories if needed
                try:
                    # Check if categories or rules need updating
                    current_categories = existing_filter.GetCategories()
                    current_rules = existing_filter.GetRules() # Basic rule count check

                    # Simple check if categories differ (more robust check might compare sets/hashes)
                    needs_category_update = True
                    if len(current_categories) == len(categories) and categories[0] in current_categories:
                        needs_category_update = False

                    # Rudimentary rule check (more robust check is complex, involves comparing rule details)
                    needs_rule_update = True
                    if len(current_rules) == len(filter_rules):
                         if current_rules[0].GetRuleParameter() == filter_rules[0].GetRuleParameter():
                              # Basic check: assume if parameter ID matches, it's ok for this simple case.
                              # A full check would compare evaluator, value, etc.
                              needs_rule_update = False

                    if needs_category_update:
                        existing_filter.SetCategories(categories) # Requires transaction
                        print("# Updated existing filter '{{0}}' categories.".format(filter_name))
                    if needs_rule_update:
                         existing_filter.SetRules(filter_rules) # Requires transaction
                         print("# Updated existing filter '{{0}}' rules.".format(filter_name))
                    if not needs_category_update and not needs_rule_update:
                        print("# Existing filter '{{0}}' configuration matches. No update needed.".format(filter_name))

                except Exception as update_e:
                    print("# Error updating existing filter '{{0}}': {{1}}".format(filter_name, update_e))
                    new_filter_id = ElementId.InvalidElementId # Prevent proceeding if update fails
            else:
                # Create the Parameter Filter Element
                try:
                    # ParameterFilterElement.Create handles the logical AND of rules internally
                    new_filter = ParameterFilterElement.Create(doc, filter_name, categories, filter_rules) # Requires transaction
                    new_filter_id = new_filter.Id
                    print("# Created new filter: '{{0}}'".format(filter_name))
                except Exception as create_e:
                    # Handle potential race condition ("name is already in use") or other creation errors
                    if "name is already in use" in str(create_e).lower():
                         # Re-query in case it was created between the check and the create call
                         collector_retry = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
                         for pfe_retry in collector_retry:
                             try:
                                 pfe_retry_name = Element.Name.GetValue(pfe_retry)
                                 if pfe_retry_name == filter_name:
                                     new_filter_id = pfe_retry.Id
                                     print("# Found filter '{{0}}' after creation conflict.".format(filter_name))
                                     break
                             except:
                                 pass
                    else:
                         print("# Error creating ParameterFilterElement: {{0}}".format(create_e))

            if new_filter_id != ElementId.InvalidElementId:
                # Find solid fill pattern
                solid_fill_id = find_solid_fill_pattern(doc)
                if solid_fill_id == ElementId.InvalidElementId:
                    print("# Warning: Could not find a 'Solid fill' drafting pattern. Color override might not be fully visible without a pattern.")

                # --- Define Override Settings ---
                ogs = OverrideGraphicSettings()
                # Apply color to surface pattern (projection)
                ogs.SetSurfaceForegroundPatternColor(override_color)
                if solid_fill_id != ElementId.InvalidElementId:
                    ogs.SetSurfaceForegroundPatternVisible(True)
                    ogs.SetSurfaceForegroundPatternId(solid_fill_id)
                else:
                     ogs.SetSurfaceForegroundPatternVisible(False) # Hide if no pattern

                # Apply color to cut pattern
                ogs.SetCutForegroundPatternColor(override_color)
                if solid_fill_id != ElementId.InvalidElementId:
                     ogs.SetCutForegroundPatternVisible(True)
                     ogs.SetCutForegroundPatternId(solid_fill_id)
                else:
                     ogs.SetCutForegroundPatternVisible(False) # Hide if no pattern

                 # Also set Projection Line color for better visibility when fills aren't dominant
                ogs.SetProjectionLineColor(override_color)
                # Optional: set line weight if needed, e.g., make lines thicker
                # ogs.SetProjectionLineWeight(5)

                # --- Apply Filter and Overrides to Active View ---
                try:
                    # Check if filter is applicable to the view (category must be visible in V/G)
                    if active_view.IsFilterApplicable(new_filter_id):
                        # Check if filter is already added to the view
                        applied_filters = active_view.GetFilters()
                        if new_filter_id not in applied_filters:
                             active_view.AddFilter(new_filter_id) # Requires transaction
                             print("# Added filter '{{0}}' to view '{{1}}'.".format(filter_name, active_view.Name))
                        else:
                             print("# Filter '{{0}}' was already present in view '{{1}}'.".format(filter_name, active_view.Name))

                        # Set the overrides for the filter in the view
                        active_view.SetFilterOverrides(new_filter_id, ogs) # Requires transaction
                        # Ensure the filter is enabled (visible) in the view's filter list
                        active_view.SetFilterVisibility(new_filter_id, True) # Requires transaction
                        print("# Applied graphic overrides for filter '{{0}}' in view '{{1}}'.".format(filter_name, active_view.Name))
                    else:
                        print("# Warning: Filter '{{0}}' is not applicable to the current view '{{1}}' (Category 'Cable Trays' might be hidden in V/G settings).".format(filter_name, active_view.Name))

                except Exception as apply_e:
                     print("# Error applying filter or overrides to view '{{0}}': {{1}}".format(active_view.Name, apply_e))
            else:
                 # Error during filter creation/retrieval
                 print("# Failed to obtain a valid filter ID for '{0}'. Filter was not applied.".format(filter_name))

        except Exception as outer_e:
            # Catch errors during filter creation/update or applying to view steps
            print("# An error occurred during filter processing: {{0}}".format(outer_e))
        finally:
            # Transaction commit/rollback handled externally by C# wrapper
            pass
    else:
        # Error message should have been printed during rule creation attempt
        pass