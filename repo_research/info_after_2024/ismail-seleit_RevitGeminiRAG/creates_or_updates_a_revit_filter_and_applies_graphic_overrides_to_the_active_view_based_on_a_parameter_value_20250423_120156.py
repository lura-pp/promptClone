# Purpose: This script creates or updates a Revit filter and applies graphic overrides to the active view based on a parameter value.

﻿# Import necessary classes
import clr
clr.AddReference('System.Collections')
from System.Collections.Generic import List

clr.AddReference('RevitAPI')
from Autodesk.Revit.DB import (
    ParameterFilterElement,
    ElementParameterFilter,
    FilterRule,
    ParameterFilterRuleFactory,
    FilterStringRuleEvaluator,
    FilterStringContains,
    BuiltInCategory,
    BuiltInParameter,
    OverrideGraphicSettings,
    Color,
    View,
    ElementId
)

# --- Configuration ---
filter_name = "Critical Equipment"
target_category_bic = BuiltInCategory.OST_MechanicalEquipment
parameter_bic = BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS
rule_string_value = "CRITICAL"
case_sensitive_rule = False # Typically better to be case-insensitive for user input

# Override settings
override_color = Color(255, 165, 0) # Orange
override_halftone = True
override_line_weight = 6

# --- Get Category and Parameter IDs ---
category_id = ElementId(target_category_bic)
param_id = ElementId(parameter_bic)

# Check if the parameter exists (basic check)
param_elem = doc.GetElement(param_id)
if not param_elem:
    print("# Error: BuiltInParameter {} not found in the document.".format(parameter_bic))
else:
    # --- Create Filter Rule ---
    # Use FilterStringContains rule evaluator
    fs_evaluator = FilterStringContains()
    # Create the rule: Parameter ID, Evaluator, Value, Case Sensitivity
    filter_rule = ParameterFilterRuleFactory.CreateRule(param_id, fs_evaluator, rule_string_value, case_sensitive_rule)

    # --- Create Element Parameter Filter from the rule ---
    # Use a list as ElementParameterFilter constructor takes IList<FilterRule>
    rules_list = List[FilterRule]()
    rules_list.Add(filter_rule)
    element_filter = ElementParameterFilter(rules_list)

    # --- Define Categories for the filter ---
    category_list = List[ElementId]()
    category_list.Add(category_id)

    # --- Check if Filter already exists ---
    existing_filter = None
    collector = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
    for pf_elem in collector:
        if pf_elem.Name == filter_name:
            existing_filter = pf_elem
            # print("# Info: Filter '{}' already exists. Will update categories and rules.".format(filter_name)) # Optional Info
            break

    # --- Create or Update Parameter Filter Element ---
    if existing_filter:
        filter_element = existing_filter
        # Update categories and filter definition if needed (requires transaction)
        try:
            filter_element.SetCategories(category_list)
            filter_element.SetElementFilter(element_filter)
        except Exception as update_ex:
             # print("# Warning: Failed to update existing filter '{}': {}".format(filter_name, update_ex)) # Optional Warning
             pass # Continue to apply overrides anyway
    else:
        # Create the ParameterFilterElement (requires transaction)
        try:
            filter_element = ParameterFilterElement.Create(doc, filter_name, category_list, element_filter)
            # print("# Info: Created filter '{}'.".format(filter_name)) # Optional Info
        except Exception as create_ex:
            print("# Error: Failed to create filter '{}': {}".format(filter_name, create_ex))
            filter_element = None # Ensure it's None if creation fails

    # --- Apply Filter and Overrides to Active View ---
    if filter_element:
        active_view = doc.ActiveView
        if active_view and isinstance(active_view, View) and not active_view.IsTemplate and active_view.AreGraphicsOverridesAllowed():
            try:
                # Check if filter is already applied to the view
                applied_filter_ids = active_view.GetFilters()
                if filter_element.Id not in applied_filter_ids:
                    # Add the filter to the view (requires transaction)
                    active_view.AddFilter(filter_element.Id)
                    # print("# Info: Added filter '{}' to view '{}'.".format(filter_name, active_view.Name)) # Optional Info

                # --- Create Override Graphic Settings ---
                ogs = OverrideGraphicSettings()
                ogs.SetProjectionLineColor(override_color)
                ogs.SetHalftone(override_halftone)
                ogs.SetProjectionLineWeight(override_line_weight)

                # --- Apply Overrides for the Filter in the View (requires transaction) ---
                active_view.SetFilterOverrides(filter_element.Id, ogs)
                # print("# Info: Applied overrides for filter '{}' in view '{}'.".format(filter_name, active_view.Name)) # Optional Info

            except Exception as view_ex:
                print("# Error: Failed to apply filter/overrides to view '{}': {}".format(active_view.Name, view_ex))
        elif not active_view:
             print("# Error: No active view found.")
        elif not isinstance(active_view, View):
            print("# Error: Active view is not a graphical view.")
        elif active_view.IsTemplate:
            print("# Error: Active view is a template and cannot have filters applied directly.")
        elif not active_view.AreGraphicsOverridesAllowed():
            print("# Error: Graphics overrides are not allowed in the active view.")
    # else:
         # Error message already printed if filter creation failed
         # print("# Info: Filter element was not created or found, cannot apply to view.") # Optional Info
# else part handled above for parameter check