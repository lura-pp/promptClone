# Purpose: This script creates a Revit filter based on door parameters and applies graphic overrides to the active view.

﻿# Import necessary classes
import clr
clr.AddReference('RevitAPI')
clr.AddReference('System.Collections')
from System.Collections.Generic import List

from Autodesk.Revit.DB import (
    FilteredElementCollector,
    ParameterFilterElement,
    ElementId,
    BuiltInCategory,
    ParameterFilterRuleFactory,
    FilterRule, FilterStringRule, FilterStringGreaterOrEqual, FilterStringContains,
    BuiltInParameter,
    View,
    OverrideGraphicSettings
)
from Autodesk.Revit.Exceptions import ArgumentException # Import for potential exception handling

# --- Configuration ---
filter_name = "Steel Frame Doors - 1hr"
target_category_ids = List[ElementId]()
target_category_ids.Add(ElementId(BuiltInCategory.OST_Doors))

# Rule 1: Fire Rating >= '1 hr'
# Assumption: 'Fire Rating' corresponds to the built-in parameter FIRE_RATING.
# If this is a shared or project parameter, this ID needs to be found differently.
fire_rating_param_id = ElementId(BuiltInParameter.FIRE_RATING)
fire_rating_rule_value = "1 hr"

# Rule 2: Frame Material contains 'Steel'
# Assumption: 'Frame Material' corresponds to the built-in parameter DOOR_FRAME_MATERIAL.
# If this is a shared or project parameter, this ID needs to be found differently.
frame_material_param_id = ElementId(BuiltInParameter.DOOR_FRAME_MATERIAL)
frame_material_rule_value = "Steel"
# Note: FilterStringContains is case-sensitive by default in the API.
# Use 'Steel' or 'steel' depending on expected data format. Assuming 'Steel'.

# Override Settings
projection_line_weight = 4

# --- Main Script ---

# Check if a filter with this name already exists
existing_filter = None
filter_collector = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
for f in filter_collector:
    if f.Name == filter_name:
        existing_filter = f
        break

newly_created = False
target_filter_id = ElementId.InvalidElementId

if existing_filter:
    print("# Filter named '{{}}' already exists.".format(filter_name))
    target_filter_id = existing_filter.Id
    # Optional: Add checks here to see if existing filter rules/categories match
    # and update if necessary (outside the scope of the current request).
else:
    # Create the filter rules
    rules_list = List[FilterRule]()
    rule1_created = False
    rule2_created = False

    try:
        # Rule 1: Fire Rating >= '1 hr'
        fire_rating_evaluator = FilterStringGreaterOrEqual()
        # Note: Comparison is typically case-insensitive for text in Revit filters.
        filter_rule1 = ParameterFilterRuleFactory.CreateFilterRule(fire_rating_param_id, fire_rating_evaluator, fire_rating_rule_value)
        rules_list.Add(filter_rule1)
        rule1_created = True
    except ArgumentException as ae:
        print("# Error creating filter rule 1 (Fire Rating): {{{{}}}} - Ensure parameter 'FIRE_RATING' exists, is Text/String, and applicable to Doors.".format(ae.Message))
    except Exception as e1:
        print("# Error creating filter rule 1 (Fire Rating): {{{{}}}}".format(e1))

    try:
        # Rule 2: Frame Material contains 'Steel'
        frame_material_evaluator = FilterStringContains()
        # Note: FilterStringContains IS case-sensitive. Adjust value if needed.
        filter_rule2 = ParameterFilterRuleFactory.CreateFilterRule(frame_material_param_id, frame_material_evaluator, frame_material_rule_value)
        rules_list.Add(filter_rule2)
        rule2_created = True
    except ArgumentException as ae:
        print("# Error creating filter rule 2 (Frame Material): {{{{}}}} - Ensure parameter 'DOOR_FRAME_MATERIAL' exists, is Text/String, and applicable to Doors.".format(ae.Message))
    except Exception as e2:
        print("# Error creating filter rule 2 (Frame Material): {{{{}}}}".format(e2))

    # Create the Parameter Filter Element only if both rules were created successfully
    if rule1_created and rule2_created and rules_list.Count == 2:
        try:
            # Create method with List<FilterRule> implicitly uses AND logic
            new_filter = ParameterFilterElement.Create(doc, filter_name, target_category_ids, rules_list)
            target_filter_id = new_filter.Id
            newly_created = True
            print("# Successfully created filter: '{{}}'".format(filter_name))
            print("#   Applies to: Doors")
            print("#   Rule 1: Fire Rating >= '{{}}'".format(fire_rating_rule_value))
            print("#   Rule 2: Frame Material contains '{{}}'".format(frame_material_rule_value))
        except Exception as create_e:
            print("# Error creating ParameterFilterElement '{{}}': {{{{}}}}".format(filter_name, create_e))
    else:
        print("# Filter creation skipped due to errors in rule creation.")

# Apply filter and overrides to the active view if a filter was found or created
if target_filter_id != ElementId.InvalidElementId:
    active_view = doc.ActiveView
    if active_view and isinstance(active_view, View) and not active_view.IsTemplate and active_view.AreGraphicsOverridesAllowed():
        try:
            # Add filter to view if not already present
            applied_filters = active_view.GetFilters()
            if target_filter_id not in applied_filters:
                active_view.AddFilter(target_filter_id)
                print("# Applied filter '{{}}' to view '{{}}'.".format(filter_name, active_view.Name))
            else:
                 if newly_created: # Only print if we just created it AND it happened to be applied already (unlikely but possible if run twice quickly)
                      print("# Filter '{{}}' was already applied to view '{{}}'.".format(filter_name, active_view.Name))
                 #else: # If filter existed, don't repeatedly print that it's applied.
                 #    pass

            # Set overrides
            override_settings = OverrideGraphicSettings()
            override_settings.SetProjectionLineWeight(projection_line_weight)
            active_view.SetFilterOverrides(target_filter_id, override_settings)

            # Ensure filter is enabled (visible and affecting graphics)
            if not active_view.IsFilterEnabled(target_filter_id):
                 active_view.SetIsFilterEnabled(target_filter_id, True)
            # Optionally ensure visibility if overrides only affect visibility (less common for line weight)
            # if not active_view.GetFilterVisibility(target_filter_id):
            #     active_view.SetFilterVisibility(target_filter_id, True)

            print("# Applied Projection Line Weight override ({}) for filter '{{}}' in view '{{}}'.".format(projection_line_weight, filter_name, active_view.Name))

        except Exception as apply_override_err:
            print("# Error applying filter or overrides to view '{{}}': {{{{}}}}".format(active_view.Name, apply_override_err))
    elif newly_created:
        print("# Filter '{{}}' created, but no active valid view to apply overrides to.".format(filter_name))
    # If filter existed and no valid view, don't print anything extra.

elif not existing_filter: # Only print if we failed to create it
     print("# Filter '{{}}' could not be created or found.".format(filter_name))