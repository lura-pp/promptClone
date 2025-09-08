# Purpose: This script creates a Revit parameter filter based on specified rules.

﻿# -*- coding: utf-8 -*-
import clr
clr.AddReference('RevitAPI')
clr.AddReference('System.Collections') # Required for List

# Import necessary Revit API classes
from Autodesk.Revit.DB import (
    FilteredElementCollector, BuiltInCategory, ParameterFilterElement, ElementId,
    ElementParameterFilter, FilterRule, ParameterFilterRuleFactory,
    BuiltInParameter, ParameterFilterUtilities, ParameterElement, Definition,
    Category
)
# Import .NET List
from System.Collections.Generic import List

# --- Configuration ---
filter_name = "Specific Concrete Columns"
target_category_bip = BuiltInCategory.OST_StructuralColumns

# Rule 1: Structural Material contains 'Concrete'
param1_bip = BuiltInParameter.STRUCTURAL_MATERIAL_PARAM
rule1_string_value = "Concrete"

# Rule 2: Type Mark starts with 'C1-'
param2_bip = BuiltInParameter.ALL_MODEL_TYPE_MARK
rule2_string_value = "C1-"

# Note: Overrides (Cut Pattern Solid Red) are applied when adding the filter to a view,
# they are not part of the ParameterFilterElement definition itself.

# --- Get Category Info ---
cat = Category.GetCategory(doc, target_category_bip)

if not cat:
    print("# Error: Category 'Structural Columns' (OST_StructuralColumns) not found in the document.")
else:
    category_ids = List[ElementId]()
    category_ids.Add(cat.Id)

    # --- Find Parameter ElementIds ---
    param1_id = ElementId.InvalidElementId
    param2_id = ElementId.InvalidElementId
    filterable_param_ids = None
    try:
        filterable_param_ids = ParameterFilterUtilities.GetFilterableParametersInCommon(doc, category_ids)
    except Exception as param_find_ex:
        print("# Error finding filterable parameters: {}".format(param_find_ex))

    if filterable_param_ids:
        for p_id in filterable_param_ids:
            param_elem = doc.GetElement(p_id)
            if isinstance(param_elem, ParameterElement):
                definition = param_elem.GetDefinition()
                if definition:
                    if definition.BuiltInParameter == param1_bip:
                        param1_id = p_id
                    elif definition.BuiltInParameter == param2_bip:
                        param2_id = p_id
            if param1_id != ElementId.InvalidElementId and param2_id != ElementId.InvalidElementId:
                break # Found both

    if param1_id == ElementId.InvalidElementId:
        print("# Error: Parameter 'Structural Material' (BIP: {}) is not found among filterable parameters for category '{}'.".format(param1_bip, target_category_bip))
    if param2_id == ElementId.InvalidElementId:
        print("# Error: Parameter 'Type Mark' (BIP: {}) is not found among filterable parameters for category '{}'.".format(param2_bip, target_category_bip))

    # --- Proceed only if both parameters were found ---
    if param1_id != ElementId.InvalidElementId and param2_id != ElementId.InvalidElementId:
        # --- Create Filter Rules ---
        filter_rule1 = None
        filter_rule2 = None
        try:
            # Rule 1: Structural Material contains "Concrete" (case-insensitive by default)
            filter_rule1 = ParameterFilterRuleFactory.CreateContainsRule(param1_id, rule1_string_value)
            # Rule 2: Type Mark begins with "C1-" (case-insensitive by default)
            filter_rule2 = ParameterFilterRuleFactory.CreateBeginsWithRule(param2_id, rule2_string_value)
        except Exception as rule_ex:
             print("# Error creating filter rules: {}".format(rule_ex))

        if filter_rule1 and filter_rule2:
            # --- Combine Rules (Logical AND) ---
            rules = List[FilterRule]()
            rules.Add(filter_rule1)
            rules.Add(filter_rule2)

            # --- Create Element Filter ---
            element_filter = None
            try:
                # ElementParameterFilter with a list of rules implies logical AND
                element_filter = ElementParameterFilter(rules)
            except Exception as el_filter_ex:
                print("# Error creating ElementParameterFilter: {}".format(el_filter_ex))

            if element_filter:
                # --- Check for Existing Filter ---
                existing_filter = None
                try:
                    filter_collector = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
                    for f in filter_collector:
                        if f.Name == filter_name:
                            existing_filter = f
                            break
                except Exception as collector_ex:
                     print("# Error checking for existing filters: {}".format(collector_ex))

                if existing_filter:
                    # print("# Info: Filter '{}' already exists. Skipping creation.".format(filter_name))
                    pass # Filter already exists, do nothing per constraints
                else:
                    # --- Create New Filter ---
                    try:
                        # The transaction is handled by the external C# wrapper
                        if ParameterFilterElement.IsNameUnique(doc, filter_name):
                            created_filter = ParameterFilterElement.Create(doc, filter_name, category_ids, element_filter)
                            # print("# Created new filter: {}".format(filter_name)) # Optional success message
                            # Note: The requested overrides (Cut Pattern Solid Red) need to be applied
                            # separately when adding this filter to a specific view using View.AddFilter()
                            # and View.SetFilterOverrides(). Example:
                            # view = doc.ActiveView
                            # ogs = OverrideGraphicSettings()
                            # solid_fill = FillPatternElement.GetFillPatternElementByName(doc, FillPatternTarget.Drafting, "<Solid fill>")
                            # if solid_fill:
                            #     ogs.SetSurfaceBackgroundPatternId(solid_fill.Id) # Or SetCutBackgroundPatternId
                            #     ogs.SetSurfaceBackgroundPatternColor(Color(255, 0, 0)) # Or SetCutBackgroundPatternColor
                            # view.AddFilter(created_filter.Id)
                            # view.SetFilterOverrides(created_filter.Id, ogs)
                        else:
                            # This case should ideally be caught by the existence check, but added for safety
                            print("# Error: Filter name '{}' is already in use (but wasn't found directly).".format(filter_name))
                    except Exception as create_ex:
                        print("# Error creating ParameterFilterElement '{}': {}".format(filter_name, create_ex))

        elif not (filter_rule1 and filter_rule2):
            print("# Filter creation skipped because one or more rules could not be created.")

    elif filterable_param_ids is None:
         print("# Filter creation skipped due to error retrieving filterable parameters.")
    else: # One or both parameters not found
         print("# Filter creation skipped because required parameters were not found.")