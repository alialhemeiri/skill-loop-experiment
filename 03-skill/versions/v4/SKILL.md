<!-- v2: Resolve duplicate or conflicting values by honoring explicit amendments and otherwise requiring an unambiguous operative term. -->
# UAE Tenancy Contract Field Extraction

Extract the tenancy terms into the requested 12-field JSON object. Read the whole document before
answering, but prefer the agreement's key terms and clauses that explicitly identify a role or
field. Later administrative clauses often contain unrelated names, dates, amounts, and counts.

## Output rules

- Output only one valid JSON object, with no markdown or commentary.
- Include all 12 requested keys exactly once and do not add keys.
- Use JSON strings for names, unit, community, and ISO dates.
- Use unquoted JSON integers for rent, deposit, payment count, and notice days.
- Use an unquoted JSON number for the early-termination penalty in months; decimals such as `1.5`
  are allowed.
- Use only `"furnished"`, `"semi-furnished"`, `"unfurnished"`, or `null` for furnished status.
- Treat a value as stated when it appears directly or is defined by an explicit deterministic
  relationship whose required inputs are stated in the agreement. Perform only that calculation;
  if the relationship or any input is missing or ambiguous, return JSON `null`.
- Otherwise, if the document does not state a field, return JSON `null`. Do not guess or copy a
  nearby distractor into the field.
- When multiple values compete for one field, use a later value only when an amendment, addendum,
  or correction explicitly supersedes the original term. Otherwise prefer the unambiguous value
  in the operative key terms; if equally authoritative values conflict, return `null`.

## Locate the tenancy terms

1. Find the parties explicitly identified as Landlord and Tenant. Labels such as Owner or Lessor
   may describe the landlord, while Occupant or Lessee may describe the tenant, but use the named
   parties tied to the agreement rather than an agent, property manager, guest, or utility provider.
2. Return the person's or entity's name without an honorific and without role text such as
   `(the Landlord)`. Preserve the actual spelling; capitalization need not be copied mechanically.
3. Take `unit_number` from the leased premises description or key-terms section. Preserve meaningful
   letters, hyphens, and leading zeroes. Do not substitute a parking bay, account number, or Ejari
   reference.
4. Take `community` from the named neighborhood or community containing the premises. Distinguish it
   from the building or tower name and from the city or Emirate. If no community is identified, use
   `null` rather than promoting another address component.

## Normalize dates

- Identify the dates explicitly labeled as the contract or tenancy start and end dates. Do not use
  signature, cheque, registration, handover, or notice dates.
- Convert all stated formats to `YYYY-MM-DD`: for example, `26/08/2026` becomes `2026-08-26`, a
  month-name date is converted by its month, and an ISO date stays ISO.
- Treat slash dates in these UAE agreements as day/month/year unless the text clearly says otherwise.
- Zero-pad months and days. Check that the chosen end date follows the chosen start date.
- If no end date is printed but the agreement explicitly states both the commencement date and a
  tenancy duration, derive the inclusive end date by advancing the commencement date by the stated
  calendar duration and subtracting one day. For example, a twelve-month term commencing on a given
  date ends one day before the same date in the following year.
- Do not derive an end date when the duration or commencement date is absent, conditional, or
  ambiguous.

## Parse money and payment count

- For `annual_rent_aed`, use the amount explicitly labeled annual rent. For
  `security_deposit_aed`, use only the tenancy security deposit.
- If the deposit is explicitly defined as a percentage or other arithmetic formula of the stated
  annual rent, calculate that formula and return the resulting whole-dirham amount. Do not apply a
  customary deposit rate that the agreement itself does not state.
- AED markers may appear before or after the number as `AED`, `Dhs.`, or similar. Remove currency
  labels, commas, spaces, and a trailing `/-`, then return the whole-dirham integer.
- When an amount is written in words and digits, use the digit amount after confirming the two forms
  agree. Do not include punctuation or currency text in the JSON number.
- Do not confuse rent or deposit with an agent commission, DEWA or chiller charge or guarantee,
  Ejari or typing fee, maintenance threshold, repair cost, access-card charge, or arbitration cost.
- Determine `number_of_payments` from the rent payment plan, cheque count, or instalment frequency:
  `single` or `one` means 1, semi-annual or twice-yearly means 2, quarterly means 4, and monthly
  means 12. An explicit phrase such as `four (4) post-dated cheques` means 4.
- Count rent payments only. Do not count the deposit, fees, utilities, or the number of clauses.

## Remaining fields

- `notice_period_days`: use the explicit contractual notice period associated with renewal,
  non-renewal, or termination. Return the stated day count. Convert weeks to seven days each; if the
  document gives only months, use 30 days per month. Do not use a repair-response or access notice.
- `early_termination_penalty_months`: use only a penalty explicitly expressed as a number of months
  of rent. Keep a stated fraction or decimal. Do not confuse it with the notice period, tenancy
  duration, payment schedule, or an AED fee. If no such penalty is stated, use `null`.
- `furnished_status`: normalize clear descriptions to `"furnished"`, `"semi-furnished"`, or
  `"unfurnished"`. A furniture inventory alone is not enough to infer a status not stated by the
  agreement.

## Final check

Before responding, verify that every value was stated directly or follows an explicit deterministic
relationship in this agreement, dates are ISO strings, money and counts are JSON numbers rather than
quoted text, absent values are `null`, and distractor clauses did not replace the core tenancy terms.
Then emit the JSON object only.