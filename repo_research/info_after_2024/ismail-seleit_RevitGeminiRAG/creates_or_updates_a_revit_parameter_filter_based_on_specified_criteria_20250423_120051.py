# Purpose: This script creates or updates a Revit parameter filter based on specified criteria.

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
    FilterRule, FilterStringRule, FilterStringGreaterOrEqual,
    BuiltInParameter
)
from Autodesk.Revit.Exceptions import ArgumentException # Import for potential exception handling

# --- Configuration ---
filter_name = "Fire Rated - Walls and Floors"
# Assumption: 'Fire Rating' corresponds to the built-in parameter FIRE_RATING.
# If this is a shared or project parameter, this ID needs to be found differently.
target_parameter_id = ElementId(BuiltInParameter.FIRE_RATING)
# Value to compare against. Assumes 'Fire Rating' is a text parameter where string comparison works as desired.
rule_value = "1 hr"
# Categories to apply the filter to
target_category_ids = List[ElementId]()
target_category_ids.Add(ElementId(BuiltInCategory.OST_Walls))
target_category_ids.Add(ElementId(BuiltInCategory.OST_Floors))

# --- Main Script ---

# Check if a filter with this name already exists
existing_filter = None
filter_collector = FilteredElementCollector(doc).OfClass(ParameterFilterElement)
for f in filter_collector:
    if f.Name == filter_name:
        existing_filter = f
        break

if existing_filter:
    print("# Filter named '{{}}' already exists.".format(filter_name))
    # Optional: Check if categories/rules match and update if necessary
    try:
        needs_category_update = False
        current_categories = existing_filter.GetCategories()
        if len(current_categories) != len(target_category_ids):
            needs_category_update = True
        else:
            current_cat_ids = set(c.IntegerValue for c in current_categories)
            target_cat_ids_set = set(c.IntegerValue for c in target_category_ids)
            if current_cat_ids != target_cat_ids_set:
                needs_category_update = True

        if needs_category_update:
            # Update categories (Transaction handled externally)
            existing_filter.SetCategories(target_category_ids)
            print("# Updated categories for existing filter '{{}}'.".format(filter_name))

        # Create the rule to compare against
        str_evaluator = FilterStringGreaterOrEqual()
        # Note: Case sensitivity depends on the evaluator implementation in Revit. Typically case-insensitive for text params.
        try:
            filter_rule = ParameterFilterRuleFactory.CreateFilterRule(target_parameter_id, str_evaluator, rule_value)
            rules_list = List[FilterRule]()
            rules_list.Add(filter_rule)

            needs_rule_update = False
            current_rules = existing_filter.GetRules()
            # Basic check: assumes only one rule. A more robust check would compare rule details.
            if len(current_rules) != 1 or str(current_rules[0]) != str(filter_rule):
                 needs_rule_update = True

            if needs_rule_update:
                 # Update rules (Transaction handled externally)
                 existing_filter.SetRules(rules_list)
                 print("# Updated rules for existing filter '{{}}'.".format(filter_name))
            
            if not needs_category_update and not needs_rule_update:
                 print("# Existing filter '{{}}' configuration matches. No update needed.".format(filter_name))

        except ArgumentException as ae:
            print("# Error creating filter rule for comparison (ArgumentException): {{}} - Ensure parameter 'FIRE_RATING' exists, is Text/String, and applicable to Walls/Floors.".format(ae.Message))
        except Exception as rule_e:
            print("# Error creating or comparing filter rule: {{}}".format(rule_e))

    except Exception as update_e:
        print("# Error checking or updating existing filter '{{}}': {{}}".format(filter_name, update_e))

else:
    # Create the filter rule: 'Fire Rating' >= '1 hr'
    filter_rule = None
    try:
        str_evaluator = FilterStringGreaterOrEqual()
        # Note: Case sensitivity depends on the evaluator implementation in Revit. Typically case-insensitive for text params.
        filter_rule = ParameterFilterRuleFactory.CreateFilterRule(target_parameter_id, str_evaluator, rule_value)
    except ArgumentException as ae:
        print("# Error creating filter rule (ArgumentException): {{}} - Ensure parameter 'FIRE_RATING' exists, is Text/String, and applicable to Walls/Floors.".format(ae.Message))
    except Exception as e:
        print("# Error creating filter rule: {{}}".format(e))

    if filter_rule:
        filter_rules = List[FilterRule]()
        filter_rules.Add(filter_rule)

        # Create the Parameter Filter Element (Transaction handled externally)
        try:
            new_filter = ParameterFilterElement.Create(doc, filter_name, target_category_ids, filter_rules)
            print("# Successfully created filter: '{{}}'".format(filter_name))
            print("#   Applies to: Walls, Floors")
            print("#   Rule: Fire Rating >= '{{}}'".format(rule_value))
        except Exception as create_e:
            print("# Error creating ParameterFilterElement '{{}}': {{}}".format(filter_name, create_e))
    else:
        print("# Filter creation skipped due to rule creation error.")

# Note: This script only creates the filter definition.
# It does not apply it to any specific view or set overrides.
# Use the 'apply filter to view' pattern if needed separately.