CREATE OR ALTER VIEW prd.vw_HouseholdMetrics AS
SELECT f.EffectiveDateKey,p.ProgramTypeCode,COUNT_BIG(*) AS Households,
       SUM(CASE WHEN HouseholdType='With children' THEN 1 ELSE 0 END) AS HWC,
       SUM(CASE WHEN HouseholdType='With children' AND Category='Elderly' THEN 1 ELSE 0 END) AS HWC_Elderly,
       SUM(CASE WHEN HouseholdType='With children' AND Category='Disabled' THEN 1 ELSE 0 END) AS HWC_Disabled,
       SUM(CASE WHEN HouseholdType='With children' AND Category='Workforce' THEN 1 ELSE 0 END) AS HWC_Workforce,
       SUM(CASE WHEN HouseholdType='Without children' THEN 1 ELSE 0 END) AS HWOC,
       SUM(CASE WHEN HouseholdType='Without children' AND Category='Elderly' THEN 1 ELSE 0 END) AS HWOC_Elderly,
       SUM(CASE WHEN HouseholdType='Without children' AND Category='Disabled' THEN 1 ELSE 0 END) AS HWOC_Disabled,
       SUM(CASE WHEN HouseholdType='Without children' AND Category='Workforce' THEN 1 ELSE 0 END) AS HWOC_Workforce
FROM prd.FactHouseholdSnapshot f JOIN prd.DimProgramType p ON p.ProgramTypeKey=f.ProgramTypeKey
GROUP BY f.EffectiveDateKey,p.ProgramTypeCode;
GO
CREATE OR ALTER VIEW prd.vw_AllMetrics AS
WITH supportive AS (
    SELECT EffectiveDateKey,ProgramTypeKey,
      SUM(CASE WHEN SupportType='VASH' AND HouseholdType='With children' THEN 1 ELSE 0 END) AS VASH_HWC,
      SUM(CASE WHEN SupportType='VASH' AND HouseholdType='Without children' THEN 1 ELSE 0 END) AS VASH_HWOC,
      SUM(CASE WHEN SupportType='Other' AND HouseholdType='With children' THEN 1 ELSE 0 END) AS OtherSupportive_HWC,
      SUM(CASE WHEN SupportType='Other' AND HouseholdType='Without children' THEN 1 ELSE 0 END) AS OtherSupportive_HWOC
    FROM prd.FactSupportiveHousing GROUP BY EffectiveDateKey,ProgramTypeKey
)
SELECT h.*,COALESCE(s.VASH_HWC,0) AS VASH_HWC,COALESCE(s.VASH_HWOC,0) AS VASH_HWOC,
       COALESCE(s.OtherSupportive_HWC,0) AS OtherSupportive_HWC,
       COALESCE(s.OtherSupportive_HWOC,0) AS OtherSupportive_HWOC,
       a.TotalUnits,a.AvailableUnits,a.LIHTCUnits,a.AvailableUnits-h.Households AS VacantUnits
FROM prd.vw_HouseholdMetrics h JOIN prd.DimProgramType p ON p.ProgramTypeCode=h.ProgramTypeCode
LEFT JOIN supportive s ON s.EffectiveDateKey=h.EffectiveDateKey AND s.ProgramTypeKey=p.ProgramTypeKey
LEFT JOIN prd.FactUnitAvailability a ON a.EffectiveDateKey=h.EffectiveDateKey AND a.ProgramTypeKey=p.ProgramTypeKey;
