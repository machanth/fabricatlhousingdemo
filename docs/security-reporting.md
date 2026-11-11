# Security and reporting

## Explicit semantic model

`SM_HouseholdsServed` is deployed explicitly through the supported OneLake-table
creation API and configured from its real TMSL export. Its partitions are Direct
Lake on OneLake, not an assumed default model. It includes production dimensions,
three production facts, DQ results and the disconnected security map, not staging
or AnswerKey. `scripts\deploy_model.py` preserves this configuration reproducibly.

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

The supplied expressions are persisted as actual model measures, not merely
query-scoped definitions. Surrogate keys are hidden. Unnecessary HouseholdID,
MemberKey, SourceUnitKey and PropertyManager columns are physically excluded from
the model. Hiding a field is not security; underlying Warehouse access must also
be governed before granting users access.

The actual January/July/December DAX query has reconciled all 17 metrics for 27
program-months. `scripts\validate_model.py` repeats this comparison, and the master
notebook frames the model before querying it. Structural blank program rows are
explicitly excluded, not confused with an extra real program.

## ProgramScope RLS

The deployed model includes only the physical `mtd.ProgramScope` security map
from metadata, disconnected and hidden. It is currently empty. Populate it only
from an approved UPN/program mapping; do not expose other control tables.

The unassigned `ProgramScope` role uses `semantic-model/ProgramScope.dax`
on DimProgramType and the table filter
`LOWER(ProgramScope[UserPrincipalName]) = LOWER(USERPRINCIPALNAME())`
on ProgramScope itself so role members cannot query other users' mappings.
Unmapped role members must see no programs. An unassigned role does not
automatically restrict every workspace user or constitute a completed access grant.

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

`RPT_MTW_Detail_HT` is an actual deployed report. Reusable PBIR is under
`report\RPT_MTW_Detail_HT.Report`; `report\layout.json` is its companion layout and
acceptance summary. It contains:

1. Single-select month slicer that filters every visual.
2. Occupied Units matrix: HouseholdType then Category on rows, program on columns,
   Households as values. Preserve household-program-month observation counts.
3. Inventory matrix: LIHTC Units, Vacant Units, Available Units and Total Units by
   program. Per-cell negative vacancy font is red. Voucher inventory is blank.
4. Supportive matrix with VASH/Other split by household type and program.
5. Definition tooltips and a DQ page showing rule, severity, run ID and timestamp,
   including Blocked outcomes.

Do not sum availability across a disconnected month slicer or subtract voucher
households from unit-based inventory at a grand total. The supplied Vacant Units
measure uses unit-based households and preserves blank non-applicable inventory.

Actual browser checks verified the three matrices for January, July and December,
expanded categories, strict single-month selection (including Ctrl-click), red
negative vacancy and the DQ page. Warm month interactions measured
0.405/0.414/0.409 seconds; page reload measured 3.938 seconds and exceeds the
three-second full-page target. These are rendered-correct-totals timings, not
Performance Analyzer or a cold-capacity measurement. Cold/warm capacity acceptance
remains open; no universal timing guarantee is claimed. Real report/model
definitions are preserved in the private repository.
