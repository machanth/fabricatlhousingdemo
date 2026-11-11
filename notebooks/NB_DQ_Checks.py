import json
import struct
import uuid

import com.microsoft.spark.fabric
import notebookutils
import pyodbc
from pyspark.sql import functions as F

run_id = str(uuid.uuid4())
facts = spark.read.synapsesql("WH_ATL_HS.prd.FactHouseholdSnapshot")
members = spark.read.synapsesql("WH_ATL_HS.stg.Member")
properties = spark.read.synapsesql("WH_ATL_HS.stg.Property")
duplicate_groups = facts.groupBy("EffectiveDateKey", "HouseholdID").agg(
    F.countDistinct("ProgramTypeKey").alias("Programs")).filter("Programs > 1")
invalid_dates = members.filter(
    F.to_date(F.col("EffectiveDateKey").cast("string"), "yyyyMMdd").isNull()
    | (F.col("EffectiveDateKey") < 20150101)
    | (F.col("EffectiveDateKey") > 20301231)
    | ((F.col("EffectiveDateKey") % 100) != 1))
invalid_current = properties.groupBy("PropertyID").agg(
    F.sum(F.col("IsCurrent").cast("int")).alias("CurrentRows")).filter("CurrentRows <> 1")
a, b = properties.alias("a"), properties.alias("b")
overlaps = a.join(b, (F.col("a.PropertyID") == F.col("b.PropertyID"))
                  & (F.col("a.PropertyKey") < F.col("b.PropertyKey"))
                  & (F.col("a.EffectiveBeginDate") <= F.col("b.EffectiveEndDate"))
                  & (F.col("b.EffectiveBeginDate") <= F.col("a.EffectiveEndDate")))
rules = [
    ("DuplicateProgramHouseholdMonths", duplicate_groups.count(), "Warning"),
    ("MissingUnitObservations", facts.filter("UnitKey = -1").count(), "Warning"),
    ("InvalidMonthlyDates", invalid_dates.count(), "Error"),
    ("InvalidCurrentPropertyVersions", invalid_current.count(), "Error"),
    ("OverlappingPropertyIntervals", overlaps.count(), "Error"),
]
availability = spark.read.synapsesql("WH_ATL_HS.stg.UnitAvailability")
if availability.count() == 0:
    rules.append(("OccupancyExcelBlocked", 0, "Blocked"))
else:
    occupancy = spark.read.synapsesql("WH_ATL_HS.prd.vw_DQ_OccupancyVsAvailable")
    programs = {r.ProgramTypeCode for r in occupancy.select("ProgramTypeCode").distinct().collect()}
    if programs != {"MIXED_HF", "MIXED_RAD"}:
        raise RuntimeError(f"Unexpected negative-vacancy programs: {sorted(programs)}")
    rules.append(("OverOccupiedProgramMonths", occupancy.count(), "Warning"))
raw_token = notebookutils.credentials.getToken("pbi").encode("utf-16-le")
with pyodbc.connect(
    f"Driver={{ODBC Driver 18 for SQL Server}};Server={warehouse_server};"
    "Database=WH_ATL_HS;Encrypt=yes;TrustServerCertificate=no;",
    attrs_before={1256: struct.pack("<I", len(raw_token)) + raw_token},
    autocommit=True,
) as connection:
    for rule, count, severity in rules:
        connection.cursor().execute(
            "INSERT INTO prd.DQ_Results VALUES (?,?,?,?,SYSUTCDATETIME())",
            run_id, rule, count, severity)
if any(count > 0 and severity == "Error" for _, count, severity in rules):
    raise RuntimeError("Structural DQ failures; inspect prd.DQ_Results.")
if not rules[0][1] or not rules[1][1]:
    raise RuntimeError("Expected seeded duplicate-program/missing-unit observations were not found.")
notebookutils.notebook.exit(json.dumps({"run_id": run_id, "scope": "SQL-only", "rules": rules}))
