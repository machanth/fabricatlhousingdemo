-- Only an approved mapping in your participant Warehouse.
DECLARE @ApprovedUPN varchar(320) = '<APPROVED_VIEWER_UPN>';
DECLARE @ApprovedProgram varchar(20) = '<APPROVED_PROGRAM_CODE>';
IF @ApprovedUPN LIKE '<%' OR @ApprovedProgram LIKE '<%'
    THROW 51020,'Replace placeholders only with an explicitly approved mapping.',1;
IF NOT EXISTS (SELECT 1 FROM prd.DimProgramType WHERE ProgramTypeCode=@ApprovedProgram)
    THROW 51021,'Approved program code was not found; no permission was granted.',1;
INSERT INTO mtd.ProgramScope (UserPrincipalName,ProgramTypeKey)
SELECT @ApprovedUPN,p.ProgramTypeKey FROM prd.DimProgramType p
WHERE p.ProgramTypeCode=@ApprovedProgram AND NOT EXISTS (
    SELECT 1 FROM mtd.ProgramScope s WHERE LOWER(s.UserPrincipalName)=LOWER(@ApprovedUPN)
    AND s.ProgramTypeKey=p.ProgramTypeKey
);
SELECT s.UserPrincipalName,p.ProgramTypeCode FROM mtd.ProgramScope s
JOIN prd.DimProgramType p ON s.ProgramTypeKey=p.ProgramTypeKey
WHERE LOWER(s.UserPrincipalName)=LOWER(@ApprovedUPN);
-- Repeat only for each additional explicitly approved program grant.
