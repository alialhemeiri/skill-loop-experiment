# Evidence Pack — nf-4b

- **Batch ID:** `nf-4b`
- **Skill:** `03-skill/versions/v0/SKILL.md` (`sha256: 57585893fe94b546ceb76f43f204828903e4e0ee285310f699f6b6e99f681174`)
- **Pooled score:** 216/240 (0.900000)
- **Per-rep scores:** rep1 107/120 (0.891667), rep2 109/120 (0.908333)
- **Counters:** unparseable=0; wrong_shape=0; missing=0; hallucinated_absent=0; missed_present=24; fence_stripped=0; turn_check_retries=0

## Per-field accuracy

| Field | Correct/total | Accuracy |
|---|---:|---:|
| `landlord_name` | 20/20 | 1.000000 |
| `tenant_name` | 20/20 | 1.000000 |
| `unit_number` | 20/20 | 1.000000 |
| `community` | 20/20 | 1.000000 |
| `contract_start_date` | 20/20 | 1.000000 |
| `contract_end_date` | 3/20 | 0.150000 |
| `annual_rent_aed` | 20/20 | 1.000000 |
| `security_deposit_aed` | 13/20 | 0.650000 |
| `number_of_payments` | 20/20 | 1.000000 |
| `notice_period_days` | 20/20 | 1.000000 |
| `early_termination_penalty_months` | 20/20 | 1.000000 |
| `furnished_status` | 20/20 | 1.000000 |

## Wrong instances

### `contract_end_date`

#### `doc-01`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
"2027-08-20"
```

#### `doc-01`, rep 2

Worker answer:

```json
null
```

Training gold:

```json
"2027-08-20"
```

#### `doc-02`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
"2027-09-13"
```

#### `doc-02`, rep 2

Worker answer:

```json
null
```

Training gold:

```json
"2027-09-13"
```

#### `doc-03`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
"2027-09-28"
```

#### `doc-03`, rep 2

Worker answer:

```json
null
```

Training gold:

```json
"2027-09-28"
```

#### `doc-04`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
"2027-10-16"
```

#### `doc-04`, rep 2

Worker answer:

```json
null
```

Training gold:

```json
"2027-10-16"
```

#### `doc-06`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
"2027-11-25"
```

#### `doc-07`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
"2027-12-07"
```

#### `doc-07`, rep 2

Worker answer:

```json
null
```

Training gold:

```json
"2027-12-07"
```

#### `doc-08`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
"2028-01-03"
```

#### `doc-08`, rep 2

Worker answer:

```json
null
```

Training gold:

```json
"2028-01-03"
```

#### `doc-09`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
"2028-01-17"
```

#### `doc-09`, rep 2

Worker answer:

```json
null
```

Training gold:

```json
"2028-01-17"
```

#### `doc-10`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
"2028-02-03"
```

#### `doc-10`, rep 2

Worker answer:

```json
null
```

Training gold:

```json
"2028-02-03"
```

### `security_deposit_aed`

#### `doc-02`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
8400
```

#### `doc-02`, rep 2

Worker answer:

```json
null
```

Training gold:

```json
8400
```

#### `doc-04`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
7200
```

#### `doc-04`, rep 2

Worker answer:

```json
null
```

Training gold:

```json
7200
```

#### `doc-06`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
3900
```

#### `doc-08`, rep 1

Worker answer:

```json
null
```

Training gold:

```json
6300
```

#### `doc-08`, rep 2

Worker answer:

```json
null
```

Training gold:

```json
6300
```

## Exemplar documents

### `doc-02`

Wrong fields exemplified: `contract_end_date`, `security_deposit_aed`

```text
RESIDENTIAL TENANCY AGREEMENT

1. PARTIES AND SELECTED ADMINISTRATIVE DETAILS
Tenant: Salma Benyahia

2. OPERATIVE PARTICULARS
Mr. Dario Kovac is the Landlord, with leasing agent Bilal Azzam authorised only to coordinate access and paperwork; the representative acquires no ownership interest. The demised premises are Unit F-1601; parking bay P-638 is a separate access reference and is not part of the unit identifier. The unit lies in Acacia Shade Building, within the wider community of Mushrif Iris Quarter; the building name does not replace the community.

3. TERM AND MONEY
The contractual term is a term of twelve months commencing 14/09/2026; the handover inspection dated 09/09/2026 is an administrative event, not the tenancy commencement. The yearly residential consideration is One hundred sixty-eight thousand dirhams in total; the agent commission of 2450 AED and chiller account guarantee of Eight hundred dirhams (AED 800) are separate sums owed only to their named service providers. The tenancy security deposit is fixed at five per cent of the yearly residential consideration; that percentage does not describe either external service-provider amount.

4. OTHER AGREED TERMS
Four post-dated cheques, each separately identified in the delivery record, constitute the complete set of rent instruments. A party declining renewal must give the other party 90 calendar days before expiry.

5. PURPOSE AND OCCUPATION
The home is let only for private residential occupation by the Occupant and members of the Occupant's household. It may not be used as a shop, office, holiday rental, shared lodging business, or address for an unrelated commercial licence. Guests remain the Occupant's responsibility while inside the premises or common areas.

6. HANDOVER AND CONDITION
At handover, both sides may complete a written condition record and attach dated photographs. Acceptance of keys confirms access but does not waive a hidden defect reported promptly after discovery. The Occupant shall keep the interior reasonably clean and return it in comparable condition, allowing for ordinary wear.

7. DEWA AND CHILLER SERVICES
Where DEWA and district cooling serve the premises, the Occupant handles activation, consumption, and final clearance directly with the service companies. Those accounts do not alter any residential sum recorded in the operative particulars.

8. PAYMENT ADMINISTRATION
Rent instruments shall be delivered to the Owner or a representative authorised in writing. Bank handling charges caused by a rejected instrument remain the Occupant's responsibility. Both sides should retain a receipt or bank record. Cash collection does not change a financial term unless both sides sign a written variation.

9. UTILITIES AND SERVICES
The Occupant is responsible for consumption-based household services connected to the premises. The Owner remains responsible for charges attaching solely to ownership of the building. Each side shall cooperate with account-opening papers, meter access, and final clearance without treating a service bill as part of the rent.

10. CARE OF THE PREMISES
Routine cleaning, replacement of consumable items, and repair of damage caused by misuse fall to the Occupant. Structural defects and failures caused by age fall to the Owner, subject to building access rules. A problem should be reported promptly with enough detail for a suitable technician to be arranged.

11. ALTERATIONS
Painting, drilling into stone, changing locks, installing exterior equipment, or altering service connections requires the Owner's written consent in advance. Any approved work must comply with building management rules and be carried out by a competent person. Consent to one alteration does not imply consent to another.

12. EJARI ADMINISTRATION
The parties shall provide ordinary identity and property papers needed for Ejari registration. A typing-centre receipt proves filing activity only and does not amend the dates, parties, premises, or financial bargain recorded here.

13. ACCESS AND PRIVACY
The Owner may request access at a reasonable hour for inspection, repair, or a building-management requirement. Except in a genuine emergency, the parties shall coordinate a suitable time in writing. The Owner shall not interfere unnecessarily with peaceful occupation, and the Occupant shall not unreasonably withhold access.

14. CONDUCT AND COMMON AREAS
The Occupant shall observe access, parking, waste, noise, pool, lift, and visitor rules issued for the building. Corridors and fire routes must remain clear. Any access card or key supplied for common facilities remains linked to the premises and may not be copied for an unrelated person.

15. RECORDS AND CHANGES
This agreement and its operative particulars record the entire residential arrangement. A change is effective only when written clearly and accepted by both sides. Informal messages may coordinate practical matters, but they do not replace a signed change to a financial or occupancy obligation.

16. MAINTENANCE ALLOCATION
Minor maintenance arising from day-to-day use is handled by the Occupant, while major building-system work remains with the Owner unless misuse caused the damage. A help desk may classify a call, but that classification does not decide a dispute.

17. COUNTERPARTS
The agreement may be signed in matching counterparts or by an accepted eletronic signature method. Each counterpart is treated as part of the same instrument. The parties confirm that they had an opportunity to read the complete text and seek independent advice before acceptance.

SIGNATURE CONFIRMATION
The parties accept this agreement through their respective signature blocks. Matching signature copies identify the same residential instrument and add no new party, date, premises reference, or financial term.
```

### `doc-04`

Wrong fields exemplified: `contract_end_date`, `security_deposit_aed`

```text
RESIDENTIAL TENANCY AGREEMENT

SCHEDULE A — KEY TERMS
SELECTED ADMINISTRATIVE DETAILS
+-------------------+---------------------------+
| Field             | Agreed detail             |
+-------------------+---------------------------+
| المستأجر / Tenant | Aya Morimoto (the Tenant) |
+-------------------+---------------------------+

Schedule A forms part of this agreement; operative prose controls every matter not recorded in the table.

OPERATIVE TERMS
YOUSEF MAJID AL KETBI is the Landlord, with leasing agent Tala Mensah authorised only to coordinate access and paperwork; the representative acquires no ownership interest. The demised premises are Unit F-2912; parking bay P-566 is a separate access reference and is not part of the unit identifier. The unit lies in Silver Ghaf Court, within the wider community of Al Rimal Orchard; the building name does not replace the community.

The contractual term is a term of twelve months commencing 2026-10-17; the handover inspection dated 20/10/2026 is an administrative event, not the tenancy commencement. The yearly residential consideration is One hundred forty-four thousand dirhams in total; the agent commission of Two thousand eight hundred dirhams (AED 2,800) and chiller account guarantee of 1050 AED are separate sums owed only to their named service providers. The tenancy security deposit is fixed at five per cent of the yearly residential consideration; that percentage does not describe either external service-provider amount.

Twelve post-dated cheques, each separately identified in the delivery record, constitute the complete set of rent instruments. If the Occupant ends the tenancy early, the agreed termination penalty equals one and one-half months of the agreed rent.

PURPOSE AND OCCUPATION
The home is let only for private residential occupation by the Occupant and members of the Occupant's household. It may not be used as a shop, office, holiday rental, shared lodging business, or address for an unrelated commercial licence. Guests remain the Occupant's responsibility while inside the premises or common areas.

HANDOVER AND CONDITION
At handover, both sides may complete a written condition record and attach dated photographs. Acceptance of keys confirms access but does not waive a hidden defect reported promptly after discovery. The Occupant shall keep the interior reasonably clean and return it in comparable condition, allowing for ordinary wear.

PAYMENT ADMINISTRATION
Rent instruments shall be delivered to the Owner or a representative authorised in writing. Bank handling charges caused by a rejected instrument remain the Occupant's responsibility. Both sides should retain a receipt or bank record. Cash collection does not change a financial term unless both sides sign a written variation.

EJARI ADMINISTRATION
The parties shall provide ordinary identity and property papers needed for Ejari registration. A typing-centre receipt proves filing activity only and does not amend the dates, parties, premises, or financial bargain recorded here.

UTILITIES AND SERVICES
The Occupant is responsible for consumption-based household services connected to the premises. The Owner remains responsible for charges attaching solely to ownership of the building. Each side shall cooperate with account-opening papers, meter access, and final clearance without treating a service bill as part of the rent.

ARBITRATION
A dispute not resolved through good-faith discussion may be referred to one arbitrator seated in the same Emirate. The arbitrator may allocate filing costs in the award. This process clause creates no additional rent, instalment, or utility charge.

CARE OF THE PREMISES
Routine cleaning, replacement of consumable items, and repair of damage caused by misuse fall to the Occupant. Structural defects and failures caused by age fall to the Owner, subject to building access rules. A problem should be reported promptly with enough detail for a suitable technician to be arranged.

ALTERATIONS
Painting, drilling into stone, changing locks, installing exterior equipment, or altering service connections requires the Owner's written consent in advance. Any approved work must comply with building management rules and be carried out by a competent person. Consent to one alteration does not imply consent to another.

ACCESS AND PRIVACY
The Owner may request access at a reasonable hour for inspection, repair, or a building-management requirement. Except in a genuine emergency, the parties shall coordinate a suitable time in writing. The Owner shall not interfere unnecessarily with peaceful occupation, and the Occupant shall not unreasonably withhold access.

CONDUCT AND COMMON AREAS
The Occupant shall observe access, parking, waste, noise, pool, lift, and visitor rules issued for the building. Corridors and fire routes must remain clear. Any access card or key supplied for common facilities remains linked to the premises and may not be copied for an unrelated person.

RECORDS AND CHANGES
This agreement and its operative particulars record the entire residential arrangement. A change is effective only when written clearly and accepted by both sides. Informal messages may coordinate practical matters, but they do not replace a signed change to a financial or occupancy obligation.

COUNTERPARTS
The agreement may be signed in matching counterparts or by an accepted electronic signature method. Each counterpart is treated as part of the same instrument. The parties confirm that they had an opportunity to read the complete text and seek independent advice before acceptance.

SIGNATURE CONFIRMATION
The parties accept this agreement through their respective signature blocks. Matching signature copies identify the same residential instrument and add no new party, date, premises reference, or financial term.
```

---

This pack contains training-set data only. Holdout documents and holdout gold exist but are never shown to you.
