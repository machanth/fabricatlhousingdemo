-- Run only against your participant Warehouse.
SELECT 'actual' AS Side,COUNT(*) AS ProgramMonths FROM prd.vw_AllMetrics
UNION ALL SELECT 'expected',COUNT(*) FROM stg.AnswerKey;

SELECT 'actual' AS Side,EffectiveDateKey,ProgramTypeCode,COUNT(*) AS DuplicateCount
FROM prd.vw_AllMetrics GROUP BY EffectiveDateKey,ProgramTypeCode HAVING COUNT(*)>1
UNION ALL
SELECT 'expected',EffectiveDateKey,ProgramTypeCode,COUNT(*)
FROM stg.AnswerKey GROUP BY EffectiveDateKey,ProgramTypeCode HAVING COUNT(*)>1;

SELECT COALESCE(a.EffectiveDateKey,e.EffectiveDateKey) AS EffectiveDateKey,
       COALESCE(a.ProgramTypeCode,e.ProgramTypeCode) AS ProgramTypeCode,
       m.Metric,m.Actual,m.Expected
FROM prd.vw_AllMetrics a
FULL OUTER JOIN stg.AnswerKey e ON a.EffectiveDateKey=e.EffectiveDateKey
    AND a.ProgramTypeCode=e.ProgramTypeCode
CROSS APPLY (VALUES
      ('Households',a.[Households],e.[Households]),
      ('HWC',a.[HWC],e.[HWC]),
      ('HWC_Elderly',a.[HWC_Elderly],e.[HWC_Elderly]),
      ('HWC_Disabled',a.[HWC_Disabled],e.[HWC_Disabled]),
      ('HWC_Workforce',a.[HWC_Workforce],e.[HWC_Workforce]),
      ('HWOC',a.[HWOC],e.[HWOC]),
      ('HWOC_Elderly',a.[HWOC_Elderly],e.[HWOC_Elderly]),
      ('HWOC_Disabled',a.[HWOC_Disabled],e.[HWOC_Disabled]),
      ('HWOC_Workforce',a.[HWOC_Workforce],e.[HWOC_Workforce]),
      ('VASH_HWC',a.[VASH_HWC],e.[VASH_HWC]),
      ('VASH_HWOC',a.[VASH_HWOC],e.[VASH_HWOC]),
      ('OtherSupportive_HWC',a.[OtherSupportive_HWC],e.[OtherSupportive_HWC]),
      ('OtherSupportive_HWOC',a.[OtherSupportive_HWOC],e.[OtherSupportive_HWOC]),
      ('TotalUnits',a.[TotalUnits],e.[TotalUnits]),
      ('AvailableUnits',a.[AvailableUnits],e.[AvailableUnits]),
      ('LIHTCUnits',a.[LIHTCUnits],e.[LIHTCUnits]),
      ('VacantUnits',a.[VacantUnits],e.[VacantUnits])
) m(Metric,Actual,Expected)
WHERE a.EffectiveDateKey IS NULL OR e.EffectiveDateKey IS NULL
   OR m.Actual<>m.Expected
   OR (m.Actual IS NULL AND m.Expected IS NOT NULL)
   OR (m.Actual IS NOT NULL AND m.Expected IS NULL)
ORDER BY EffectiveDateKey,ProgramTypeCode,m.Metric;
-- Expected: two 108 counts; zero duplicate keys; zero mismatch rows. NULL is not zero.
