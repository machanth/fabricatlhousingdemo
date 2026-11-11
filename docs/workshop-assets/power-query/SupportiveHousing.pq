let
    Files = Table.SelectRows(CurrentBatch, each Text.StartsWith([Name],"SupportiveHousing_") and Text.EndsWith([Name],".xlsx")),
    Check = if Table.RowCount(Files)<>12 then error "Exactly 12 supportive workbooks required" else Files,
    Rows = Table.Combine(List.Transform(Table.ToRecords(Check),each WorkbookRows([Content],[Name],"SupportiveHousing")))
in Rows
