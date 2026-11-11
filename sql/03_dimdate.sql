IF OBJECT_ID('prd.DimDate') IS NULL
BEGIN
    WITH digits AS (
        SELECT n FROM (VALUES(0),(1),(2),(3),(4),(5),(6),(7),(8),(9)) d(n)
    ), numbers AS (
        SELECT a.n+10*b.n+100*c.n+1000*d.n AS n
        FROM digits a CROSS JOIN digits b CROSS JOIN digits c CROSS JOIN digits d
    ), dates AS (
        SELECT DATEADD(day,n,CONVERT(date,'20150101',112)) AS [Date]
        FROM numbers WHERE n<5844
    )
    SELECT [Date],YEAR([Date])*10000+MONTH([Date])*100+DAY([Date]) AS DateKey,
           YEAR([Date]) AS CalendarYear,MONTH([Date]) AS MonthNumber,
           DATEPART(quarter,[Date]) AS QuarterNumber,DATEPART(iso_week,[Date]) AS ISOWeek,
           CONVERT(char(7),[Date],126) AS MonthYear,
           CAST(CONCAT(YEAR([Date]),'-Q',DATEPART(quarter,[Date])) AS varchar(7)) AS QuarterYear,
           DATEFROMPARTS(YEAR([Date]),MONTH([Date]),1) AS MonthStartDate,
           CAST(CASE WHEN DATEDIFF(day,CONVERT(date,'19000101',112),[Date])%7 IN (5,6)
                     THEN 'Yes' ELSE 'No' END AS varchar(3)) AS IsWeekend,
           CAST(NULL AS int) AS AgencyFiscalYear
    INTO prd.DimDate FROM dates;
END;
IF (SELECT COUNT(*) FROM prd.DimDate)<>5844
    THROW 51015, 'DimDate must contain exactly 5844 rows.', 1;
