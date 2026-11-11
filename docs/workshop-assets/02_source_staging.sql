-- Run only in your assigned Fabric Warehouse WH_ATL_HS. No source SQL writes.

IF OBJECT_ID('stg.ActionType') IS NULL
CREATE TABLE stg.[ActionType] (
    [ActionTypeKey] int NULL,
    [ActionTypeCode] varchar(20) NULL,
    [ActionTypeName] varchar(100) NULL,
    [EffectiveDateKey] int NULL,
    [SourceSystemKey] int NULL
);
GO

IF OBJECT_ID('stg.AnswerKey') IS NULL
CREATE TABLE stg.[AnswerKey] (
    [EffectiveDateKey] int NULL,
    [ProgramTypeCode] varchar(20) NULL,
    [Households] int NULL,
    [HWC] int NULL,
    [HWC_Elderly] int NULL,
    [HWC_Disabled] int NULL,
    [HWC_Workforce] int NULL,
    [HWOC] int NULL,
    [HWOC_Elderly] int NULL,
    [HWOC_Disabled] int NULL,
    [HWOC_Workforce] int NULL,
    [VASH_HWC] int NULL,
    [VASH_HWOC] int NULL,
    [OtherSupportive_HWC] int NULL,
    [OtherSupportive_HWOC] int NULL,
    [TotalUnits] int NULL,
    [AvailableUnits] int NULL,
    [LIHTCUnits] int NULL,
    [VacantUnits] int NULL
);
GO

IF OBJECT_ID('stg.FamilyMember') IS NULL
CREATE TABLE stg.[FamilyMember] (
    [FamilyMemberKey] int NULL,
    [HouseholdID] varchar(12) NULL,
    [MemberSeq] smallint NULL,
    [Relationship] varchar(20) NULL,
    [FirstName] varchar(50) NULL,
    [LastName] varchar(50) NULL,
    [DateOfBirth] date NULL,
    [Gender] char(1) NULL,
    [Ethnicity] varchar(40) NULL,
    [Race] varchar(40) NULL,
    [Citizenship] varchar(40) NULL,
    [IsDisabled] bit NULL,
    [EffectiveDateKey] int NULL
);
GO

IF OBJECT_ID('stg.IncomeSource') IS NULL
CREATE TABLE stg.[IncomeSource] (
    [IncomeSourceKey] int NULL,
    [IncomeSourceCode] varchar(20) NULL,
    [IncomeSourceDesc] varchar(100) NULL,
    [EffectiveDateKey] int NULL,
    [SourceSystemKey] int NULL
);
GO

IF OBJECT_ID('stg.Member') IS NULL
CREATE TABLE stg.[Member] (
    [MemberKey] bigint NULL,
    [HouseholdID] varchar(12) NULL,
    [EffectiveDateKey] int NULL,
    [UnitKey] int NULL,
    [ProgramTypeKey] int NULL,
    [VoucherTypeKey] int NULL,
    [ActionTypeKey] int NULL,
    [IncomeSourceKey] int NULL,
    [BatchID] int NULL,
    [SourceSystemKey] int NULL,
    [AnnualIncome] decimal(12,2) NULL,
    [BDEMO_TotalAdultCount] smallint NULL,
    [BDEMO_TotalChildCount] smallint NULL,
    [BDEMO_TotalSeniorCount] smallint NULL,
    [BDEMO_TotalDisabledAdultCount] smallint NULL,
    [BDEMO_TotalDisabledChildCount] smallint NULL,
    [BDEMO_TotalLiveInAideCount] smallint NULL
);
GO

IF OBJECT_ID('stg.ProgramType') IS NULL
CREATE TABLE stg.[ProgramType] (
    [ProgramTypeKey] int NULL,
    [ProgramTypeCode] varchar(20) NULL,
    [ProgramTypeShortName] varchar(40) NULL,
    [ProgramTypeLongName] varchar(100) NULL,
    [ProgramFamily] varchar(20) NULL,
    [EffectiveDateKey] int NULL,
    [SourceSystemKey] int NULL
);
GO

IF OBJECT_ID('stg.Property') IS NULL
CREATE TABLE stg.[Property] (
    [PropertyKey] int NULL,
    [PropertyID] varchar(10) NULL,
    [PropertyCode] varchar(12) NULL,
    [PropertyName] varchar(100) NULL,
    [ProgramTypeKey] int NULL,
    [PropertyManager] varchar(50) NULL,
    [IsPropertyActive] bit NULL,
    [EffectiveBeginDate] date NULL,
    [EffectiveEndDate] date NULL,
    [IsCurrent] bit NULL,
    [EffectiveDateKey] int NULL,
    [SourceSystemKey] int NULL
);
GO

IF OBJECT_ID('stg.SourceSystem') IS NULL
CREATE TABLE stg.[SourceSystem] (
    [SourceSystemKey] int NULL,
    [SourceSystemCode] varchar(20) NULL,
    [SourceSystemName] varchar(100) NULL
);
GO

IF OBJECT_ID('stg.Unit') IS NULL
CREATE TABLE stg.[Unit] (
    [UnitKey] int NULL,
    [UnitAK] varchar(12) NULL,
    [PropertyID] varchar(10) NULL,
    [Bedrooms] smallint NULL,
    [IsAvailable] bit NULL,
    [IsLIHTC] bit NULL,
    [PublicHousingUnitACCYes] bit NULL,
    [UnitAddress1] varchar(100) NULL,
    [UnitAddress2] varchar(50) NULL,
    [MailingAddressUnit] varchar(50) NULL,
    [EffectiveDateKey] int NULL,
    [SourceSystemKey] int NULL
);
GO

IF OBJECT_ID('stg.UnitLocation') IS NULL
CREATE TABLE stg.[UnitLocation] (
    [UnitKey] int NULL,
    [CouncilDistrictName] varchar(30) NULL,
    [FormattedAddress] varchar(150) NULL,
    [FormattedCity] varchar(50) NULL,
    [FormattedCounty] varchar(50) NULL,
    [FormattedState] char(2) NULL,
    [FormattedZip] varchar(10) NULL,
    [CreateDate] date NULL,
    [CreatedBy] varchar(50) NULL
);
GO

IF OBJECT_ID('stg.VoucherType') IS NULL
CREATE TABLE stg.[VoucherType] (
    [VoucherTypeKey] int NULL,
    [VoucherTypeCode] varchar(20) NULL,
    [VoucherTypeDesc] varchar(100) NULL,
    [EffectiveDateKey] int NULL,
    [SourceSystemKey] int NULL
);
GO

