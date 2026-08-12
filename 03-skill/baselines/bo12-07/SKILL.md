# UAE Residential Tenancy Contract Extraction

Extract the operative tenancy terms into the exact 12-key JSON object required by the harness. Read the whole document before selecting values. Use the document alone: never import UAE custom, statutory defaults, or outside knowledge.

## Evidence and conflict method

1. Identify the contracting parties, leased premises, tenancy term, rent terms, and relevant special conditions.
2. For each field, keep an internal candidate plus its exact label or clause and context. Do not emit this evidence or reasoning.
3. Read tables by headers, row labels, and alignment. Join wrapped cells, but never shift a neighboring value into a blank cell. In option lists, use only a clearly selected item such as `[x]`, `☒`, or explicit `Yes`.
4. Resolve a genuine conflict using this priority:
   - an amendment, addendum, or special condition that expressly changes or supersedes that field;
   - a completed key-terms, particulars, or schedule entry explicitly labeled for that field;
   - a definition, premises description, or operative clause clearly tied to this tenancy;
   - for a party name only, a role-labeled signature block.
5. An override changes only the fields it expressly changes. Position alone gives no priority. Ignore historical, proposed, example, or future-renewal values unless expressly made operative for this contract.
6. Repeated matching values corroborate each other. If equally authoritative evidence conflicts and no controlling words resolve it, return `null`; do not average, repair, or choose the plausible-looking value.
7. Administrative clauses are not tenancy terms merely because they contain a nearby name, date, amount, or count.

## Null, zero, and inference

- Return `null` for an absent, blank, unchecked, redacted, illegible, bare `N/A`, placeholder, "to be agreed," formula-only, or genuinely ambiguous field.
- Return numeric `0`, not `null`, when the agreement explicitly says the security deposit, qualifying notice, or early-termination penalty is zero, waived, or not required.
- "Early termination is prohibited" does not state a zero penalty. Return `null` unless a penalty is separately stated.
- Do not derive one requested value from another. The only permitted calculations are the date/amount normalization and notice/payment conversions stated below.

## Parties

- Use the party expressly defined or labeled Landlord, Owner, or Lessor for `landlord_name`; use the party defined or labeled Tenant or Lessee for `tenant_name`.
- Use Occupant, Party A/B, or a similar term only when the contract explicitly defines it as the relevant contracting role.
- Exclude brokers, agents, property managers, representatives, entity signatories, witnesses, non-tenant occupants, guarantors, and contacts.
- If an entity is the party, return its legal name, not its human signatory. Preserve entity suffixes such as LLC, PJSC, or FZE.
- Remove honorifics/titles such as Mr., Mrs., Ms., Miss, Dr., H.E., or Sheikh and role wrappers such as "(the Landlord)." Preserve the remaining spelling, initials, punctuation, and meaningful suffixes.
- If one labeled entry names co-parties, preserve all names and its stated separator after removing titles and role text.

## Premises

- Take `unit_number` only from the leased-premises description or a labeled Unit, Apartment, Flat, or Villa number field.
- Return only the identifier as a string. Preserve meaningful letters, internal spaces, slashes, hyphens, and leading zeroes.
- Do not use a building/tower, plot, floor, parking bay, bedroom count, title deed, Makani, utility account, cheque, or Ejari/reference number.
- Take `community` from an address field labeled Community, Neighborhood, District, Development, or Area, or from a clearly named neighborhood/development in the premises address.
- Do not substitute the building/tower, street, floor area, city, Emirate, country, or management company. If no community is identified, return `null`.

## Contract dates

- Populate `contract_start_date` from the explicitly identified tenancy/contract start or commencement and `contract_end_date` from its expiry/end. In "from X to Y," X is the start and Y the end.
- Ignore execution/signature, issue, registration/Ejari, handover, move-in, cheque, installment, inspection, notice, amendment-signing, birth, passport-expiry, and administrative dates.
- Convert valid dates to `YYYY-MM-DD`. Treat numeric UAE dates as day/month/year unless they begin with a four-digit year or the text explicitly establishes another order. Convert month names and remove ordinal suffixes.
- Expand a two-digit year only when the paired date or context makes the century unambiguous; otherwise return `null`. Zero-pad month and day.
- An impossible source date is `null`; do not repair it. Confirm the end follows the start. If rechecking labels and date order does not resolve a contradiction, return `null` for the affected date rather than swapping or altering it.
- Do not calculate a missing endpoint from "one year," "12 months," or another duration.

## Rent and security deposit

- For `annual_rent_aed`, use an amount explicitly identified as annual/yearly/per-annum rent, or a single Rent/Total Rent amount explicitly stated for the full annual tenancy.
- Do not annualize a monthly rate, divide a term total, sum installments, or treat one installment as annual rent.
- For `security_deposit_aed`, use only the tenancy security deposit amount. If only a percentage, number of months, or formula is stated, return `null`; do not calculate it from rent.
- Exclude commissions and booking/holding, utility, chiller, furniture, access-card, or key deposits unless expressly identified as the tenancy security deposit.
- Recognize AED, Dhs/Dirhams, grouping commas/spaces, and trailing `/-`. Convert an unambiguous amount written only in words. Treat `.00` as whole dirhams; never round a non-whole amount to fit the integer type.
- If digits and words both state an amount, verify they agree. If not, follow an explicit "words/digits prevail" rule; otherwise return `null`.
- Ignore commission, utilities, Ejari/typing fees, maintenance thresholds, repairs, access charges, guarantees, arbitration costs, and other non-rent sums.

## Number of payments

- For `number_of_payments`, use an explicit count of rent installments, payments, or cheques. Count a clearly complete rent schedule or unambiguous numbered range.
- Normalize one/single/annually/paid in full to 1; twice-yearly/semi-annual to 2; quarterly to 4; monthly to 12, only when the phrase describes this contract's rent payments.
- Exclude deposit, fee, and security cheques; cheque numbers; installment ordinals; schedule headings; and clause counts.
- If "as per schedule" refers to a missing or incomplete schedule, return `null`.

## Notice period

- For `notice_period_days`, prefer a completed field explicitly labeled Notice Period. Otherwise use the agreement-wide renewal/non-renewal notice; if none exists, use notice expressly required for tenant termination or early surrender.
- Do not replace a labeled/general period with a different early-termination notice. If multiple qualifying periods remain and this priority does not resolve them, return `null`.
- Return the stated day count. Convert weeks as 7 days each and months as 30 days each. Keep a stated business-day count as that numeric count.
- Ignore notice for access/inspection, repairs, maintenance, payment default, breach/cure, eviction, rent increase, legal process, arbitration, or administrative response.
- "Reasonable notice" or similar language without a count yields `null`.

## Early-termination penalty

- For `early_termination_penalty_months`, use only compensation expressly triggered by the tenant's early termination, cancellation, break, or surrender and expressly measured as months of rent.
- Convert number words, fractions, and decimals: "one and one-half months' rent" is `1.5`.
- Keep notice and penalty separate. Do not add a forfeited deposit or another charge to a stated months-of-rent penalty.
- An AED-only fee, deposit forfeiture alone, remaining rent, or a percentage/formula is not a months value. Return `null`; never divide an AED amount by rent.
- If different penalties apply under unresolved conditions, return `null`. An explicit "no early-termination penalty" is `0`.

## Furnishing

- For `furnished_status`, normalize an explicit status: furnished/fully furnished to `"furnished"`; semi-, partly, or partially furnished to `"semi-furnished"`; unfurnished/not furnished to `"unfurnished"`.
- Respect scope: "unfurnished except fitted appliances" is `"unfurnished"`.
- Do not infer status from an inventory, appliances, curtains, wardrobes, fixtures, photographs, or an "as-is" clause alone.
- If options are present but none or more than one is selected, return `null`.

## Output validation

- Emit one bare valid JSON object only: no prose, markdown fence, comments, or trailing comma.
- Include every harness key exactly once, in harness order, and no other keys.
- Use strings only for names, unit, community, dates, and furnished status; use JSON numbers for money, counts, days, and penalty months; use bare `null` for missing values.
- Ensure dates are ISO strings, annual rent/deposit/payment count/notice days are integers, and furnished status is exactly one allowed enum value.
- Before emitting, verify every non-null value against its field-specific evidence and rescan for role, date, amount, count, and notice distractors.