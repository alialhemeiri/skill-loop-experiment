# UAE Residential Tenancy Contract Field Extraction

Extract the 12 requested fields from this document only. Read the entire document before selecting
values. Treat every field as a separate evidence question: a plausible nearby value is not evidence
for the requested field.

## Required process

1. Identify the operative tenancy and any amendment, renewal, or addendum that explicitly changes it.
2. Locate completed contract particulars, key terms, schedules, party definitions, premises
   descriptions, rent/payment terms, and special conditions.
3. In a flattened table, associate a value only with an unambiguous row or column label. Do not shift
   values between neighboring rows; if the alignment permits multiple mappings, treat it as unresolved.
4. For each field, collect candidates with their exact label, sentence, and section. Reject candidates
   that belong to another role, date, amount, count, property, or administrative process.
5. Resolve repetitions before normalizing. An explicit amendment or correction overrides the original;
   a completed key-terms/schedule entry for this tenancy normally outranks generic boilerplate; a
   field-specific operative clause outranks an incidental mention. Later text does not win merely
   because it is later.
6. If equally authoritative candidates genuinely conflict and the document does not resolve them,
   return `null` for that field.
7. Normalize only after choosing the supported source value, then run the final audit.

Blank fields, dashes, unchecked alternatives, examples, instructions to complete a form, `N/A`,
`TBD`, and redacted placeholders do not state a value. Never use customary UAE practice, outside
knowledge, or another field to fill a gap. Do not derive a missing term by arithmetic except for the
specific unit conversions allowed below.

## Output contract

- Emit exactly one bare, valid JSON object: no markdown fence, explanation, confidence, or source text.
- Include each harness key exactly once and no additional keys:
  `landlord_name`, `tenant_name`, `unit_number`, `community`,
  `contract_start_date`, `contract_end_date`, `annual_rent_aed`,
  `security_deposit_aed`, `number_of_payments`, `notice_period_days`,
  `early_termination_penalty_months`, and `furnished_status`.
- Names, unit, community, and dates are JSON strings. Rent, deposit, payment count, and notice days
  are unquoted integers. The penalty is an unquoted number and may be decimal.
- Furnished status is exactly `"furnished"`, `"semi-furnished"`, `"unfurnished"`, or `null`.
- Use JSON `null`, never an empty string, `"null"`, zero, or an invented default, for an unstated
  or unresolved field. Escape quotation marks and backslashes inside strings.

## Parties

- Select a name only when the document explicitly assigns that person or entity the relevant role.
  Owner/Lessor and Lessee are aliases only when the contract maps them to Landlord and Tenant.
  First/Second Party labels require the same explicit mapping; never infer roles from order alone.
- A definition such as `A ("Landlord")` is strong evidence. A role-labeled printed signature name is
  a fallback when the party section is absent; an unlabeled signature is not.
- Exclude agents, brokers, property managers, authorized representatives, witnesses, guarantors,
  occupants who are not the tenant, emergency contacts, utility providers, and names in payment or
  notice details. Do not replace a named principal with someone signing on the principal's behalf.
- Return only the party name: remove an honorific and surrounding role wording, and exclude ID,
  passport, nationality, address, phone, and email text. Preserve capitalization, initials, spelling,
  punctuation, and entity suffixes such as LLC. If the document defines joint parties as one role,
  preserve the complete joint-party wording rather than choosing one person.

## Premises

- Take `unit_number` only from the demised/leased premises or a completed property field. Apartment,
  Flat, Villa, or Unit may introduce it. Return the identifier rather than the generic label; preserve
  meaningful letters, hyphens, slashes, and leading zeroes.
- Reject building numbers, floor numbers, plot numbers, title-deed or Makani numbers, parking bays,
  PO boxes, account numbers, cheque numbers, and Ejari/registration references.
- Take `community` from an explicit Community, Area, District, Neighbourhood, or clearly-locality
  Location field. An unlabeled address component is acceptable only when it unambiguously names the
  locality containing the premises.
- Do not promote a building/tower/residence name, street, city, Emirate, or country to community.
  Preserve the community wording as stated; do not expand an abbreviation from outside knowledge.
  If only those other address components appear, return `null`.

## Contract dates

- Use dates explicitly defining the tenancy period: Start, Commencement, From, End, Expiry, or
  `term from X to Y`. For a stated renewal, use the explicitly designated new/current renewal period,
  not the prior tenancy or an optional future period.
- Exclude agreement/execution/signature dates, issue dates, registration/Ejari dates, handover or
  move-in dates, cheque/payment dates, inspection dates, and dates by which notice must be sent.
- Treat a four-digit first component as year-month-day. Otherwise interpret numeric slash, dot, or
  hyphen dates as day-month-year unless the text explicitly establishes another order. Expand a
  two-digit year only when document context unambiguously fixes its century. Convert English month
  names and zero-pad to `YYYY-MM-DD`.
- Validate the Gregorian date. The selected end should follow the selected start; use a chronology
  failure to recheck the evidence, never to swap, repair, or invent a date. Do not calculate one date
  from the other date or from a stated duration.

## Rent, deposit, and payment count

- For `annual_rent_aed`, accept an amount explicitly identified as Annual Rent, Yearly Rent, Rent
  per annum, or rent explicitly stated for a one-year tenancy. Do not annualize a monthly amount,
  sum cheques, or assume an unlabeled total is annual solely from the contract dates.
- For `security_deposit_aed`, accept only a fixed AED amount explicitly tied to the tenancy security
  deposit/refundable deposit. A percentage without its AED amount is not enough; do not calculate it.
- Reject agent commission, booking/holding deposits, advance rent, utility/chiller/DEWA deposits or
  charges, VAT, Ejari/typing fees, maintenance thresholds, repair costs, access-card/key charges,
  bank guarantees, arbitration costs, and other fees.
- Accept `AED`, `Dhs`, `Dirhams`, equivalent clear currency wording, or a table-wide AED header.
  Remove currency markers, thousands separators, surrounding spaces, and a terminal `/-`. Convert
  an unambiguous words-only amount. If digits and words both occur, use the digits only when they
  agree. Remove `.00`; never round a non-whole-dirham amount to satisfy the integer type.
- Determine `number_of_payments` only from the rent payment plan. Prefer an explicit rent-instalment,
  cheque, or PDC/post-dated-cheque count. Otherwise map annual/yearly/single/one payment to 1,
  semi-annual/half-yearly/twice-yearly to 2, quarterly to 4, and monthly to 12, only when the phrase
  describes payment frequency.
- If no total is stated, count clearly itemized rent instalments only when the schedule is complete.
  Exclude the security-deposit cheque, fees, utilities, bounced/replacement cheques, cheque numbers,
  clause numbering, and dates.

## Notice, early termination, and furnishing

- For `notice_period_days`, prefer a completed field explicitly labeled Notice Period. Otherwise use
  the general notice to renew, not renew, or vacate at tenancy end; if absent, use the general
  early-termination notice.
- Exclude notice for access/inspection, repairs or maintenance, breach/default cure, rent increase,
  payment demand, cheque replacement, complaints, utilities, or legal proceedings. Do not use the
  number of days remaining until a dated deadline.
- Return a stated day count. Convert weeks to 7 days each and months to 30 days each; these are
  normalization rules, not permission to infer a missing period. If distinct qualifying notice
  periods apply to different choices and no single general/requested period is identified, use
  `null`.
- For `early_termination_penalty_months`, require an explicit consequence of ending the tenancy
  early and an explicit fixed number of months of rent, such as `two months' rent` or `1.5 months
  of rent`. Convert clear number words and fractions to a number.
- Do not convert an AED-only fee, days of rent, a notice period, remaining rent, tenancy duration,
  rent-free period, payment frequency, or deposit forfeiture into penalty months. If conditional
  clauses give different month penalties and the document does not establish which applies, use
  `null`.
- Normalize explicit `fully furnished` or `furnished: yes` to `"furnished"`; `semi`,
  `semi-furnished`, `partly furnished`, or `partially furnished` to `"semi-furnished"`; and
  `unfurnished`, `not furnished`, `furnished: no`, or an explicit furnishing status of `none`
  to `"unfurnished"`.
- In a list of alternatives, use only the clearly selected/marked option. Furniture inventories,
  appliance lists, fitted kitchens, curtains, or move-in condition reports alone do not establish
  furnished status.

## Final audit

Verify every value belongs to this tenancy. Recheck agent/landlord, occupant/tenant,
building/community, payment or signature/tenancy date, fee/deposit, cheque amount/annual rent,
all cheques/rent payments, access/tenancy notice, and notice/penalty months. Confirm ISO dates,
exact enums and JSON types, all 12 keys, and parseable bare JSON; then emit only the object.