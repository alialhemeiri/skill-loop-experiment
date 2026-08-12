# UAE Residential Tenancy Contract Field Extraction

Extract the operative terms of the residential tenancy in the current document into the harness-provided 12-field JSON object. Work silently: read the entire document, select evidence field by field, normalize it, and validate the result.

## Output contract

- Emit exactly one valid JSON object and nothing else: no prose, markdown, code fence, citations, or extra keys.
- Include every harness key exactly once. Use the harness-required JSON types; use JSON null for an unstated or unresolved field.
- Never use an empty string, "N/A", an approximate value, or quoted text where the harness requires a number.
- Preserve source spelling in names and identifiers except for the cleaning rules below. Escape strings as valid JSON.

## Evidence-selection workflow

1. Read the whole document before choosing any value. Treat prose, numbered clauses, and schedule/table rows as equally usable; keep each table label associated with its value.
2. For each field, collect only candidates explicitly linked to that field, role, or leased premises. Nearby text is not evidence by itself.
3. Discard blank fields, unchecked options, headings without values, examples, templates, proposed future terms, prior contracts, and values for another person, property, or service.
4. Apply this precedence unless the agreement states its own precedence rule:
   - An operative amendment, addendum, correction, or replacement that expressly changes the same field.
   - A populated key-terms, particulars, lease-schedule, or premises row, including a clearly selected checkbox.
   - A specific operative clause that states the agreement's value.
   - Unambiguous contract prose corroborated by context.
5. Position alone never creates precedence. A later administrative clause is not an amendment; require words such as "amended", "replaced", "revised", "notwithstanding", or an equally clear override.
6. Normalize candidates before comparing them. Identical normalized values corroborate. If different values remain, use a clear override or the single higher-precedence candidate. If equally authoritative candidates still conflict, return null for that field.
7. Do not combine fragments from different alternatives to manufacture a value. Do not infer from common UAE practice, outside knowledge, or what a normal lease would contain.

## Parties and premises

- landlord_name: use the party explicitly designated Landlord, Owner, or Lessor. tenant_name: use the party explicitly designated Tenant or Lessee. Use "Occupant" only if the agreement expressly defines that occupant as the tenant, not for a separately named approved occupant.
- A company named as a party remains the party even when a person signs or acts for it. Exclude brokers, agents, property managers, authorized signatories, witnesses, guarantors, guests, and utility contacts unless that person or entity is itself explicitly the relevant contracting party.
- Remove leading honorifics from each person, such as Mr, Mrs, Ms, Miss, Dr, Sheikh, or H.E.; also remove role wrappers, signatures labels, IDs, licence numbers, addresses, phone numbers, and parenthetical phrases such as "(the Landlord)". Preserve initials and legal entity suffixes such as LLC, PJSC, FZE, and FZ-LLC.
- If several people are jointly named under one role, retain all of their names in document order after cleaning; do not select only one.
- unit_number: take the leased unit identifier from the premises or property description. Return the identifier, not its field label or a generic property-type prefix: "Apartment No. 0012" becomes "0012" and "Villa 14A" becomes "14A". Preserve meaningful letters, separators, and leading zeroes.
- Never use a parking/storage bay, plot, title-deed number, Makani number, utility account, cheque number, or Ejari/contract reference as the unit unless it is explicitly the leased unit identifier.
- community: use an explicitly named community, neighborhood, district, or master development containing the premises. Prefer a Community/Area row; otherwise use the unambiguous address component.
- Do not substitute a building, tower, residence name, street, city, Emirate, or country. A genuine community name may contain "Dubai" (for example, Dubai Marina); do not strip it. If only a building and city are given, return null.

## Contract dates

- contract_start_date comes only from the tenancy/lease start, commencement, or "from" date. contract_end_date comes only from its expiry, expiration, end, or "to/until" date.
- Exclude execution, signature, preparation, issue, printing, registration, cheque, payment, notice, inspection, handover, and move-in dates unless the agreement explicitly equates one with tenancy commencement or expiry.
- Use start and end candidates for the same operative term. Ignore a proposed renewal period unless the document itself makes that renewal the operative term.
- Convert a valid stated date to YYYY-MM-DD. Interpret numeric slash or hyphen dates as day/month/year in these UAE contracts unless the text explicitly establishes another order. Convert month names and zero-pad day and month.
- Expand a two-digit year only when the century is unambiguous from the document; otherwise return null for that date.
- Verify that the end date is later than the start date. If not, recheck source labels and date order; never swap labels or invent a date merely to make the pair work.
- Extract either date independently if only one is stated. Never derive the other from a duration or by adding/subtracting a day or year.

## Rent, deposit, and payments

- annual_rent_aed: use rent explicitly stated per year, per annum, annually, or as the rent for the full one-year tenancy. A bare Rent value in the operative key terms qualifies when context clearly makes it the total rent for that one-year term.
- Do not annualize monthly/quarterly rent, sum cheques, use a multi-year total, or treat a renewal offer as current annual rent.
- security_deposit_aed: use only the stated AED amount of the refundable tenancy/security deposit for the premises. If only a percentage or "equivalent to" formula is stated, return null; do not calculate it.
- Accept AED, Dhs, DHS, Dh, dirham(s), commas, spaces, and a trailing "/-". Treat a final .00 as whole dirhams and expand an unambiguous "k" as thousands. Return the whole-dirham integer without currency text or separators; never round a nonzero fractional-dirham amount.
- Convert an unambiguous amount written only in English number words. When digits and words both appear, confirm they agree. If they disagree, use an express correction; otherwise return null for that amount.
- Exclude agent commission, booking/holding deposit, utility or chiller deposit/charge, bank guarantee, security cheque, Ejari/typing fee, VAT, maintenance threshold, repair cost, service charge, access-card fee, and arbitration/legal cost.
- number_of_payments: use the rent instalment/cheque count, count clearly enumerated rent instalment rows, or normalize an unambiguous full-year frequency.
- Map annual/single/once/one cheque to 1; semi-annual/half-yearly/every six months to 2; every four months/three times yearly to 3; quarterly/every three months to 4; every two months to 6; monthly to 12.
- Treat "bi-monthly" as ambiguous unless a count or schedule resolves it. Count rent payments only, excluding deposits, fees, utility payments, security cheques, and digits within cheque numbers.

## Notice, early termination, and furnishing

- notice_period_days: prefer a populated general "Notice Period" key term. Otherwise use the notice the agreement requires for renewal, non-renewal, or termination, including early termination.
- Exclude access/inspection notice, maintenance response time, payment demand, breach-cure period, deemed-receipt delay, rent-review proposal, eviction procedure, statutory reminder that does not set this contract's notice, and administrative deadlines.
- Return an explicit day count unchanged. Convert weeks to 7 days each and months to 30 days each; do not compute a period from two calendar dates.
- If different notice periods govern different qualifying events or parties and no general field or clear override identifies the requested one, return null rather than choosing arbitrarily.
- early_termination_penalty_months: use only a numeric month-of-rent coefficient expressly imposed as the penalty, compensation, or charge for ending this tenancy early. Convert number words and fractions: "half a month" is 0.5 and "one and one-half months" is 1.5.
- Do not confuse the penalty with the notice period, normal rent, remaining-term rent, rent-free period, payment frequency, deposit forfeiture, an AED/percentage fee, or rent expressed in days/weeks. Do not convert days to months. Payment in lieu of notice is not a penalty unless the agreement expressly treats it as early-termination compensation.
- furnished_status: normalize an explicit status of furnished/fully furnished to "furnished"; semi-furnished/part-furnished/partly furnished to "semi-furnished"; and unfurnished/not furnished or Furnished: No to "unfurnished".
- For checkbox or slash-option text, use only a clearly selected option. A list of options, furniture inventory, appliances, fittings, or condition report alone does not establish furnished status.

## Final audit

For every non-null value, confirm an exact span in this agreement identifies the correct field, role, premises, and operative term. Allow only the normalizations explicitly authorized above. Recheck date validity, JSON escaping, enum spelling, and numeric types. Then emit the single JSON object only.