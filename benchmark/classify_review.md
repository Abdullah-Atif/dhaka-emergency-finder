# Classifier: third hand check (2026-10-23)

A fresh random sample of 50 of the 447 `healthcare.hospital` places in Dhaka (seed 20261023), classified **after** all earlier fixes and reviewed by hand. The two earlier samples are in [classify_eval.md](classify_eval.md) and the [tutorial](../docs/tutorial.md).

**Result: 47 of 50 right. The 3 misses all came out as "unknown"**: no non-hospital was promoted and no emergency hospital was hidden. Two of the three are fixed now (after this review, so they no longer count as an independent test).

| # | Name in the map data | Classifier | Verdict |
|---|---|---|---|
| 1 | Dhaka Mohanagar General Hospital, Babubazar Bridge, Dhaka | yes · major | right |
| 2 | Dr Ainul Islam Khan Chamber(ড আইনুল ইসলাম চেম্বার) | no | right |
| 3 | ইবনে সিনা মেডিকেল কলেজ হাসপাতাল / Ibn Sina Medical College Hospital | likely · major | right |
| 4 | Bresba Medical Services LTD. | unknown | right |
| 5 | Newton maternity clinic, Hospital | specialised / maternity | right |
| 6 | ICDDRB, Kamalapur Field office | unknown | miss: an office, not a facility ("Field office" is in the second comma part, which is ignored so that addresses like "Mosque Road" do not mislead). Left as is: unknown is harmless. |
| 7 | Dhaka Central International Medical College & Hospital | likely · major | right |
| 8 | Physical Medicine and Rehabilitation Ward / Physical Medicine and Rehabilitation Ward | no | right |
| 9 | Institute of Nuclear Medicine | unknown | miss: nuclear-medicine institute (imaging and therapy, no emergency department). Fixed: "nuclear medicine" is now a diagnostic word. |
| 10 | (no name) | unknown | right |
| 11 | MARKS HOSPITAL | likely | right |
| 12 | Al arafat hospital | likely | right |
| 13 | Life Care | unknown | right |
| 14 | ওয়েলকেয়ার হসপিটাল লিমিটেড / Wellcare Hospital Limited | likely | right |
| 15 | Burn & Plastic Surgery Unit, Hospital, Secretariate Road, Dhaka Medical College Hospital, Dhaka | specialised / burn | right |
| 16 | General Medical Hospital | likely | right |
| 17 | Homeopathic Charitable Hospital, Hospital | no | right |
| 18 | Family Dentist | no | right |
| 19 | Puspit Nursing Home | unknown | right |
| 20 | Diabetic Hospital | likely | right |
| 21 | Popular | unknown | right |
| 22 | Ibn Sina Cancer Diagnostic Center | no | right |
| 23 | Ad-din Berrister Rafiq-ul- Haque hospital,Jurain | likely | right |
| 24 | Padma General Hospital, Sonargaon Road, Dhaka | likely | right |
| 25 | Lubana General Hospital & Uttara Cardiac Center | likely / heart | right |
| 26 | (no name) | unknown | right |
| 27 | B.M. Hospital, Hospital | likely | right |
| 28 | Modern Physiotherapy | no | right |
| 29 | সেন্ট্রাল হসপিটাল লিমিটেড / Central Hospital Limited | likely | right |
| 30 | Radda MCH-FP Centre (Mirpur-10), Hospital | specialised / maternity | right |
| 31 | ঢাকা মেডিক্যাল কলেজ হাসপাতাল / Dhaka Medical College Hospital | confirmed · major | right |
| 32 | Japan Bangladesh Friendship Hospital | likely | right |
| 33 | BIHS General Hospital | likely | right |
| 34 | Eye hospital | specialised / eye | right |
| 35 | Uttara Cresent | unknown | right |
| 36 | Aitam Metarnity and General Hospital | likely / maternity | right |
| 37 | English / English | unknown | right |
| 38 | Combind Care | unknown | right |
| 39 | Platinum Hospital Limited, Panthapath, Dhaka | likely | right |
| 40 | DigiLab | unknown | miss: a laboratory ("lab" is joined into the name). Fixed: "digilab" is now a laboratory word. |
| 41 | ভার্ড চক্ষু হাসপাতাল / Vard Eye Hospital | specialised / eye | right |
| 42 | Jahan Ara Clinic | unknown | right |
| 43 | Transfusion Medicine Department / Transfusion Medicine Department | no | right |
| 44 | Green Specialized Hospital (Pvt. Ltd.) | likely | right |
| 45 | Ad-Din Women's Medical college & Hospital | likely · major | right |
| 46 | AMZ HOSPITAL LTD | likely | right |
| 47 | Unico Hospitals PLC, Green Rd, Dhaka | likely | right |
| 48 | মুগদা মেডিক্যাল কলেজ হাসপাতাল / Mugda Medical College Hospital | yes · major | right |
| 49 | Dr. A R Khan Hospital, Hospital | likely | right |
| 50 | Dhaka Medical College Hospital, Government hospital, Secretariat Rd, Dhaka | confirmed · major | right |
