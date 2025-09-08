# Purpose: This script creates a Revit parameter filter element based on specified criteria.

﻿# Import necessary classes
import clr
clr.AddReference("RevitAPI")
clr.AddReference("System.Collections") # Required for List<T>

from Autodesk.Revit.DB import (
    ParameterFilterElement,
    BuiltInCategory,
    ElementId,
    Category,
    FilteredElementCollector,
    ParameterFilterRuleFactory,
    FilterRule,       # Base class for rules
    ElementParameterFilter,
    BuiltInParameter,
    ParameterFilterUtilities,
    ParameterElement, # To inspect parameter definitions
    Definition        # To get BuiltInParameter enum from ParameterElement
    # OverrideGraphicSettings, # Not needed for filter *creation*
    # Color                    # Not needed for filter *creation*
)
from System.Collections.Generic import List

# --- Configuration ---
filter_name = "Primary Beams Highlight"
target_category_bip = BuiltInCategory.OST_StructuralFraming
# Parameter to filter by: Type Comments
param_bip_to_find = BuiltInParameter.ALL_MODEL_TYPE_COMMENTS
# Rule: Contains the string 'Primary' (case-insensitive)
rule_string_value = "Primary"
# The overrides (Red color, Weight 5) are defined when this filter is applied to a View,
# not stored within the ParameterFilterElement itself. This script creates the filter definition.

# --- Get Category Info ---
cat = Category.GetCategory(doc, target_category_bip)

if not cat:
    # Error: Category not found
    print("# Error: Category 'Structural Framing' (OST_StructuralFraming) not found in the document.")
else:
    category_ids = List[ElementId]()
    category_ids.Add(cat.Id)

    # --- Get Parameter Info ---
    # Find the ElementId of the 'Type Comments' parameter among the filterable parameters for the category
    target_param_id = ElementId.InvalidElementId
    try:
        # Get all filterable parameter ElementIds for the given categories
        filterable_param_ids = ParameterFilterUtilities.GetFilterableParametersInCommon(doc, category_ids)

        # Iterate through filterable parameter IDs and find the one matching the desired BuiltInParameter
        for p_id in filterable_param_ids:
            param_elem = doc.GetElement(p_id)
            # Check if it's a ParameterElement before accessing Definition
            if isinstance(param_elem, ParameterElement):
                definition = param_elem.GetDefinition()
                # Check if the definition exists and matches the target BuiltInParameter
                if definition and definition.BuiltInParameter == param_bip_to_find:
                    target_param_id = p_id
                    break # Found the correct parameter ID
    except Exception as param_find_ex:
        print("# Error finding filterable parameters: {}".format(param_find_ex))
        # Ensure target_param_id remains InvalidElementId if error occurs
        target_param_id = ElementId.InvalidElementId

    if target_param_id == ElementId.InvalidElementId:
        # Error: Parameter not found or not filterable
        print("# Error: Parameter 'Type Comments' (BIP: {}) is not found among filterable parameters for category '{}'.".format(param_bip_to_find, target_category_bip))
    else:
        # --- Create Filter Rule ---
        filter_rule = None
        try:
            # Create a "contains" rule, case-insensitive
            # ParameterFilterRuleFactory.CreateContainsRule(parameterId, stringValue, caseSensitive=False)
            filter_rule = ParameterFilterRuleFactory.CreateContainsRule(target_param_id, rule_string_value, False)
        except Exception as rule_ex:
             print("# Error creating filter rule: {}".format(rule_ex))

        if filter_rule:
            # --- Create Element Filter from the rule(s) ---
            element_filter = None
            try:
                rules = List[FilterRule]()
                rules.Add(filter_rule)
                element_filter = ElementParameterFilter(rules)
            except Exception as el_filter_ex:
                print("# Error creating ElementParameterFilter: {}".format(el_filter_ex))

            if element_filter:
                # --- Check for existing filter by name to avoid errors ---
                existing_filter = None
                try:
                    filter_collector = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
                    # Iterate and compare names (case-sensitive comparison)
                    for f in filter_collector:
                        if f.Name == filter_name:
                            existing_filter = f
                            break
                except Exception as collector_ex:
                     print("# Error checking for existing filters: {}".format(collector_ex))

                if existing_filter:
                    # Info: Filter already exists. Script will not create a duplicate.
                    # print("# Info: Filter '{}' already exists (ID: {}). Skipping creation.".format(filter_name, existing_filter.Id))
                    pass # Comply with non-interactive requirements; do nothing if exists
                else:
                    # --- Create the Parameter Filter Element ---
                    try:
                        # The transaction is handled by the external C# wrapper
                        created_filter = ParameterFilterElement.Create(doc, filter_name, category_ids, element_filter)
                        # Success: Filter created. No output needed unless debugging.
                        # print("# Filter '{}' created successfully with ID {}.".format(filter_name, created_filter.Id))
                        # Note on Overrides: The specified overrides (Projection Line Color Red, Line Weight 5)
                        # must be configured separately when this filter is added to a specific view.
                        # Example (for context, not executed here):
                        # ogs = OverrideGraphicSettings()
                        # ogs.SetProjectionLineColor(Color(255, 0, 0))
                        # ogs.SetProjectionLineWeight(5)
                        # view.AddFilter(created_filter.Id)
                        # view.SetFilterOverrides(created_filter.Id, ogs)
                    except Exception as create_ex:
                        # Error: Failed to create the filter
                        print("# Error creating ParameterFilterElement '{}': {}".format(filter_name, create_ex))