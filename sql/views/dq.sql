CREATE OR ALTER VIEW prd.vw_DQ_DuplicatePrograms AS
SELECT EffectiveDateKey,HouseholdID,COUNT(DISTINCT ProgramTypeKey) AS ProgramCount
FROM prd.FactHouseholdSnapshot GROUP BY EffectiveDateKey,HouseholdID
HAVING COUNT(DISTINCT ProgramTypeKey)>1;
GO
CREATE OR ALTER VIEW prd.vw_DQ_MissingUnits AS
SELECT MemberKey,HouseholdID,EffectiveDateKey,ProgramTypeKey,SourceUnitKey
FROM prd.FactHouseholdSnapshot WHERE UnitKey=-1;
GO
CREATE OR ALTER VIEW prd.vw_DQ_OccupancyVsAvailable AS
SELECT f.EffectiveDateKey,p.ProgramTypeCode,COUNT_BIG(*) AS OccupiedHouseholds,
       a.AvailableUnits,a.AvailableUnits-COUNT_BIG(*) AS VacantUnits
FROM prd.FactHouseholdSnapshot f JOIN prd.DimProgramType p ON p.ProgramTypeKey=f.ProgramTypeKey
JOIN stg.UnitAvailability a ON a.EffectiveDateKey=f.EffectiveDateKey AND a.Program=p.ProgramTypeCode
GROUP BY f.EffectiveDateKey,p.ProgramTypeCode,a.AvailableUnits
HAVING COUNT_BIG(*)>a.AvailableUnits;
