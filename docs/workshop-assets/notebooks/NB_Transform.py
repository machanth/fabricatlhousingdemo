import struct
import uuid

import notebookutils
import pyodbc

run_id = str(uuid.uuid4())
raw_token = notebookutils.credentials.getToken("pbi").encode("utf-16-le")
with pyodbc.connect(
    f"Driver={{ODBC Driver 18 for SQL Server}};Server={warehouse_server};"
    "Database=WH_ATL_HS;Encrypt=yes;TrustServerCertificate=no;",
    attrs_before={1256: struct.pack("<I", len(raw_token)) + raw_token},
    autocommit=True,
) as connection:
    for procedure in ("prd.usp_Load_Dimensions", "prd.usp_Load_FactHouseholdSnapshot",
                      "prd.usp_Load_FactUnitAvailability"):
        try:
            connection.cursor().execute(f"EXEC {procedure}")
        except Exception:
            connection.cursor().execute("EXEC mtd.usp_LogRun ?,?,'Failed',NULL,?",
                                        run_id, procedure, "Inspect notebook activity exception.")
            raise
        connection.cursor().execute("EXEC mtd.usp_LogRun ?,?,'Succeeded'", run_id, procedure)
notebookutils.notebook.exit(run_id)
