"""Build a real PBIR report bound to the explicit, validated Direct Lake model."""
import json

from common import CONFIG, ROOT, check_account, fabric, items, save_state
from deploy_items import part


SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/"


def literal(value):
    if isinstance(value, bool):
        value = str(value).lower()
    elif isinstance(value, str):
        value = "'" + value.replace("'", "''") + "'"
    else:
        value = str(value) + "D"
    return {"expr": {"Literal": {"Value": value}}}


def field(table, name, measure=False):
    return {"Measure" if measure else "Column": {
        "Expression": {"SourceRef": {"Entity": table}}, "Property": name,
    }}


def projection(table, name, measure=False):
    return {"field": field(table, name, measure), "queryRef": f"{table}.{name}",
            "nativeQueryRef": name}


def title(text):
    return {"title": [{"properties": {
        "show": literal(True), "text": literal(text), "fontSize": literal(14),
        "fontColor": {"solid": {"color": literal("#183153")}},
    }}]}


def visual(name, kind, x, y, width, height, roles=None, heading=None):
    content = {"visualType": kind, "drillFilterOtherVisuals": True}
    if roles:
        content["query"] = {"queryState": {
            role: {"projections": values} for role, values in roles.items()
        }}
    if heading:
        content["visualContainerObjects"] = title(heading)
    return {
        "$schema": SCHEMA + "definition/visualContainer/2.0.0/schema.json",
        "name": name, "position": {"x": x, "y": y, "z": y + x, "width": width,
                                   "height": height, "tabOrder": y + x},
        "visual": content,
    }


def text_box(name, paragraphs, x, y, width, height, size=12):
    result = visual(name, "textbox", x, y, width, height)
    result["visual"]["objects"] = {"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": text, "textStyle": {"fontSize": f"{size}pt",
                                                  "fontFamily": "Segoe UI"}}]}
        for text in paragraphs
    ]}}]}
    return result


def categorical_filter(name, table, column, value):
    return {
        "name": name, "field": field(table, column), "type": "Categorical",
        "filter": {"Version": 2, "From": [{"Name": "s", "Entity": table, "Type": 0}],
                   "Where": [{"Condition": {"In": {
                       "Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "s"}},
                                                   "Property": column}}],
                       "Values": [[{"Literal": {"Value":
                           f"'{value}'" if isinstance(value, str) else f"{value}L"}}]],
                   }}}]},
        "howCreated": "User",
    }


def build(model_id):
    docs = {}

    def add(path, document):
        docs[path] = document

    main = "mtw_detail_ht"
    dq = "data_quality"
    tooltip = "metric_definitions"
    add("definition.pbir", {
        "$schema": SCHEMA + "definitionProperties/2.0.0/schema.json",
        "version": "4.0", "datasetReference": {"byConnection": {
            "connectionString": f"semanticmodelid={model_id}"}}})
    add("definition/version.json", {
        "$schema": SCHEMA + "definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
    add("definition/report.json", {
        "$schema": SCHEMA + "definition/report/3.1.0/schema.json",
        "themeCollection": {"baseTheme": {
            "name": "CY25SU12", "type": "SharedResources",
            "reportVersionAtImport": {"visual": "2.0.0", "report": "3.1.0", "page": "2.0.0"},
        }},
        "resourcePackages": [{"name": "SharedResources", "type": "SharedResources", "items": [
            {"name": "CY25SU12", "path": "BaseThemes/CY25SU12.json", "type": "BaseTheme"},
        ]}],
        "settings": {"useEnhancedTooltips": True, "defaultDrillFilterOtherVisuals": True},
        "filterConfig": {"filters": [{
            "name": "exclude_structural_blank_program", "type": "Categorical",
            "field": field("DimProgramType", "ProgramTypeShortName"),
            "filter": {"Version": 2, "From": [
                {"Name": "p", "Entity": "DimProgramType", "Type": 0}],
                "Where": [{"Condition": {"Not": {"Expression": {"In": {
                    "Expressions": [{"Column": {
                        "Expression": {"SourceRef": {"Source": "p"}},
                        "Property": "ProgramTypeShortName"}}],
                    "Values": [[{"Literal": {"Value": "null"}}]],
                }}}}}]},
            "howCreated": "User", "isHiddenInViewMode": True,
        }]},
    })
    add("definition/pages/pages.json", {
        "$schema": SCHEMA + "definition/pagesMetadata/1.0.0/schema.json",
        "pageOrder": [main, dq, tooltip], "activePageName": main,
    })
    for name, display in ((main, "MTW Detail Data HT1-HT10"), (dq, "Data quality"),
                          (tooltip, "Metric definitions")):
        page = {"$schema": SCHEMA + "definition/page/2.0.0/schema.json", "name": name,
                "displayName": display, "displayOption": "FitToPage", "width": 1440, "height": 1000}
        if name == tooltip:
            page.update(type="Tooltip", visibility="HiddenInViewMode", width=560, height=330,
                        pageBinding={"name": "metric_definitions_binding", "type": "Tooltip"})
        add(f"definition/pages/{name}/page.json", page)

    def add_visual(page, content):
        add(f"definition/pages/{page}/visuals/{content['name']}/visual.json", content)

    add_visual(main, text_box("heading", ["ATL Housing | Households served"],
                             24, 10, 1040, 50, 24))
    month = visual("month_selection", "slicer", 1120, 12, 290, 76,
                   {"Values": [projection("DimDate", "MonthYear")]}, "Reporting month")
    month["visual"]["objects"] = {
        "general": [{"properties": {"filter": {"filter": categorical_filter(
            "selected_month", "DimDate", "MonthYear", "2025-01")["filter"]}}}],
        "data": [{"properties": {"mode": literal("Dropdown")}}],
        "selection": [{"properties": {"singleSelect": literal(True),
                                      "strictSingleSelect": literal(True),
                                      "selectAllCheckboxEnabled": literal(False)}}],
    }
    month["filterConfig"] = {"filters": [
        categorical_filter("demo_reporting_year", "DimDate", "CalendarYear", 2025),
    ]}
    add_visual(main, month)
    program = projection("DimProgramType", "ProgramTypeShortName")
    occupied = visual("occupied", "pivotTable", 24, 100, 1388, 320, {
        "Rows": [projection("FactHouseholdSnapshot", "HouseholdType"),
                 projection("FactHouseholdSnapshot", "Category")],
        "Columns": [program],
        "Values": [projection("FactHouseholdSnapshot", "Households", True)],
    }, "Occupied households | Elderly > Disabled > Workforce")
    for row in occupied["visual"]["query"]["queryState"]["Rows"]["projections"]:
        row["active"] = True
    occupied["visual"]["expansionStates"] = [{
        "roles": ["Rows"], "levels": [{
            "queryRefs": ["FactHouseholdSnapshot.HouseholdType"], "isPinned": True,
        }, {"queryRefs": ["FactHouseholdSnapshot.Category"], "isPinned": True}], "root": {},
    }]
    occupied["visual"]["visualContainerObjects"]["visualTooltip"] = [{"properties": {
        "type": literal("ReportPage"), "section": literal(tooltip)}}]
    add_visual(main, occupied)
    inventory = visual("inventory", "pivotTable", 24, 435, 1388, 220, {
        "Columns": [program], "Values": [
            projection("FactUnitAvailability", name, True) for name in
            ("Available Units", "LIHTC Units", "Total Units", "Vacant Units")],
    }, "Unit availability | Available excludes LIHTC; voucher vacancy is not applicable")
    inventory["visual"]["objects"] = {
        "values": [{"properties": {"valuesOnRow": literal(True)}}, {
            "selector": {"metadata": "FactUnitAvailability.Vacant Units",
                         "data": [{"dataViewWildcard": {"matchingOption": 0}}]},
            "properties": {"fontColor": {"solid": {"color": {
                "expr": field("FactUnitAvailability", "Vacancy Color", True)}}}},
        }],
        "columnHeaders": [{"properties": {"show": literal(True)}}],
    }
    inventory["visual"]["visualContainerObjects"]["visualTooltip"] = [{"properties": {
        "type": literal("ReportPage"), "section": literal(tooltip)}}]
    add_visual(main, inventory)
    supportive = visual("supportive", "pivotTable", 24, 670, 1388, 220, {
        "Columns": [program], "Values": [
            projection("FactSupportiveHousing", name, True) for name in
            ("VASH With Children", "VASH Without Children",
             "Other Supportive With Children", "Other Supportive Without Children")],
    }, "Supportive housing | Match reporting month + household + its own program")
    supportive["visual"]["objects"] = {
        "values": [{"properties": {"valuesOnRow": literal(True)}}],
    }
    add_visual(main, supportive)
    add_visual(main, text_box("grain_note", [
        "Counts are household-program-month observations, not distinct households. "
        "Deliberate second-program records are retained.",
        "Negative vacancy is preserved. See Data quality for seeded exceptions and run IDs.",
    ], 24, 915, 1388, 70))
    add_visual(dq, text_box("dq_heading", [
        "Data quality | Seeded exceptions stay visible",
        "Missing units and multi-program observations are preserved. "
        "These checks are run-level controls, not affected by the report month.",
    ], 24, 14, 1388, 95, 17))
    add_visual(dq, visual("dq_results", "tableEx", 24, 125, 1388, 740, {
        "Values": [projection("DQ_Results", name) for name in
                   ("RunId", "Rule", "Severity", "CheckedAt")] +
                  [projection("DQ_Results", "DQ Observations", True)],
    }, "Actual Spark DQ results by run"))
    add_visual(tooltip, text_box("definitions", [
        "Households served: household-program-month observations.",
        "Child count > 0: With children. Live-in aides are excluded.",
        "Category precedence: Elderly, then Disabled, then Workforce.",
        "Available units excludes LIHTC. Voucher vacancy is blank.",
        "Vacant = available - unit-based occupied households.",
        "Negative vacancy is a DQ signal, never clamped to zero.",
    ], 12, 12, 530, 305))
    return docs


def main():
    check_account()
    available = items()
    model = next(i for i in available if i["displayName"] == "SM_HouseholdsServed"
                 and i["type"] == "SemanticModel")
    documents = build(model["id"])
    folder = ROOT / "report" / "RPT_MTW_Detail_HT.Report"
    for path, document in documents.items():
        target = folder.joinpath(*path.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, indent=2) + "\n")
    definition = {"parts": [part(path, json.dumps(doc)) for path, doc in documents.items()]}
    existing = next((i for i in available if i["displayName"] == "RPT_MTW_Detail_HT"), None)
    path = f"workspaces/{CONFIG['workspace_id']}/reports"
    if existing:
        if existing["type"] != "Report":
            raise RuntimeError("The report name is used by another item type.")
        fabric("POST", f"{path}/{existing['id']}/updateDefinition",
               {"definition": definition}, has_result=False)
        result = existing
    else:
        result = fabric("POST", path, {"displayName": "RPT_MTW_Detail_HT",
                                       "definition": definition})
    save_state("report-item.json", result)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
