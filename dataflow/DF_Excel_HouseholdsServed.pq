section Section1;
shared pApprovedBatch = "" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true];
shared WorkbookRows = (Content as binary, FileName as text, Kind as text) as table =>
let
    Expected = if Kind = "UnitAvailability"
        then {"ReportMonth","Program","TotalUnits","AvailableUnits","LIHTCUnits"}
        else {"ReportMonth","HouseholdID","Program","SupportType"},
    Book = Excel.Workbook(Content, null, true),
    Sheet = Book{[Item=if Kind="UnitAvailability" then "UnitAvailability" else "Roster",Kind="Sheet"]}[Data],
    Headers = Table.PromoteHeaders(Sheet, [PromoteAllScalars=true]),
    Checked = if List.Sort(Table.ColumnNames(Headers)) <> List.Sort(Expected)
        then error Error.Record("SchemaMismatch","Inspect replacement workbook before mapping",FileName) else Headers,
    MonthText = Text.BeforeDelimiter(Text.AfterDelimiter(FileName,"_"),"."),
    Month = #date(Number.FromText(Text.Start(MonthText,4)),Number.FromText(Text.End(MonthText,2)),1),
    Dates = Table.TransformColumnTypes(Checked,{{"ReportMonth",type date},{"Program",type text}}),
    Validated = if Table.RowCount(Table.SelectRows(Dates,each [ReportMonth] <> Month or [ReportMonth] = null)) > 0
        then error Error.Record("MonthMismatch","File name and ReportMonth disagree",FileName) else Dates,
    Typed = if Kind="UnitAvailability"
        then Table.TransformColumnTypes(Validated,{{"TotalUnits",Int64.Type},{"AvailableUnits",Int64.Type},{"LIHTCUnits",Int64.Type}})
        else Table.TransformColumnTypes(Validated,{{"HouseholdID",type text},{"SupportType",type text}}),
    DateKey = Table.AddColumn(Typed,"EffectiveDateKey",each Date.Year(Month)*10000+Date.Month(Month)*100+1,Int64.Type),
    Source = Table.AddColumn(DateKey,"SourceFile",each FileName,type text)
in Table.RemoveColumns(Source,{"ReportMonth"});
shared CurrentBatch =
    if pApprovedBatch="" or Text.Contains(pApprovedBatch,"/") or Text.Contains(pApprovedBatch,"..")
    then error Error.Record("Blocked","Set pApprovedBatch only after all 24 original workbooks pass preflight",null)
    else AzureStorage.DataLake(
        "https://onelake.dfs.fabric.microsoft.com/4d77b5c8-d96f-41df-83e1-954c582336d8/b3fdd7c1-498f-45f6-82a6-3a1ed9fa2ae9/Files/landing/excel/" & pApprovedBatch,
        [HierarchicalNavigation=false]);
shared UnitAvailability =
let
    Files = Table.SelectRows(CurrentBatch, each Text.StartsWith([Name],"UnitAvailability_") and Text.EndsWith([Name],".xlsx")),
    Check = if Table.RowCount(Files)<>12 then error "Exactly 12 availability workbooks required" else Files,
    Rows = Table.Combine(List.Transform(Table.ToRecords(Check),each WorkbookRows([Content],[Name],"UnitAvailability")))
in Rows;
shared SupportiveHousing =
let
    Files = Table.SelectRows(CurrentBatch, each Text.StartsWith([Name],"SupportiveHousing_") and Text.EndsWith([Name],".xlsx")),
    Check = if Table.RowCount(Files)<>12 then error "Exactly 12 supportive workbooks required" else Files,
    Rows = Table.Combine(List.Transform(Table.ToRecords(Check),each WorkbookRows([Content],[Name],"SupportiveHousing")))
in Rows;
