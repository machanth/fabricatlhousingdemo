if pApprovedBatch="" or Text.Contains(pApprovedBatch,"/") or Text.Contains(pApprovedBatch,"..")
    then error Error.Record("Blocked","Set pApprovedBatch only after all 24 original workbooks pass preflight",null)
    else AzureStorage.DataLake(
        "https://onelake.dfs.fabric.microsoft.com/" & pWorkspaceId & "/" & pLakehouseId & "/Files/landing/excel/" & pApprovedBatch,
        [HierarchicalNavigation=false])
