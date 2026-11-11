(Content as binary, FileName as text, Kind as text) as table =>
let
    Expected = if Kind = "UnitAvailability"
        then {"ReportMonth","Program","TotalUnits","AvailableUnits","LIHTCUnits"}
        else {"ReportMonth","HouseholdID","Program","SupportType"},
    Book = Excel.Workbook(Content, null, true),
    SheetName = if Kind="UnitAvailability" then "UnitAvailability" else "Roster",
    Sheet = Book{[Item=SheetName,Kind="Sheet"]}[Data],
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
in Table.RemoveColumns(Source,{"ReportMonth"})
