let
    Files = Table.SelectRows(CurrentBatch, each Text.StartsWith([Name],"UnitAvailability_") and Text.EndsWith([Name],".xlsx")),
    Check = if Table.RowCount(Files)<>12 then error "Exactly 12 availability workbooks required" else Files,
    Rows = Table.Combine(List.Transform(Table.ToRecords(Check),each WorkbookRows([Content],[Name],"UnitAvailability")))
in Rows
