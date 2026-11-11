CREATE OR ALTER PROCEDURE mtd.usp_LogRun
    @RunId varchar(36), @Stage varchar(100), @Status varchar(20),
    @Rows bigint = NULL, @ErrorMessage varchar(4000) = NULL
AS
BEGIN
    INSERT INTO mtd.PipelineRunLog
    (RunId,Stage,StartedAt,FinishedAt,Status,[RowCount],ErrorMessage)
    VALUES (@RunId,@Stage,SYSUTCDATETIME(),SYSUTCDATETIME(),@Status,@Rows,@ErrorMessage);
END;
GO
CREATE OR ALTER PROCEDURE prd.usp_Load_Dimensions
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM stg.ProgramType)
        THROW 51000, 'SQL staging is empty; ingestion must succeed first.', 1;
    IF EXISTS (SELECT PropertyID FROM stg.Property GROUP BY PropertyID HAVING SUM(CAST(IsCurrent AS int)) <> 1)
        THROW 51001, 'Property must have exactly one current version per business key.', 1;
    IF EXISTS (
        SELECT 1 FROM stg.Property a JOIN stg.Property b
          ON a.PropertyID=b.PropertyID AND a.PropertyKey<b.PropertyKey
         AND a.EffectiveBeginDate<=b.EffectiveEndDate AND b.EffectiveBeginDate<=a.EffectiveEndDate
    ) THROW 51002, 'Overlapping property SCD2 intervals.', 1;
    BEGIN TRY
        BEGIN TRANSACTION;
        DROP TABLE IF EXISTS prd.DimProgramType;
        SELECT ProgramTypeKey,ProgramTypeCode,ProgramTypeShortName,ProgramTypeLongName,ProgramFamily
        INTO prd.DimProgramType FROM stg.ProgramType;
        DROP TABLE IF EXISTS prd.DimVoucherType;
        SELECT VoucherTypeKey,VoucherTypeCode,VoucherTypeDesc INTO prd.DimVoucherType FROM stg.VoucherType;
        INSERT INTO prd.DimVoucherType VALUES (-1,'UNKNOWN','Unknown or not applicable');
        DROP TABLE IF EXISTS prd.DimActionType;
        SELECT ActionTypeKey,ActionTypeCode,ActionTypeName INTO prd.DimActionType FROM stg.ActionType;
        DROP TABLE IF EXISTS prd.DimIncomeSource;
        SELECT IncomeSourceKey,IncomeSourceCode,IncomeSourceDesc INTO prd.DimIncomeSource FROM stg.IncomeSource;
        DROP TABLE IF EXISTS prd.DimProperty;
        SELECT PropertyKey,PropertyID,PropertyCode,PropertyName,PropertyManager,
               EffectiveBeginDate,EffectiveEndDate,IsCurrent,IsPropertyActive
        INTO prd.DimProperty FROM stg.Property;
        INSERT INTO prd.DimProperty VALUES
          (-1,'UNKNOWN','UNKNOWN','Unknown property','Unknown','20150101','99991231',1,0);
        DROP TABLE IF EXISTS prd.DimUnit;
        SELECT UnitKey,UnitAK,PropertyID,Bedrooms,IsAvailable,IsLIHTC,
               CONVERT(date,CONVERT(char(8),EffectiveDateKey),112) AS EffectiveBeginDate,
               CONVERT(date,'99991231',112) AS EffectiveEndDate,CAST(1 AS bit) AS IsCurrent
        INTO prd.DimUnit FROM stg.Unit;
        INSERT INTO prd.DimUnit VALUES
          (-1,'UNKNOWN','UNKNOWN',NULL,0,0,'20150101','99991231',1);
        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT>0 ROLLBACK;
        THROW;
    END CATCH;
END;
GO
CREATE OR ALTER PROCEDURE prd.usp_Load_FactHouseholdSnapshot
AS
BEGIN
    SET NOCOUNT ON;
    IF EXISTS (SELECT 1 FROM stg.Member
               WHERE TRY_CONVERT(date,CONVERT(char(8),EffectiveDateKey),112) IS NULL
                  OR EffectiveDateKey<20150101 OR EffectiveDateKey>20301231
                  OR EffectiveDateKey%100<>1)
        THROW 51003, 'Invalid monthly effective date in Member.', 1;
    IF EXISTS (SELECT EffectiveDateKey,HouseholdID,ProgramTypeKey
               FROM stg.Member GROUP BY EffectiveDateKey,HouseholdID,ProgramTypeKey HAVING COUNT(*)>1)
        THROW 51004, 'Duplicate household-program-month rows would multiply facts.', 1;
    IF EXISTS (SELECT 1 FROM stg.Member m LEFT JOIN prd.DimProgramType p
               ON p.ProgramTypeKey=m.ProgramTypeKey WHERE p.ProgramTypeKey IS NULL)
        THROW 51005, 'Member has an unmapped program.', 1;
    IF EXISTS (
        SELECT 1 FROM stg.Member m JOIN prd.DimUnit u ON u.UnitKey=m.UnitKey
        LEFT JOIN prd.DimProperty p ON p.PropertyID=u.PropertyID
          AND CONVERT(date,CONVERT(char(8),m.EffectiveDateKey),112) BETWEEN p.EffectiveBeginDate AND p.EffectiveEndDate
        WHERE p.PropertyKey IS NULL
    ) THROW 51006, 'An existing unit has no property version at the snapshot date.', 1;
    BEGIN TRY
        BEGIN TRANSACTION;
        DROP TABLE IF EXISTS prd.FactHouseholdSnapshot;
        SELECT m.MemberKey,m.HouseholdID,m.EffectiveDateKey,m.ProgramTypeKey,
               COALESCE(u.UnitKey,-1) AS UnitKey,COALESCE(p.PropertyKey,-1) AS PropertyKey,
               COALESCE(m.VoucherTypeKey,-1) AS VoucherTypeKey,m.ActionTypeKey,m.IncomeSourceKey,
               m.UnitKey AS SourceUnitKey,
               CAST(CASE WHEN m.BDEMO_TotalChildCount>0 THEN 'With children' ELSE 'Without children' END AS varchar(20)) AS HouseholdType,
               CAST(CASE WHEN m.BDEMO_TotalSeniorCount>0 THEN 'Elderly'
                         WHEN m.BDEMO_TotalDisabledAdultCount>0 THEN 'Disabled' ELSE 'Workforce' END AS varchar(20)) AS Category
        INTO prd.FactHouseholdSnapshot
        FROM stg.Member m
        LEFT JOIN prd.DimUnit u ON u.UnitKey=m.UnitKey
        LEFT JOIN prd.DimProperty p ON p.PropertyID=u.PropertyID
          AND CONVERT(date,CONVERT(char(8),m.EffectiveDateKey),112) BETWEEN p.EffectiveBeginDate AND p.EffectiveEndDate;
        IF (SELECT COUNT_BIG(*) FROM prd.FactHouseholdSnapshot)<>(SELECT COUNT_BIG(*) FROM stg.Member)
            THROW 51007, 'Fact join changed the source observation count.', 1;
        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT>0 ROLLBACK;
        THROW;
    END CATCH;
END;
GO
CREATE OR ALTER PROCEDURE prd.usp_Load_FactUnitAvailability
AS
BEGIN
    SET NOCOUNT ON;
    IF NOT EXISTS (SELECT 1 FROM stg.UnitAvailability) OR NOT EXISTS (SELECT 1 FROM stg.SupportiveHousing)
        THROW 51008, 'BLOCKED: readable Excel ingestion must complete before Excel-dependent facts.', 1;
    IF EXISTS (SELECT EffectiveDateKey,Program FROM stg.UnitAvailability
               GROUP BY EffectiveDateKey,Program HAVING COUNT(*)>1)
        THROW 51009, 'Duplicate availability program-month.', 1;
    IF EXISTS (SELECT EffectiveDateKey,HouseholdID,Program FROM stg.SupportiveHousing
               GROUP BY EffectiveDateKey,HouseholdID,Program HAVING COUNT(*)>1)
        THROW 51010, 'Duplicate supportive household-program-month.', 1;
    IF EXISTS (SELECT 1 FROM stg.SupportiveHousing WHERE SupportType NOT IN ('VASH','Other'))
        THROW 51011, 'Unknown supportive housing classification.', 1;
    IF EXISTS (
        SELECT DISTINCT m.EffectiveDateKey,p.ProgramTypeCode FROM stg.Member m
        JOIN prd.DimProgramType p ON p.ProgramTypeKey=m.ProgramTypeKey WHERE p.ProgramFamily='Unit-based'
        EXCEPT SELECT EffectiveDateKey,Program FROM stg.UnitAvailability
    ) THROW 51012, 'Missing availability program-month.', 1;
    IF EXISTS (SELECT 1 FROM stg.UnitAvailability a LEFT JOIN prd.DimProgramType p
               ON p.ProgramTypeCode=a.Program WHERE p.ProgramTypeKey IS NULL OR p.ProgramFamily<>'Unit-based'
               OR a.TotalUnits<>a.AvailableUnits+a.LIHTCUnits OR a.AvailableUnits<0 OR a.LIHTCUnits<0)
        THROW 51013, 'Invalid availability inventory or unmapped program.', 1;
    IF EXISTS (
        SELECT 1 FROM stg.SupportiveHousing s LEFT JOIN prd.DimProgramType p ON p.ProgramTypeCode=s.Program
        LEFT JOIN prd.FactHouseholdSnapshot f ON f.EffectiveDateKey=s.EffectiveDateKey
          AND f.HouseholdID=s.HouseholdID AND f.ProgramTypeKey=p.ProgramTypeKey WHERE f.MemberKey IS NULL
    ) THROW 51014, 'Supportive roster has unmatched household-program-month.', 1;
    BEGIN TRY
        BEGIN TRANSACTION;
        DROP TABLE IF EXISTS prd.FactUnitAvailability;
        SELECT a.EffectiveDateKey,p.ProgramTypeKey,a.TotalUnits,a.AvailableUnits,a.LIHTCUnits
        INTO prd.FactUnitAvailability FROM stg.UnitAvailability a
        JOIN prd.DimProgramType p ON p.ProgramTypeCode=a.Program;
        DROP TABLE IF EXISTS prd.FactSupportiveHousing;
        SELECT f.MemberKey,f.HouseholdID,f.EffectiveDateKey,f.ProgramTypeKey,f.HouseholdType,s.SupportType
        INTO prd.FactSupportiveHousing FROM stg.SupportiveHousing s
        JOIN prd.DimProgramType p ON p.ProgramTypeCode=s.Program
        JOIN prd.FactHouseholdSnapshot f ON f.EffectiveDateKey=s.EffectiveDateKey
          AND f.HouseholdID=s.HouseholdID AND f.ProgramTypeKey=p.ProgramTypeKey;
        COMMIT;
    END TRY
    BEGIN CATCH
        IF @@TRANCOUNT>0 ROLLBACK;
        THROW;
    END CATCH;
END;
