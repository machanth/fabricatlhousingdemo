# Security and reporting

## Explicit semantic model

After all data gates pass, open `WH_ATL_HS`, choose **New semantic model**, select
Direct Lake explicitly and name it `SM_HouseholdsServed`. Include production
dimensions and the three production fact tables, not staging or AnswerKey.
The model must be created explicitly; no default semantic model is assumed.

| From fact column | To dimension column |
|---|---|
| FactHouseholdSnapshot.EffectiveDateKey | DimDate.DateKey |
| FactHouseholdSnapshot.ProgramTypeKey | DimProgramType.ProgramTypeKey |
| FactHouseholdSnapshot.PropertyKey | DimProperty.PropertyKey |
| FactHouseholdSnapshot.UnitKey | DimUnit.UnitKey |
| FactHouseholdSnapshot.VoucherTypeKey | DimVoucherType.VoucherTypeKey |
| FactHouseholdSnapshot.ActionTypeKey | DimActionType.ActionTypeKey |
| FactHouseholdSnapshot.IncomeSourceKey | DimIncomeSource.IncomeSourceKey |
| FactUnitAvailability.EffectiveDateKey | DimDate.DateKey |
| FactUnitAvailability.ProgramTypeKey | DimProgramType.ProgramTypeKey |
| FactSupportiveHousing.EffectiveDateKey | DimDate.DateKey |
| FactSupportiveHousing.ProgramTypeKey | DimProgramType.ProgramTypeKey |

Each relationship is many-to-one from fact to dimension, with **single-direction**
filtering from dimension to fact. Do not relate facts to each other or create a
FamilyMember-to-monthly-fact many-to-many relationship. Unit.PropertyID is an
attribute, not an additional DimUnit->DimProperty active relationship; the snapshot
already holds the correct effective-dated PropertyKey.

Install the provided query-scoped `DEFINE MEASURE` expressions as model measures
(DAX query definitions alone do not persist measures). Hide surrogate keys and
household identifiers from normal reporting. Avoid adding source personal columns;
hiding a field does not secure its contents.

Run `semantic-model/reconcile.dax` in DAX query view for January, July and December,
export the 27 program-month results privately, and full-outer-compare all 17
metrics with staging AnswerKey. Confirm Direct Lake partitions and framing; do not
silently accept Import or DirectQuery fallback as passing Direct Lake acceptance.

## ProgramScope RLS

Populate `mtd.ProgramScope` only from an approved UPN/program mapping. Expose a
secured physical copy as `prd.ProgramScope` before adding the mapping to the model,
or explicitly approve inclusion of the metadata security table; do not expose
unnecessary control data. Keep mapping disconnected, hidden, and unavailable as an
unrestricted report table.

Create role `ProgramScope`. Put the expression from `semantic-model/ProgramScope.dax`
on DimProgramType. Add a table filter
`LOWER(ProgramScope[UserPrincipalName]) = LOWER(USERPRINCIPALNAME())`
on ProgramScope itself so members cannot query other users' mappings.
Unmapped users must see no programs.

Assign an approved test user to the role. Test both "View as" and an actual
**Viewer** session with model access. Workspace Admin/Member/Contributor roles are
not valid evidence of Viewer RLS enforcement. Verify household, supportive and
availability facts are all filtered through DimProgramType. Do not grant workspace
Contributor merely to make RLS testing easier.

No approved mapping, test Viewer, Entra groups or sensitivity label has been
provided. Those security acceptance steps are pending, not automatically inferred.
Apply only an approved existing label and verify export inheritance with actual
permissions; a label name in documentation is not proof of enforcement.

## HT1-HT10 report

`report/layout.json` is an explicit build specification, **not an exported PBIP or
deployed report**. Create `RPT_MTW_Detail_HT` from the completed model:

1. Single-select month slicer that filters every visual.
2. Occupied Units matrix: HouseholdType then Category on rows, program on columns,
   Households as values. Preserve household-program-month observation counts.
3. Inventory matrix: LIHTC Units, Vacant Units, Available Units and Total Units by
   program. Set negative vacancy font/background red. Voucher inventory is blank.
4. Supportive matrix with VASH/Other split by household type and program.
5. Definition tooltips and a DQ page showing rule, severity, run ID and timestamp,
   including Blocked outcomes.

Do not sum availability across a disconnected month slicer or subtract voucher
households from unit-based inventory at a grand total. The supplied Vacant Units
measure uses unit-based households and preserves blank non-applicable inventory.

Acceptance requires actual Performance Analyzer/capacity observations for cold and
warm visual loads on the existing F8. The target is under three seconds; no timing
is promised before measurements. Save the finished report and model definitions
back into the private repository after reviewing exports for sensitive metadata.
