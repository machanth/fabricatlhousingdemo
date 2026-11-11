IF SCHEMA_ID('stg') IS NULL EXEC('CREATE SCHEMA stg');
IF SCHEMA_ID('prd') IS NULL EXEC('CREATE SCHEMA prd');
IF SCHEMA_ID('mtd') IS NULL EXEC('CREATE SCHEMA mtd');
GO
IF OBJECT_ID('mtd.TablesToCopy') IS NULL
CREATE TABLE mtd.TablesToCopy (
    SourceSchema varchar(128) NOT NULL, SourceTable varchar(128) NOT NULL,
    TargetTable varchar(128) NOT NULL, LoadType varchar(20) NOT NULL,
    WatermarkColumn varchar(128) NULL, IsActive bit NOT NULL
);
IF NOT EXISTS (SELECT 1 FROM mtd.TablesToCopy)
INSERT INTO mtd.TablesToCopy VALUES
('hs','SourceSystem','SourceSystem','Full',NULL,1),
('hs','ProgramType','ProgramType','Full',NULL,1),
('hs','VoucherType','VoucherType','Full',NULL,1),
('hs','ActionType','ActionType','Full',NULL,1),
('hs','IncomeSource','IncomeSource','Full',NULL,1),
('hs','Property','Property','Full',NULL,1),
('hs','Unit','Unit','Full',NULL,1),
('hs','UnitLocation','UnitLocation','Full',NULL,1),
('hs','Member','Member','Full',NULL,1),
('hs','FamilyMember','FamilyMember','Full',NULL,1);
IF OBJECT_ID('mtd.FilesToLoad') IS NULL
CREATE TABLE mtd.FilesToLoad (
    RunId varchar(36) NOT NULL, SourceFile varchar(500) NOT NULL,
    EffectiveDateKey int NOT NULL, TargetTable varchar(128) NOT NULL,
    Sha256 varchar(64) NOT NULL, LoadStatus varchar(20) NOT NULL
);
IF OBJECT_ID('mtd.PipelineRunLog') IS NULL
CREATE TABLE mtd.PipelineRunLog (
    RunId varchar(36) NOT NULL, Stage varchar(100) NOT NULL,
    StartedAt datetime2(6) NOT NULL, FinishedAt datetime2(6) NULL,
    Status varchar(20) NOT NULL, [RowCount] bigint NULL, ErrorMessage varchar(4000) NULL
);
IF OBJECT_ID('mtd.ProgramScope') IS NULL
CREATE TABLE mtd.ProgramScope (UserPrincipalName varchar(320) NOT NULL, ProgramTypeKey int NOT NULL);
IF OBJECT_ID('stg.UnitAvailability') IS NULL
CREATE TABLE stg.UnitAvailability (
    EffectiveDateKey int NOT NULL, Program varchar(20) NOT NULL,
    TotalUnits int NOT NULL, AvailableUnits int NOT NULL, LIHTCUnits int NOT NULL,
    SourceFile varchar(500) NOT NULL
);
IF OBJECT_ID('stg.SupportiveHousing') IS NULL
CREATE TABLE stg.SupportiveHousing (
    EffectiveDateKey int NOT NULL, HouseholdID varchar(12) NOT NULL,
    Program varchar(20) NOT NULL, SupportType varchar(20) NOT NULL,
    SourceFile varchar(500) NOT NULL
);
IF OBJECT_ID('prd.DQ_Results') IS NULL
CREATE TABLE prd.DQ_Results (
    RunId varchar(36) NOT NULL, [Rule] varchar(100) NOT NULL,
    ObservedCount bigint NOT NULL, Severity varchar(20) NOT NULL,
    CheckedAt datetime2(6) NOT NULL
);
