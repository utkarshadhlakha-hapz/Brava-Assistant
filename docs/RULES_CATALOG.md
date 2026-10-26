# Rules Catalog — Brava Cedar Shake

**Created:** 2026-08-10
**Verified against the guide PDF:** 2026-08-17 — values below were checked line-by-line against the source document; corrections are noted inline.
**Interaction notes updated:** 2026-08-26
**Source:** Brava Cedar Shake Installation Guide (June 13, 2023) + rule variety observed in the current codebase.
**Purpose:** Authoritative reference for implementing each `IPlacementRule` in `Roofing.Domain.Rules`. Values are **default rule data**, carried on `RuleDefinition` assets — never hardcoded in engine logic.

Read with: [FRAMEWORK_DESIGN.md](FRAMEWORK_DESIGN.md) §5 (rules engine).

**Implementation status (2026-08-28):** M2 implemented `ExposureRule`, `KeywayRule`, `SidelapRule`, and `CutEligibilityRule`. M5 implemented `StarterCoursePolicyRule`, `FastenerCountRule`, `FastenerPositionRule`, `CutAmountRule`, and course progression. M6 adds `SlopeEligibilityRule`, `SlopeCapAngleRule`, and `RidgeInstallLastRule`, authors slope/membrane data on roof faces, and includes `OverhangRule` and `RakeEdgePolicyRule` in both Brava RuleSets. Runtime roof/TileSet/exposure selection, player-drawn chalk lines, and the pooled install-last ridge-cap flow are wired in the Sandbox; physical Quest validation remains.

> **Guide vs. our rules.** Some guide statements are hard requirements (keyway 3/16" — below it "will void warranty coverage"), some are recommendations (Solid Shakes at rakes "for the most natural aesthetic"), and some are arithmetic consequences rather than constraints (the 12"/2" course lap). Where we choose to be stricter than the guide, that is called out explicitly and the severity is kept in **data** so a scenario can relax it without a code change.

---

## Tile types (materials)

Guide §1.1 (Materials) + the Specifications table. **Length and width are different axes — do not conflate them.**

| Role | Length | Width | Where | Cuttable | Notes |
|---|---|---|---|---|---|
| Starter | **12"** | 12" | Eaves | — | Thick edge toward eave; a 12" piece at a ½" overhang puts its head on the 11½" line |
| Field Shake | 22" | **5" / 7" / 12"** | All roof sections | No (field) | Structural ribbing on back |
| Solid Shake | 22" | 12" | Rakes, valleys | **Yes** | Solid back — no exposed ribbing when cut |
| Hip/Ridge Cap | 14" | 5½" (height 6") | Hips, ridges | trim only | Angle chosen by slope (see `SlopeCapAngleRule`) |

**Shared shake specifications**

| Spec | Value |
|---|---|
| Length (Field & Solid) | 22" |
| Widths | 5", 7", 12" |
| Thickness | ½" – 1" |
| Fastener locator position | **11" from top and bottom** |
| Maximum exposure | 10" |
| Minimum keyway | 3/16" |
| Minimum sidelap | 1½" |

The 22" length with the locator at 11" is *why* a ≤10" exposure guarantees fastener coverage and a 12" course-to-course lap — the geometry is derived, not arbitrary.

## Rule results carry evidence (2026-09-09)

`RuleResult` has an optional `RuleEvidence?`. A failing rule reports not only how far out the
placement was but the face-space geometry it measured along, so the error lines drawn on the roof
start at the reference the rule actually used rather than at one a presenter re-derived.

- **`RuleEvidence.Span`** - a reference segment, the subject edge, the measured value and the limit
  or range it missed. Used by `keyway`, `sidelap`, `overhang`, `exposure` and the starter flush
  check.
- **`RuleEvidence.At`** - a point and text, for a failure that is not a distance: an unsuitable tile
  type, a row started from the wrong end, a cut that cannot be made. These get anchored text and no
  line, because a line would show a measurement that was never taken.

The geometry reaches the rules on `PlacementContext.References` (`MeasurementReferences`), filled by
`PlacementMeasurer.Describe` from the same neighbour and joint lookups `Measure` uses. `Measurements`
is unchanged in shape and still carries only scalars. A context built without references evaluates
exactly as before and its results carry no evidence, so **no authored threshold changed** and no
existing rule verdict moved.

`FastenerCountRule` and `FastenerPositionRule` deliberately carry no evidence. `FastenerCountRule`
reports a half-nailed shake as `Invalid` as progress reporting rather than as a workmanship failure
(see the comment in `FastenerTool.TryDriveFastener`), so annotating it would put a label on every
shake mid-fastening.

## Rule reference (one row → one `IPlacementRule`)

### ExposureRule
- **Definition:** distance between course head lines (how much of each shake is exposed).
- **Project values:** selectable target **8" / 9" / 10"**; operating band **8"–10"**. Below 8" is a `Warning`; above 10" is `Invalid`.
- **Guide distinction:** guide §2.3 allows a maximum of 10" and suggests a 4" minimum. The training project intentionally adopts the stricter 8" minimum; this is a product/training constraint, not a claim that the guide requires 8".
- **Evaluate:** measured exposure against the selected/per-face target and the 8"–10" outer band. A target miss or value below 8" warns; a value above 10" is invalid.
- **Inputs from context:** proposed placement Y in face-space, course line below.
- **Note (authoring caveat, not a rule):** the moulded exposure guidelines on each shake only mark the *maximum* 10" exposure. Guide §2.3: "If setting less than 10-inch exposure, do not use guidelines to set exposure." If we ever visualise guidelines, they must not be shown as valid targets below 10".

### KeywayRule
- **Definition:** gap between adjacent shakes within the **same** course.
- **Values:** **warranty minimum 3/16"** (0.1875"); **recommended 3/8"** (0.375").
  Guide §2.4: installing below 3/16" "will void warranty coverage"; "Using a recommended 3/8-inch keyway spacing will ensure compliance with this standard."
- **Rationale:** the gap exists for thermal expansion/contraction, so it is a hard minimum, not an aesthetic preference.
- **Evaluate:** horizontal gap between proposed tile and its left/right neighbour in the course. Model as **two thresholds**: below 3/16" → `Invalid`; between 3/16" and 3/8" → `Warning` (compliant but below recommendation); ≥ 3/8" → `Valid`. This is why `RuleSeverity` needs `Warning` and not just a boolean.
- Fasteners must never be exposed in the keyway (enforced by `FastenerPositionRule`, not here).

### SidelapRule (joint offset between courses)
- **Definition:** horizontal offset between a shake's edges/joints and the joints of the course **below**.
- **Value:** **≥ 1½"** minimum offset, for "all Field Shakes, Solid Shakes, and Starters" (guide §2.4).
- **Purpose (per guide):** lets water shed as designed **and covers the fasteners of the course below** — so a sidelap failure is a leak/fastener-exposure failure, not cosmetic.
- **Method:** achieved by mixing the 5", 7" and 12" widths "in a random order". The end-tile/width-selection algorithm is ours to design (see open questions).
- **Evaluate:** distance from proposed tile joints to nearest joint in the course below.
- **Severity (framework decision, 2026-09-14):** authored on `SidelapRuleDefinition._violationSeverity`. Brava authors **Warning**: a shake with too little sidelap attaches as an ordinary install (locators shown, nailing allowed, next shake allowed, no correction latch), the held preview still shows the shortfall message, and `RoofInspectionService` promotes it to an **error** in the Show Errors panel. The constructor default stays Invalid.

### StarterCoursePolicyRule — shared Brava eave start
- Course B requires starter support and its physical butt must match A within the authored tolerance.
- A and B are marked fixed by the eave layout, so `ExposureRule` does not judge either placement.
- Placing C establishes and validates the selected exposure relative to B.
- `OverhangRule` independently requires the authored eave overhang on both A and B.

### HeadlapRule (vertical coverage) — *derived, verify before implementing*
- **Definition:** vertical overlap of a shake onto the courses below.
- **Guide text (§2.4):** shakes are 22" long with the fastener locator 11" from top and bottom; keeping exposure ≤ 10" maintains a **12" lap course-to-course**, which "will create a 2-inch lap of each 3rd course".
- **Important:** these numbers are **arithmetic consequences** of `22" length` and `exposure ≤ 10"` (22 − 10 = 12; 22 − 2×10 = 2). They are **not an independent constraint** — if `ExposureRule` passes and the shake is 22", headlap is satisfied automatically.
- **Implication for us:** do **not** implement this as a redundant rule that can contradict `ExposureRule`. Either (a) omit it and let `ExposureRule` own the vertical axis, or (b) implement it as a *derived measurement* surfaced in `Measurements` for training feedback ("current headlap: 12\"") with no independent verdict. Preference: **(b)**.
- **Do not confuse with joint stagger.** "2-inch lap of each 3rd course" is *vertical* coverage. It says nothing about horizontal joint alignment.

### JointStaggerRule — *NOT in the guide; SME decision required*
- **Status:** The June 13 2023 guide specifies **no** rule preventing joints from aligning across 3 courses. Its only horizontal-offset requirement is `SidelapRule` (1½" vs the course below).
- **Why it's listed:** the previous codebase carried a "recurrency" penalty, implying joint-alignment-over-N-courses was scored. That is a **training/aesthetic preference, not a Brava requirement.**
- **Action:** do not implement as `Invalid` on guide authority. If the SME wants it, add it as a separate optional rule emitting `Warning` + penalty, with N and the tolerance as `RuleDefinition` data. Record the SME decision in DEVLOG.md.

### OverhangRule
- **Definition:** how far starters/shakes overhang the edge.
- **Values:** **eave ½"**, **rake 1"** (measured from fascia, not edge metal).
- **Evaluate:** proposed placement vs edge type (`Eave`/`Rake`) overhang target.

### FastenerCountRule
- **Value:** **2 fasteners per shake**, for every role. Fastener *type/length* varies by role and wind regime (guide §2.7):

| Application | Fastener |
|---|---|
| Standard | Two (2) ring shank roofing nails **or** two (2) screws; 1¾" collated ring shank nails permitted if penetration is met |
| **Hip/Ridge Cap** | Two (2) **3"** screws or two (2) **3"** ring shank nails (longer — multiple layers + flashing/vent beneath the cap) |
| **High wind** (highest wind warranty) | Two (2) **#8 × 2"** corrosion-resistant screws |

- **Evaluate:** number of placed fasteners == 2 for the tile role. Fastener *length* is a loadout/authoring concern (`TileDefinition` / scenario config), not a per-placement geometric check — keep it out of this rule.

### FastenerPositionRule
- **Constraints (guide §2.7, §4.2, §4.4):**
  - Install **no lower than** the fastener locator — the locator marks the *lowest* permitted line, not an exact point.
  - Fasteners "may be moved **slightly up and out** from the fastener locator" when sidelap, keyway, flashing or valley metal requires it. So the valid region is a **zone extending up/outward from the locator**, not a point — a rule that demands an exact locator hit would be wrong.
  - Prefer penetrating the **fastener pad** on the back of the shake.
  - ≥ **¾"** penetration into the deck, or completely through it.
  - **Never exposed:** not in the keyway between shakes, not beneath the exposure line, not anywhere uncovered/unsealed.
  - **Narrow pieces (2026-09-25, user decision):** a shake too narrow to hold the keyway clearance on both sides (width < 2 × (`_minimumKeywayClearanceInches` + 1/16", so about 1 1/8" at the Brava 0.5") is not asked for it. Otherwise a closing sliver refused every nail, and a replacement was sawn to the same width, so the row could never be finished. Still 2 nails, and locator, exposure line, deck penetration and exclusion checks still apply. `FastenerPlan.ShakeWidth` carries the width; `FastenerPositionRule.CanHoldKeywayClearance` decides.
  - **Not within 5"** of: valley **centre crimp**, a **penetration**, or a **chimney** (three separate cases, same distance).
- **Evaluate:** each fastener position vs the locator zone + the 5" exclusion regions + the covered-area test.
- **XR assistance is not a rule tolerance:** `FastenerToolAdapter` may resolve a near miss within 0.10 world units to the next unfilled locator. The resolved point is then evaluated normally. Raw impacts outside the assist search and invalid domain proposals remain rejected; neither the 11″ locator value nor any rule threshold is widened.
- **Final field course:** when a ridge cap is planned, fastening coverage uses the cap's lower
  edge (ridge line minus half its authored cross-ridge length), rather than a nonexistent next
  field row. This applies only where no field course laps the shake. *Reaching* the ridge does not
  qualify a shake: every course whose stock overruns the ridge is trimmed back to it, so a shake
  well down the slope can touch the ridge line and still be covered by the course above, whose
  ordinary exposure line is the one that applies.
- **Cut tiles keep their moulded holes:** the locator is a fixed distance up from the butt (11″ on
  a 22″ shake) and a length cut takes the head and leaves the butt, so the hole does not move.
  Both Brava targets sit on that one line after a length cut; a width cut changes only their X
  spacing. Reading the line as a share of the *retained* length instead walks both nails half-way
  down whatever the saw removed, which put them under the cap's lower edge and made a ridge-trimmed
  shake impossible to fasten.
- **Raising a target to stay covered:** where the covering edge sits above the moulded hole — the
  cap's lower edge on the final row can — both targets move up to clear it, bounded by the same
  upward tolerance the rule allows and by the material left on the shake. This is the guide's
  "slightly up and out", applied by the view; no rule threshold is widened.
- **Downward tolerance on final course:** the check against `plan.ExposureLineHeight` uses
  `downwardTolerance.Value` (0.25") rather than a hardcoded 0.05" margin, so fasteners on ridge-trimmed
  shakes where moulded holes sit ~0.17" below the cap coverage line are accepted as legal.
- **Open:** the numeric tolerance for "slightly up and out" is not given in the guide — needs SME input (see open questions).

### CutEligibilityRule
- **Rule:** only **Solid** shakes may be cut; Field Shakes (5"/7"/12") may **not** be cut.
- **Value:** `TileType.Cuttable` (Solid = true, Field = false).
- **Nuance:** the guide's language is a *recommendation* for aesthetics ("Brava recommends using the Solid Shake accessory at valleys and rakes… no structural ribbing will be exposed"), and it offers D-style flashing as an alternative to conceal ribbing on cut Field Shakes. We are choosing to enforce it as a **hard training rule**, which is a deliberate stricter-than-guide decision — keep it as rule *data* (a severity setting) so it can be relaxed to `Warning` per scenario without a code change.
- **Evaluate:** reject any cut request on a non-cuttable tile **before** any geometry/state change.
- **Implementation (2026-09-14):** Brava's Field definitions are now authored cuttable, so the hard rule above is replaced by a positional one. With the authored flag `_fieldWidthCutsOnlyAtRowEnd` on (Brava), a **width** cut on a **Field** shake in a field course is `Invalid` unless the shake closes its row: *"A Field shake can only be cut when it is the last shake of a row."*
  - **Closing piece** (`CutEligibilityRule.IsClosingPiece`): at the rake the course is laid towards (`Course.Direction` with `Measured.IsLeftRake` / `IsRightRake`), or at a valley. Measured on the trimmed footprint.
  - **Length cuts are exempt:** a Field head trimmed at the ridge or stopped under a window is judged as before.
  - **Solid shakes are unaffected.** Only a Solid opens a row at a cut width (automatic 5" on row 2, width menu from row 3); a Field shake opening a row is laid whole (`OpeningCutSelection.IsOpeningPiece`).
  - The flag defaults off, so other products keep the capability-only check.
- **The 5" and 7" Field shakes are never width-cut (2026-09-25, user decision).** `TileDefinition._allowWidthCut` is false on `BravaField5` and `BravaField7`. `PlacementController.EvaluateProposal` refuses, as a **gate** (the shake stays in the hand under a red ghost, never attached for correction), any such tile whose footprint would end up narrower than its authored width, with the message *A 5" shake cannot be cut. Use a 12" Field or a Solid here.* `_isCuttable` stays on, so ridge and window length trims still work. Guidance already routes a gap no stock shake fits to the Solid. The hand saw is never offered on a Field (`OpeningCutSelection.IsOpeningPiece` is Solid-only), so nothing else can cut one.
- **The closing Field is seated at the rake before it is trimmed (2026-09-25).** `CourseProgression.SeatAtClosingRake`, called after `FitWholeIntoOpenSpan`, slides a Field released short of the finishing rake out to the rake overhang when the stretch there is too narrow for it whole. `ClampToOpenSpan` then trims only the interior side, so the piece measures as the last of the row and `IsClosingPiece` is true. Without it the piece was clamped to a sliver that touched neither the rake nor the overhang, the cut was refused, and the correction commit laid the full-width shake through its neighbour. Opening rake: unchanged (a Field there is still refused).

### CutAmountRule
- **Rules:** straight even cuts; **factory edge to the outside**; at hip/ridge cut both sides the **same distance**, minimum **3/16"** from the hip/ridge; closed valley — shakes cut along the centre crimp leaving a **3/16"** expansion gap.
- **Evaluate:** requested cut line vs edge type + min distances.
- **Related authoring data (not placement rules):** valley flashing extends **10"** from the centre crimp each side for slopes ≥4:12, or **14"** for ≤3:12; open valley "W" metal uses a 1" centre crimp, closed valley 1½". These belong on the `RoofDefinition`/valley authoring, not in a placement rule.

### EdgeTilePolicyRule
- **Rule:** use Solid Shakes at rakes/valleys (aesthetic + no exposed ribbing). End tile of a row that needs cutting should be Solid.
- **Evaluate:** tile role vs edge type of the placement position.
- **Solid/Field spread (review only, `SolidRowInspection`):** judged per installed field course by the Show Errors panel. Starter and ridge courses are not judged. None of these refuse a placement: the shake still attaches and fastens.

  | Situation | Rule ID | Panel severity |
  |---|---|---|
  | Field shake at a row end (rake or valley) | `rake-edge-policy` | **Error** (the placement verdict stays a Warning) |
  | Solid shake away from a row end without a width cut (including a length-only ridge trim) | `interior-solid` | Warning |
  | 3rd or later shake of the same width in an unbroken run, in laying direction (Solid or Field alike) | `consecutive-same-size` | **Error** ("Recurring"), alongside any mid-row warning |

  - **Size, not role, is counted.** 12" Solid, 12" Field, 12" Solid is a run of three; 12", 7", 12" is not. Widths within ¼" are the same size.
  - A run is broken by a different width, a starter or ridge cap, or a gap at least as wide as the narrowest shake (a hole). A keyway doesn't break it.
  - **Cut shakes count at the width they were cut to.** A shake cut to 7" continues a run of 7" shakes and breaks a run of 12" ones.
  - The `interior-solid` warning exempts width-cut filler Solids. A length-only ridge trim does not exempt a mid-row Solid. Inspection compares retained width with original stock width, including tile scale. Final-row guidance uses Field stock inside the row and Solid stock at its ends before fitting the ridge length.

### StarterCoursePolicyRule
- **Rules:** starter installed at the eave, **thick edge toward the eave**, with ½" eave / 1" rake overhang; the field first course is installed **flush with the starter** using a combination of shake widths to hold 1½" sidelap.
- **Chalk line:** the starter line is chalked to set the ½" eave overhang and lands "about **11½"** from the eave" (guide §3.1). Appendix E step 1 is explicit about what it marks: "snap a line to place **head of the Starter**". It is a *consequence* of the **12"** starter with a ½" overhang — not of the 22" field shake — and the guide says "about", so it is a derived guideline value with tolerance.
- **What "flush" means for Brava:** the first field course and starter share the same physical lower
  edge and ½" eave overhang. Their different lengths put their alignment lines at 11.5" and 21.5".
- **Evaluate:** first-course placement vs starter presence, shared eave start, and eave overhang.

### CourseProgressionRule (project training sequence)
- **Rule:** course indices **0 and 1** begin at the high-X/right rake and progress **right-to-left**. Course index **2** flips to low-X/left-rake start and **left-to-right**; every later course alternates.
- **Numbering:** index 0 = Starter/physical Row 1; index 1 = first Field/physical Row 2; index 2 = physical Row 3. UI copy should prefer physical row labels while code and tests use zero-based course indices.
- **Higher rows stay locked until every lower row is complete (2026-09-29).** `PlacementController` checks `AreCoursesBeforeComplete` before opening-cut selection, automatic fitting, or rule evaluation. A locked row shows no held-tile ghost and refuses release with *"Complete row N before starting row M."* This is an unconditional gate in Guided and Freeform, including when a wrong position would otherwise attach for slide correction or direction enforcement is disabled. Row completion still uses the existing coverage/trim rules and fastening settings; mistakes within an unlocked row retain normal correction behavior.
- **Face-order refusal is silent in the popup layer (2026-09-29).** `unfinished-face` still blocks placement on another face and appears in ordinary placement feedback, but does not show, replace, or dismiss the animated guidance popup. Face-completion and ridge-ready progress announcements remain enabled.
- **Evaluate:** the first shake must touch the course's starting rake; later shakes must have the prior neighbor/keyway on the progression side. A shake with nothing behind it (no starting rake, no prior neighbor) has skipped ahead and is refused with "Start from the rake". Violations are `Invalid` in the authored Brava training asset.
- **Gap fill (2026-09-14):** a shake with something behind it (the starting rake or an installed neighbor) *and* an installed neighbor already ahead of it is filling a slot in a row laid past that point. It is `Valid` for progression; keyway and sidelap still judge the fit. This is what refilling a crowbar hole looks like, whether the hole is mid-row or at the starting rake. The old "Place tiles consecutively" refusal covered exactly this case and was removed. When the first shake is placed away from its starting rake, the rule emits a `RuleEvidence.Span` between the starting rake edge and the shake's edge, measuring the gap distance against target `0"` so error annotation lines and numbers are drawn.
- **Refilling a crowbar hole (2026-09-17):** the hole is exactly as wide as the shake removed, and every extra joint costs another keyway. A 12" hole therefore takes a 12" shake, not 7" + 5" (that needs 12.75"). The second piece would have to be trimmed, and `CutEligibilityRule` allows a Field width cut only at the row end, so it is committed for correction and cannot be nailed. Finish such a hole with a Solid, which is cuttable anywhere, or refill with the width removed.
- **An unfilled hole holds the row (2026-09-21) is a gate, not a rule.** A filler narrower than the
  hole leaves bare deck behind it — a 7" piece in a 12" hole leaves about 4.6" — and nothing used to
  notice until the trainee tried to fill the sliver with a cut Field shake. `PlacementController`
  now refuses any proposal in a course whose first installable open stretch the footprint does not
  reach: *"Fill the gap in row N before laying anywhere else."* It is the same principle as
  `AreCoursesBeforeComplete`, applied along the row rather than between rows, and a gate rather than
  a rule because carrying on elsewhere is not a mistake to illustrate on the roof. The stretch comes
  from `CourseProgression.TryFindOpenStretch`, which is the public face of the same
  `TryFindNextOpenSpan` that `IsCourseComplete` reads — so the refusal and the row-is-finished check
  cannot disagree. A gap too narrow for any legal piece is deliberately not returned, so an
  unfillable sliver closes the row instead of stranding the trainee. Ridge courses are exempt.
- **Crowbar limit and short pieces (2026-09-17) are gates, not rules.** The crowbar only removes shakes in the highest occupied course of their face (`CrowbarTool.IsLockedIn`, toggle `_crowbarLatestRowOnly`). A shake already cut in length is refused before rule evaluation on a row a full shake fits, and on a top row (or under an opening) it does not reach. It is never committed for correction; a longer piece is sawn down by the ridge fit. See `CourseProgression.RequiredHeadForShortPiece`.
- **Guidance/snap:** `CourseProgression`, `CourseGuidance`, and `RoofSession` use the same direction function as the rule, including direction-ordered internal-gap recovery.

### SlopeCapAngleRule (roof-level)
- **Rule:** hip/ridge cap angle is chosen by slope. Three angles exist: **Low 160°**, **Standard 120°**, **Steep 90°**.
- **The bands differ between Ridge Cap and Hip Cap** — this is easy to get wrong and the guide lists two separate charts (§1.1):

| Cap type | Low (160°) | Standard (120°) | Steep (90°) |
|---|---|---|---|
| **Ridge Cap** | 4:12 or lower | 5:12 – 10:12 | 11:12 or higher |
| **Hip Cap** | 5:12 or lower | 6:12 – 14:12 | 15:12 or higher |

- **Caveat (guide note):** "Recommendations are for symmetrical Hip/Ridge only" (e.g. a 5:12 meeting a 5:12). Asymmetric hips/ridges require a calculated angle or Brava Technical Support. The rule should therefore only issue a verdict for symmetrical joints and return an explicit "cannot determine — asymmetric" result otherwise, rather than guessing.
- **Also:** hip/ridge installed exposure must match Field Shake exposure, max 10" (§4.3) — reuse `ExposureRule` rather than duplicating it.
- **Evaluate:** selected cap angle vs roof slope band **and** cap type (hip vs ridge).

### SlopeEligibilityRule (roof-level)
- **Values (guide §2.2):** recommended minimum slope **4:12**. Warranty minimum **3:12**, and only *with* Ice & Water Shield over the entire slope. Below 3:12 Brava considers the installation **decorative** and it falls **outside the 50-year warranty**.
- **Evaluate:** three bands, not one threshold — `≥4:12` Valid; `3:12–4:12` Warning (requires Ice & Water); `<3:12` Invalid/decorative.
- Useful for authoring validation on `RoofDefinition` (catch an out-of-spec roof at author time, not at placement time).

## Penalty / scoring hooks (from codebase)

Rules may emit penalties for training scoring: keyway, sidelap, exposure, rake-edge (solid), nail/fastener, and recurrency penalties. `RuleResult.Penalty` + payload feed a stats/scoring service outside the domain rules.

## Extensibility note

Each rule above is one `IPlacementRule` + one `RuleDefinition` (with the values as fields). Adding a rule (e.g., a region-specific high-wind fastener rule) = a new class + asset, added to a `RuleSet`. A check that needs the whole course and must not refuse placement (such as the Solid spread above) belongs in `RoofInspectionService` instead. The engine and existing rules never change.

## Open domain questions (confirm with SME in the new project)

**Resolved by the guide** (no SME needed):
- ~~Exact allowed keyway band~~ → **Resolved.** 3/16" is the *warranty minimum*, 3/8" is the *recommended* spacing (§2.4). Both are real values with different severities — model as Invalid / Warning / Valid.
- ~~Precise stagger tolerance for the "2" on 3rd course" check~~ → **Resolved as a mis-reading.** That figure is *vertical headlap* derived from 22" shakes at ≤10" exposure, not horizontal joint stagger. There is no guide rule on joint alignment across 3 courses. See `HeadlapRule` / `JointStaggerRule` above.
- ~~Which exact field widths ship~~ → **Resolved.** 5", 7", 12" widths, all 22" long, thickness ½"–1" (Specifications table).

**Still genuinely open:**
- **End-tile / width-selection algorithm.** The guide says to mix the 5"/7"/12" widths "in a random order" to achieve sidelap, but prescribes no algorithm. We must design one (and decide whether the trainee picks widths or the system suggests them).
- **Fastener pad tolerance.** The locator marks the *lowest* allowed line and sits 11" from top/bottom, but the guide gives no explicit tolerance for placing a fastener above/lateral to it. It only says a fastener may be moved off the locator when sidelap/flashing requires it. Need a numeric tolerance for scoring.
- **Whether to score joint stagger at all** (see `JointStaggerRule`) — a training preference, not a Brava rule.
- **Staggered-exposure installation (Appendix D).** Whether the framework must support deliberately varied exposure per course; this interacts with `ExposureRule` being a simple band.

## Course planning: the ridge cap roofs the top band

Not a validation rule either, but the geometry that decides how many field courses a slope gets.

A hip/ridge cap straddles the ridge and hangs half its authored cross-ridge length down each
slope, so the band from the cap's lower edge up to the ridge is roofed by the cap, not by the
field. `CoursePlan` therefore does not plan a field course whose butt line sits inside that band:
such a course laps almost entirely onto the row below it, disappears under the cap once that goes
on, and reads on the roof as a duplicate row laid over a finished slope.

On the authored training slope (34.44" eave to ridge, 12" cap) the cap reaches down to **28.44"**,
and a fixed 10" exposure would otherwise plan a course at **29.5"**. Dropping it leaves three field
courses showing 10", 10" and 8.94" — and two chalk lines rather than three.

This lives in `CoursePlan` rather than in an `ICourseLayoutStrategy` because it is a fact about the
roof, not a method of dividing it: every strategy divides the slope its own way and none of them can
see the cap, so doing it once in the plan means a new strategy inherits the behaviour. At least one
field course always survives, so a cap authored deep enough to swallow the slope produces a roof
that looks wrong rather than a face with nothing to install.

**Which layout suits a product depends on this.** Guide §3.1's fixed exposure leaves its remainder
exactly where the cap covers, so the two compose well and that is what the Brava sets author.
Appendix E divides the whole slope including the capped band, which on a short slope leaves a course
just below the cap showing under three inches — the very sliver the cap rule exists to remove.

## Ridge caps: one pass along the shared ridge

**Sequence.** Caps go on after *every* slope is covered and fastened, not after each one.
`RoofRuntime.FindWorkFace` runs two phases: the first returns any face whose
`IsShakeCoveringComplete` is false, so the trainee finishes one slope before starting the next; only
when all of them are covered does the second phase offer ridge work. A roof is run one slope at a
time and then capped once.

**One face owns the ridge.** Every `RoofSession` plans its own ridge course, because a session sees
only its own slope and the cap angle is derived from that slope's pitch. On a two-faced roof that
would ask for caps twice — once per slope, along the same ridge. `RoofRuntime.RidgeFace` (the first
face, in face order, that plans a ridge course) is the only one offered ridge work, so the run
happens once.

**Resolving a held cap.** A cap held over the ridge is equidistant from both slopes, so the
nearest-plane search decides it on float noise. `RoofRuntime.ResolveFace(worldPoint, role)` returns
`RidgeFace` for `TileRole.RidgeCap` regardless of position; everything else still measures.

**Angle.** `SlopeCapSelector` picks Low 160° / Standard 120° / Steep 90° from the face's rise per
12, in separate bands for hip and ridge, and `SlopeCapAngleRule` validates the piece against it. The
bands are the guide's §4.3 chart exactly — ridge: Low 4:12 or lower, Standard 5:12–10:12, Steep 11:12
or higher; hip: Low 5:12 or lower, Standard 6:12–14:12, Steep 15:12 or higher — and they are the
selector's default arguments so a product can override them from data. The chart is for a
*symmetrical* ridge (a 5:12 meeting a 5:12); an asymmetric one is out of scope and the guide sends
you to Brava.

**Exposure along the ridge.** Guide §4.3 step 6: *"Match Hip/Ridge exposure to Field Shake exposure
≤ 10-inches."* `CoursePlan` already gives the ridge course the face's `SetExposure` for exactly this
reason, and `CourseProgression.GetNextRidgeLeftEdge` advances the run by it. A 14" cap at the 8–10"
the rake offers therefore laps the cap before it by 4–6", which is intended — the cap's exposure is
what shows, not its width.

**The run, and the cut that closes it.** One pass, rake to rake, and the last cap is cut to whatever
run is left, the same way the closing shake at a rake is. See `RidgeCapInstallation.png` — the front
view marks the cut on the final piece. Five things carry it, and they only work together:

- `CourseProgression.GetNextLeftEdge` keeps the joint on the exposure right to the end of the ridge.
  It used to clamp a cap to `FaceBounds.Max.X - tileWidth`, which *slid the last cap backwards* over
  the one before it and closed the run by lapping rather than by cutting. On the Sandbox's 44.4882"
  ridge at the 10" exposure that put the fifth cap at 30.49", a tenth of an inch past the cap already
  at 30".
- `CourseProgression.GetGuidance` returns `requiresCut: true` for the cap that closes the run, names
  the width of ridge still open as its suggested width, and says so in the trainee-facing message.
- `RoofSession.Snap` stops a cap's footprint at `FaceBounds.Max.X`. Every earlier cap is untouched -
  its right edge is well inside - so only the closing piece reads as a trim.
- All three cap definitions are `_isCuttable: true`, so `CutEligibilityRule` accepts the piece.
- The three cap FBXs import `isReadable: 1`, which the cut presentation needs to reshape the mesh.

`RidgeClosingCutTests` pins the arithmetic against the real Sandbox ridge, because a round face
divides evenly and would prove nothing.

**The run hangs the rake overhang at both ends (2026-09-14).** The top course's shakes hang
`RakeOverhangInches` (1") past each rake, and a run that opened at `FaceBounds.Min.X` and was cut
flush at `Max.X` left both of those ends uncapped - and read to `OverhangRule` as flush, 0" against
its 1". `CourseProgression` now runs caps from `Min.X - overhang` to `RidgeRunEndX` (`Max.X +
overhang`): the first cap opens there, `GetRemainingWidth` and `IsCourseComplete` measure to it, and
`RoofSession.Snap` trims the closing cap to the same number. On the Sandbox at 10" exposure the caps
open at -1, 9, 19, 29 and the closing cap at 39 is cut to 6.49". With no authored overhang the run
is exactly what it was. `RidgeCapRakeOverhangTests` pins it.

**A cap laps the one before it by lying on it (2026-09-14).** Each cap after the first covers the
end of its predecessor; posed flat, the two occupied the same space. Pose only - footprints, rules
and fastening are unchanged - `PlacementController` finds the lapped cap with
`FaceLayout.FindPreviousRidgeCap` (the same lookup the ridge exposure uses) and
`FaceSpaceMapper.LapRidgeCap` raises the cap along the bisector and turns it about the across-ridge
axis through the step where the previous cap ends, so the leading end leans down to the roof. Both
are tuned by eye on **Placement Settings**: `Ridge Cap Lap Tilt Degrees` (default 3) and `Ridge Cap
Lap Lift World Units` (default 0.0127, about ½"). The ghost takes the same pose. Caps already
installed keep the pose they were committed with. `RidgeCapLapPoseTests` pins the transform.

**Caps are laid in order, and a gate refusal is not a correction (2026-09-14).** No rule judges where
along the run a cap goes - with no cap before it, its exposure reads as planned - so in Freeform a
cap released anywhere on the ridge passed and was then snapped to the next slot. The Sandbox's 0.5 m
reach then refused that slot, and `TryCommit` committed it "for correction" with no failing rule:
locators hidden, the nailer refusing it, the face blocked. `PlacementController.EvaluateProposal` now
refuses a cap released more than half an exposure from the next slot, naming where it goes, and
`TryCommit` commits a refused guided target for correction only when a *rule* refused it.

**A cap's footprint is half its depth, and that is not a trim.** `RoofSession.Snap` deliberately
gives a cap a footprint from `Max.Y - halfCapDepth` to `Max.Y`, because the other half hangs down the
far slope where this face cannot see it. `PlacementController.TryCommit` decides "was this cut?" by
comparing the footprint with the tile's authored size, and reading that half as a trim committed
*every* cap as cut - which asked `TileView` to saw an 11.5" piece down to 5.75", failed inside the
cut coroutine on the then-unreadable mesh, and left the placement half-applied. Only a cap's **run
along the ridge** can say whether it was cut; its depth never can.

**Fastening a cap is not fastening a shake, in three ways.** All three were flat-shake assumptions
applied to a folded piece, and together they made every cap permanently unfastenable.

- **Where the nail is.** A cap's two nails belong on opposite legs, and the far one hangs over the
  other slope. Projecting it onto this face's plane, the way `FaceSpaceMapper.WorldToFace` does for
  everything that lies *in* a face, puts it past the ridge and outside the half-footprint the cap
  was given. `FastenerTool.RidgeCapFacePoint` takes the run along the ridge from the projection -
  the ridge is the face's own X, so the fold cannot disturb it, and a trimmed closing cap still
  reads correctly - and the depth from the piece: how far the hole sits from the fold.
- **What laps it.** `CoursePlan.FastenerExposureLine` returned the ridge course's exposure. That
  number is the spacing of the cap *run* along the ridge (§4.3 step 6), not a line anything has to
  clear; read as a fastening line it asked for a nail 10" up a sub-six-inch leg. Nothing laps a cap
  from up the slope - the next cap laps it along X - so the line is `Inches.Zero`, as a starter
  course's is.
- **Where the locator is.** All three definitions carried an inset of 5.75", half the across-ridge
  width, which is the mid-length convention a flat shake uses and which lands on the fold. The
  moulded holes measure 2.56"-3.15" up the leg. Authored per SKU from the prefabs' own points (2.5"
  on Standard 120 and Steep 90, 2.6" on Low 160), with the shipped rule's 0.25" downward and 2" upward
  allowances covering a spread that is not symmetric about the fold. `RidgeCapFasteningTests` pins all
  three. In `TileView.GetDomainType()`, visual-driven tiles defaulted to `calculatedLength / 2f` (5.75"),
  which quietly overwrote the definition's inset and rejected every cap fastener; it now directly
  preserves the authored inset for `TileRole.RidgeCap`.

**Seating: a cap rests on what it touches, not on its bounding box.** `GetWorldPose` seats a flat
shake on the bottom of its collider volume, which for a shake is its underside; a cap's box bottom
is the plane through its two leg tips and its box depth is the height of the fold, so copying that
rule stood the piece a whole fold height off the ridge. `FaceSpaceMapper.GetRidgeCapWorldPose` now
slides the cap down the bisector until its collider geometry meets the roof. A ridge is a convex
corner, so the material is what lies below the near slope AND below the far slope, and a point is
clear of it as soon as it is above EITHER: each vertex names the cheaper of the two lifts that would
clear it, and the most demanding vertex decides. Clearing every vertex of every plane instead reads
the far leg - which hangs below the near slope's plane because it must - as a hole in the roof.
Nothing assumes the cap is symmetrical, that the ridge is, or that the two angles match, and
`RidgeCapSeatTests` pins all three regimes: fold matched, wider, and narrower than the ridge.

**Steep pitch mesh clearance and tilt offsets.** On steep asymmetrical gables like the Sandbox
(20.6:12 and 18.48:12), the geometric seat left the cap partially submerged in the roof mesh, hiding
the far-side leg and its fastener hole. Two serialized settings on `PlacementSettings` resolve this
without disturbing the domain:
- `_ridgeCapPositionOffsetWorldUnits` (`Vector3`, default `(-0.024f, 0.043f, 0f)`): shifts the cap along
  world X, Y, and Z to bring both legs proud of the mesh.
- `_ridgeCapRotationOffsetDegrees` (`Vector3`, default `(6.4f, 0f, 0f)`): tilts the cap +6.4° around
  local X (along the ridge axis) to balance the legs evenly across both slopes.

**The fold is not on the pivot, and the caps are asymmetric.** Decoded from the baked collider
meshes: the fold sits at local **y = +0.500"** on all three SKUs, so one leg runs 6.25" across the
ridge and the other 5.25". Measured from the outer surface, Steep 90 is 43.8°/48.8° (interior
**87.3°**, fitting 11.5:12 and 13.7:12), Standard 120 is 27.1°/31.3° (**121.6°**), Low 160 is
17.7°/20.8° (**141.5°**). The Steep 90's band is the guide's "11:12 or higher" almost exactly.
Anything that assumes a centred fold - halving the bounding width, or splitting the mesh at y=0 -
reads these pieces wrong; `FindFoldY` measures it in both the bootstrapper and the diagnostic.

**The catalogue does not reach every pitch, and a mismatched cap perches.** The sharpest cap opens to
87.3° and the Sandbox's 20.6:12 and 18.48:12 make a ridge interior of 63.2°. The roof's peak is the
sharper of the two, so it pokes up into the piece and the cap rests on its fold with both legs
standing proud of the shakes - about 1.32" at the tips. That is what the geometry does; no seat can
close it. Closing it needs the
fold itself bent to the roof's measured angle, and `ArcBendFlexRenderer` cannot do that - it bends
an arc along a flat shake's length and rewrites only the visual mesh, never the collider.

**A cap's collider is one convex hull per leg.** One hull over the whole V is a filled wedge: the
piece stops behaving like the shape it looks like, and a loose cap balances on that false flat
bottom instead of settling astride a ridge. Convex cannot simply be turned off - these bodies are
live while the tile is loose or held, AutoHand needs them live to grab at all, and Unity silently
ignores a concave MeshCollider on a live body, which reads in play as a tile falling through the
deck. Two hulls, one per leg on a child each with nothing on the root, describe the same surfaces
with no hollow filled in and are each still convex. `TileView`, `TileBundle` and the bootstrapper's
validation read colliders from the children for this reason.

**Piece size.** The ridge course reads a cap's `NominalWidth` as its run *along* the ridge and its
`NominalLength` as its cross-ridge depth — `RoofSession.Snap` halves the length to hang the cap the
same distance down each slope, and `CoursePlan.CountCoursesThatAddCover` uses that half to find the
band the cap roofs.

| | Along the ridge | Across the ridge | Height |
|---|---|---|---|
| Guide §1.1 | 14" ("Length") | 5½" ("Width"), read as per leg → ~11" | 6" |
| `RidgeCapTiles/90/90.fbx` | 14.00" | 11.50" | 6.93" |
| ... measured fold | — | 43.8°/48.8° legs, 87.3° interior | fits 11.5:12 and 13.7:12 |
| `RidgeCapTiles/120/120.fbx` | 14.00" | 11.50" | 4.13" |
| `RidgeCapTiles/160/160.fbx` | 14.00" | 11.50" | 2.93" |
| All three definitions, as authored | 14" | 11.5" | — (no rule reads it) |

Model figures are measured from the FBX vertex data; the files are in centimetres. The measurement
has been taken twice, independently, and agrees to the hundredth: the three caps read 35.56 cm x
29.21 cm, and the calibration tiles read exactly their names — `7_inch_Tile.fbx` 17.79 cm = 7.00" and
`12inch_Tile 1.fbx` 30.49 cm = 12.00" on the same axis. The caps also lay their extents out on
*exactly* the axes the field tiles use — X across the piece, Z along it, Y through the thickness — so
`GameplayPrefabBootstrapper` scales and orients them with no cap-specific handling, and the authored
root axes stay the `X=width, Y=length, Z=thickness` of CONVENTIONS §5.

**The 11.5" is a projection, not a slope depth.** A cap's bounding width across the ridge is what a
folded piece *projects*, and its legs are longer than that: 9.0" of leg against a 5.75" projection on
the Steep 90. `RoofSession.Snap` hangs a cap `NominalLength/2` down each face and
`CoursePlan.CountCoursesThatAddCover` measures the band it roofs from the same number, so wherever a
cap's legs really do lie on the shakes, its coverage of the top course is under-stated. It does not
bite while a mismatched cap perches on its apex; it would the moment the fold is closed.

**The definitions are now authored from the models: 14" x 11.5".** The guide and the models agree
exactly on the 14" run, so the 12" this was previously authored at was simply wrong on the axis the
ridge course actually reads. **Still unresolved, and deliberately so:** whether the guide's 5½" is
per leg or the whole across-ridge span. Per leg (2 x 5½ = 11") it reconciles with the models, and
that is the reading taken — the "whole span" reading would require all three models to be wrong
about the same axis. If it *is* the whole span, the cap reaches only 2¾" down each slope and the top
field course's fasteners — which `FastenerExposureLine` pins to the cap's lower edge — stop being
coverable at any exposure the rake offers. Confirm against a real piece; the cheap standing check is
whether the top course's fasteners stay covered at 8", 9" and 10" on the Sandbox's short face.

**Fasteners, and the shakes underneath.** Guide §4.3 step 5: two fasteners at the formed locators,
penetrating at least 3/4" into the deck or completely through it — `_recommendedFastenerCount: 2` on
the cap. Step 1: the shakes below are trimmed evenly on *both* slopes, a minimum of 3/16" clear of
the ridge, which is `PlacementSettings.ExpansionGapInches` (0.1875) and the line `MaximumHead` reads.
Step 3 is a note to the installer rather than a rule: check the packing list and load the correct
angle to each hip and ridge.

**One cap per ridge position.** Guide §4.3 step 4 installs one Ridge Cap where a hip would take two
Hip Caps. Nothing in the framework models a hip yet, so this is recorded rather than implemented.

**Posed astride the ridge, on the bisector.** `RoofSession.Snap` gives a cap a footprint on the ridge
face only, from `FaceBounds.Max.Y - halfCapDepth` up to `Max.Y`, and that is right: the domain judges
a cap as a course on the ridge face and no rule cares which way it is tilted in world space. World
space is where the inverted V lives. `FaceSpaceMapper.FaceRotation` puts a tile's local +Z on its
face normal, which aims a cap's peak straight out of one slope, so caps are posed instead by
`FaceSpaceMapper.GetRidgeCapWorldPose`, which aims local +Z along the **bisector of the two slopes'
outward normals** and lifts the piece along it. The run needs no turning - the ridge *is* the face's
own +X - so only the fold is re-aimed. `RoofRuntime.TryGetOppositeSlopeNormal` supplies the far
slope, because one face cannot describe an angle that belongs to two; it picks the face whose normal
leans furthest from this one, which is the slope across the ridge rather than a neighbour sharing a
hip. The side view in `RidgeCapInstallation.png` is the intent drawn.

**The guidance ghost takes the same call, and must.** The ghost is a flat outline with no fold of its
own, so a cap posed wrongly never *looks* wrong on it - which is exactly how a quarter-turn error
survived a trainee reporting "the ghost is showing correctly". A ghost that cannot reveal an error is
not evidence that there is none.

**A cap's prefab is built from its authored aspect, not from its size order.**
`GameplayPrefabBootstrapper.FindTileRotation` chooses a model's orientation by trying every
axis-aligned rotation and keeping the one whose bounds best match the SKU's own `NominalWidth` and
`NominalLength`. It used to score against a fixed size order instead - largest side onto Y, middle
onto X, smallest onto Z - which is true of every field shake and wrong for a cap, whose longest
dimension is the 14" run that belongs on X. That put the run on Y and left the 11.5" span on X, and
the uniform correction, which divides by `size.x`, then stretched the whole cap by 14/11.5 = 1.2174.
Caps arrived a quarter-turn out and 22% oversized.

**Closing ridge cap cut and proportional fastener placement.** The cap closing a ridge run is cut to the remaining run width:
- **Single-axis width cut:** The cut scales the mesh and child leg colliders exclusively along root-local X (along the ridge). Local Y and Z are completely untouched, keeping the inverted-V profile, ridge alignment, and roof seating intact without any shearing or tilt. Length trimming (`TrimHead`) is prohibited for ridge caps.
- **Proportional fastener repositioning:** Fasteners authored on the full 14" tile at $x \approx \pm 5.8"$ are repositioned along local X by the ratio $B / A$ (retained width $B$ divided by uncut width $A$). Local Y and Z remain unchanged, keeping the markers precisely on the leg surfaces at the correct slope depth.
- **Keyway clearance:** Ridge caps do not form vertical keyways with neighboring shingles. `FastenerTool.Describe` safeguards keyway clearance at $\ge 1.25"$ for `TileRole.RidgeCap` so that narrow cuts do not falsely trigger `FastenerPositionRule` violations.

## Course planning: Set Exposure calculation (guide Appendix E)

Not a validation rule, but domain maths the framework needs, and a good example of pure-C# logic:

```
courses     = ceil(slopeDistance / maxExposure)
setExposure = slopeDistance / courses
```

Guide's worked example: allowable 10" vs a **set** exposure of 9.738" so that the run finishes with a full shake. This means the *actual* target exposure for a face is usually **not** 10" — it is computed per face. `ExposureRule` therefore validates against the face's computed set exposure (with a tolerance), while the project-specific **8"–10"** band remains the outer training envelope. The future 8"/9"/10" picker selects the planning maximum; the solver may derive a slightly smaller set exposure to finish the run cleanly.
