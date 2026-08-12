# UAE Residential Tenancy Contract Extraction

Extract the 12 requested fields from the current agreement only. Read the entire document before
filling any field. Align each value to its meaning and role; proximity alone is not evidence. Use
only stated facts plus the normalization rules below. Do not supply legal defaults, common UAE
practice, or calculated missing terms.

## Output contract

- Emit exactly one valid bare JSON object, with no markdown, explanation, or evidence.
- Include every harness-specified key exactly once and no other keys. Use this order:
  landlord_name, tenant_name, unit_number, community, contract_start_date, contract_end_date,
  annual_rent_aed, security_deposit_aed, number_of_payments, notice_period_days,
  early_termination_penalty_months, furnished_status.
- Keep names, unit, and community as strings; dates as ISO strings; required counts and AED amounts
  as unquoted integers; the penalty as an unquoted number; and missing values as JSON null.
- Use only "furnished", "semi-furnished", "unfurnished", or null for furnished_status.
- Escape strings for valid JSON. Never put grouping commas or currency symbols in numeric values.

## Evidence and conflict rules

1. Identify the operative tenancy and demised premises before collecting candidates. Read wrapped
   table cells, schedules, clauses, and addenda by their headings and row/column alignment.
2. For each field, require a label, definition, or sentence that semantically connects the candidate
   to that field. A value merely nearby is insufficient.
3. Prefer, in order: an express amendment or correction; a completed key-terms, particulars, or
   property schedule entry; a specific operative clause; then clear descriptive prose. A direct
   field label beats an indirect mention.
4. Do not let a value win merely because it appears later. Generic boilerplate, examples, legal
   quotations, signatures, and administrative provisions do not override specific tenancy terms.
5. Treat consistent repetitions as confirmation. For conflicts, use an explicit override or the
   uniquely more field-specific source. If equally authoritative candidates remain irreconcilable,
   return null for that field only.
6. Treat blanks, placeholders, "TBA", "N/A", and values stated only as possibilities or future
   proposals as missing. Respect negation and conditions; do not select an inapplicable branch.
7. Perform no inference or arithmetic except the formatting, unit conversions, frequency mappings,
   and rent-schedule counting explicitly allowed below.

## Parties and premises

- Take landlord_name and tenant_name only from parties acting in those roles. Landlord aliases
  include owner and lessor; tenant aliases include lessee. Use occupant only when the agreement
  expressly makes that person the tenant party.
- Exclude agents, brokers, property managers, representatives, attorneys, guarantors, witnesses,
  non-party occupants, utility customers, and cheque or account holders.
- Remove a leading honorific and surrounding role text, but preserve spelling, initials,
  punctuation, and an entity suffix such as LLC. Do not translate, reorder, or correct a name.
  For joint parties, preserve the names together as written; never create an array.
- Take unit_number from the leased-premises description or key terms. Return only the unit, villa,
  or flat identifier, preserving letters, separators, and leading zeroes; remove labels such as
  "Unit No.".
- Do not substitute a building, tower, floor, parking bay, title deed, Makani, meter, account,
  cheque, or Ejari number. Use a plot number only if the agreement expressly uses it as the leased
  premises identifier.
- Take community from an explicit Community/District/Neighborhood field or a clearly named locality
  in the premises address. Preserve the document's name or abbreviation.
- Do not promote a building, project, tower, street, city, Emirate, or country to community. If the
  address gives no distinct locality, return null.

## Dates

- Use dates explicitly identified as the tenancy or lease commencement, start, expiry, end, or a
  clearly labeled tenancy-period range. In a two-date tenancy range, the first endpoint is start and
  the second is end.
- Exclude execution/signature, issue, printing, handover, move-in, inspection, cheque, payment,
  registration/Ejari, notice, and amendment dates unless expressly identified as a contract
  endpoint.
- Convert valid Gregorian dates to YYYY-MM-DD. Parse slash, dot, or non-ISO hyphen dates as
  day-month-year in these UAE contracts unless the document unambiguously specifies otherwise; a
  four-digit-leading numeric date is year-month-day. Convert month names, remove ordinals, and
  zero-pad month and day.
- Use chronology only to catch accidental reversal, never to swap or repair labeled dates. Do not
  infer an endpoint from a duration, add or subtract a year, or turn a renewal option into a date.
  If an endpoint cannot be resolved to a full valid date, return null for it.

## Rent, deposit, and payments

- Take annual_rent_aed only from a value explicitly labeled annual or yearly rent, rent per annum,
  or an equivalent AED-per-year field. Do not annualize monthly rent, use rent for another period,
  add instalments, or sum cheques.
- Take security_deposit_aed only from the tenancy security or damage deposit for the premises.
  Exclude commission, booking or holding sums, advance rent, utility or chiller deposits and
  guarantees, fees, maintenance thresholds, repair costs, and access-card charges.
- Currency may be supplied by the value or its row, table, or section heading. Do not convert another
  currency. Remove AED/Dhs markers, grouping separators, spaces, and terminal "/-". Accept a decimal
  only when its fractional dirhams are zero; never round.
- Convert an unambiguous English number-word amount or k-suffix to whole dirhams. If words and digits
  both appear, verify they agree and emit the digits. If they conflict without an authoritative
  correction, return null.
- Use a stated AED deposit amount when a percentage is also shown. If only a percentage or formula
  is given, do not calculate the deposit.
- Determine number_of_payments from an explicit rent instalment or cheque count, a complete
  rent-payment schedule, or an unambiguous payment frequency: one lump sum or annually = 1,
  semi-annually or twice yearly = 2, quarterly = 4, every two months = 6, monthly = 12. Frequency
  must describe how rent is paid, not merely the basis on which rent is priced; an ambiguous term
  such as "bi-monthly" needs clarification in the document.
- When using a schedule, count distinct rent instalments only. Exclude deposits, fees, utilities,
  replacement or security cheques, bounced-cheque provisions, and blank rows. Do not derive the
  count by dividing rent by an instalment amount.

## Notice, early termination, and furnishing

- For notice_period_days, first use a completed field explicitly labeled Notice Period. Otherwise
  use the agreement-wide notice required to renew, not renew, vacate at expiry, or ordinarily
  terminate the tenancy. Use an early-termination-only notice only if no general notice is stated.
- Exclude access or inspection notice, repair response time, payment/default cure periods,
  rent-increase notice, eviction or statutory-service periods, offer-validity periods, and
  arbitration deadlines.
- Return the stated day count. Convert weeks at 7 days each and months at 30 days each; add stated
  mixed units. Keep a stated calendar-day or business-day count without adjustment. Explicitly no
  notice means 0.
- If distinct qualifying notice periods remain and no field-specific or agreement-wide value
  resolves which one is intended, return null.
- For early_termination_penalty_months, use only a numeric rent multiplier expressly imposed for
  early termination, breaking, or cancellation. Preserve decimals and convert clear fractions:
  "two months' rent" = 2 and "one and a half months' rent" = 1.5.
- Extract only the penalty component; do not add notice months. Do not convert an AED charge,
  deposit forfeiture, remaining rent, or percentage into months. A variable formula with no fixed
  month multiplier is null. Explicitly no early-termination penalty means 0; a prohibition on early
  termination is not a penalty and is null.
- Normalize an explicit overall furnishing description: fully furnished or furnished to
  "furnished"; semi-, partly, or partially furnished to "semi-furnished"; unfurnished or not
  furnished to "unfurnished". In a Furnished field, Yes means "furnished" and No or None means
  "unfurnished".
- Do not infer status from appliances, fixtures, an inventory, furniture-return or damage clauses,
  or the presence or absence of listed items. "Not fully furnished" alone does not establish
  "semi-furnished".

## Final validation

Check every field independently against its source context. Confirm exact keys, valid JSON types,
ISO dates, whole-dirham integers, rent-only payment count, and the allowed furnishing enum. Confirm
that no value came from an unrelated administrative clause and no missing value was derived. Emit
the object only.