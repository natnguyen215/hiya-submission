# Eval results

2026-10-08 07:58 · model `gemini-3.5-flash-lite` · thinking `low` · cache off · 3 run(s) per script

> **14 LLM requests failed, so the outcomes below are not meaningful.** See the list at the end.

| Script | Result |
|---|---|
| demo_call | 7/8 moments pass in every run; all moments pass in 2/3 runs |
| demo_call_stt_noise | 7/8 moments pass in every run; all moments pass in 1/3 runs |
| control_call | flags per run 0, 0, 1 (target ≤1), spoken 0, 0, 0 (target 0) → PASS |
| adversarial_clean | flags per run 0, 0, 0 (target ≤1), spoken 0, 0, 0 (target 0) → PASS |
| live_regressions | 2/3 moments pass in every run; all moments pass in 2/3 runs |
| summon_checks | 8/10 moments pass in every run; all moments pass in 0/3 runs |

## demo_call

| Line | Expected | Run 1 | Run 2 | Run 3 | Passed |
|---|---|---|---|---|---|
| d04 (t5) | MISREAD_TERM → resolved | MISREAD_TERM → resolved | MISREAD_TERM → resolved | MISREAD_TERM → resolved | 3/3 |
| d10 (t11) | MISREAD_TERM → spoken | MISREAD_TERM → spoken | MISREAD_TERM → spoken | MISREAD_TERM → spoken | 3/3 |
| d15 (t17) | UNEXPLAINED_JARGON → resolved | UNEXPLAINED_JARGON → resolved | UNEXPLAINED_JARGON → resolved | UNEXPLAINED_JARGON → resolved | 3/3 |
| d17 (t19) | UNANSWERED_QUESTION → spoken | **none (FAIL)** | UNANSWERED_QUESTION → spoken | UNANSWERED_QUESTION → spoken | 2/3 |
| d23 (t26) | UNEXPLAINED_JARGON → recap | none | none | none | 3/3 |
| d25 (t28) | SUMMON → answered | answered | answered | answered | 3/3 |
| d29 (t33) | no flag → none | none | none | none | 3/3 |
| d31 (t35) | no flag → none | none | none | none | 3/3 |

Run 1, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t27 | 21 | yes | G9 | A Parent PLUS loan is an optional federal loan borrowed by the parent, requiring a separate application, credit check, and repayment. |

<details><summary>Run 1: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi, Maria? It's Alex from financial aid at Westbrook State. Daniel's award letter is ready, so I wanted to walk you through it.
t3 PARENT: Oh, wonderful, thank you. I have it pulled up right here.
t4 COUNSELOR: Perfect. Okay, big number first. Daniel's total aid package is $31,500.
t5 PARENT: Oh, thank goodness. So it's covered.
t6 COUNSELOR: Well, not quite, it isn't all free money. $14,000 of it is loans, which get paid back, and $2,500 is work-study, which Daniel earns at a campus job.
t7 PARENT: Oh. I'm glad you said that. So how much is actually free?
t8 COUNSELOR: The grants, $15,000. That's the Westbrook Grant, $9,000, and the federal Pell Grant, $6,000. Grants never get paid back.
t9 PARENT: Okay. So $15,000 is free, and the rest is loans and his campus job.
t10 COUNSELOR: That's right. Oh, and Daniel was also selected for verification.
t11 PARENT: Oh good, so we're verified?
t12 COUNSELOR: So, on to housing. Housing and meals are estimated at $16,500 for the year, out of a total yearly cost of $38,000.
t13 BEACON: Quick check for the family: does being selected for verification mean they need to submit more documents?
t14 COUNSELOR: Oh, good catch, thank you. Maria, sorry, I went right past that. Verification means the school needs more documents from you, like tax return transcripts and a verification worksheet. They're due July 15, or Daniel's aid could be delayed or canceled.
t15 PARENT: Oh, I had that backwards. So we still owe paperwork, and it's due July 15.
t16 COUNSELOR: Exactly. Now, to keep the Westbrook Grant, Daniel needs to maintain SAP each term.
t17 PARENT (3.0s pause): ...Okay.
t18 COUNSELOR: Sorry, let me explain. SAP is Satisfactory Academic Progress. Each term, Daniel needs at least a 2.0 GPA, about a C average, and has to complete at least 67 percent of the credits he attempts.
t19 PARENT: Got it, a C average, and he finishes 67 percent of the credits he attempts. Um, does the work-study money have to be paid back?
t20 COUNSELOR: So, next step. You'll accept the awards in the student portal, and you can accept or decline each one separately.
t21 COUNSELOR: Once you submit, you'll get an email confirmation.
t22 COUNSELOR: Oh, you're right, I skipped your question, Maria. No, work-study isn't paid back. Daniel earns the $2,500 as paychecks from a campus job. It just isn't credited to the bill upfront.
t23 PARENT: Oh, okay. So it's his paycheck, not a loan, but it won't lower the bill upfront.
t24 COUNSELOR: Right. And he qualified for work-study partly because of your SAI, which came from the FAFSA you filed.
t25 PARENT: Oh, he'll be thrilled. He's already talking about working at the campus library. He practically lives there.
t26 COUNSELOR: Ha, I love that. Tell him to apply early, those jobs go fast.
t27 PARENT: Beacon, what's a Parent PLUS loan?
t28 BEACON: A Parent PLUS loan is an optional federal loan borrowed by the parent, requiring a separate application, credit check, and repayment.
t29 COUNSELOR: Yep, that's exactly right. And I'd underline the optional part. You don't have to decide on it today.
t30 PARENT: Okay, good. That's a big one, so I'd like to think it over.
t31 COUNSELOR: Totally fair. So here's the whole picture. The full cost is $38,000. Accepting every piece of aid, including the Parent PLUS loan, covers $31,500, which leaves $6,500 for your family to pay.
t32 PARENT: So even taking every loan and the work-study, we'd still need $6,500 of our own.
t33 COUNSELOR: Right. The letter also lists a net price of $23,000. That's the full cost minus only the grants, the free money.
t34 PARENT: Okay, $38,000 minus the $15,000 in grants. So $23,000 is what we'd cover with loans, work-study, and our own money.
t35 COUNSELOR: So, next steps. Accept or decline each award in the student portal, and send the verification documents by July 15.
t36 PARENT: Got it. Awards in the portal, documents by July 15. Thank you so much, Alex, this really helped.
t37 COUNSELOR: You're so welcome, Maria. And congratulations to Daniel!
t38 PARENT: Thank you! Bye now.

f1 MISREAD_TERM [total_aid_covers_everything] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
parent asked: “So how much is actually free?”
t8 answered the question from t7
f2 MISREAD_TERM [verification_means_approved] → nudged: private card for the counselor
f2 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f2 → spoken: Beacon asked aloud
f3 UNEXPLAINED_JARGON [sap_not_explained] → nudged: private card for the counselor
f3 → resolved: the counselor clarified it
parent asked: “does the work-study money have to be paid back?”
t20 answered the question from t19
```

</details>

Run 2, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t28 | 17 | yes | G9 | A Parent PLUS loan is a federal loan the parent borrows to help pay dependent undergraduate costs. |

<details><summary>Run 2: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi, Maria? It's Alex from financial aid at Westbrook State. Daniel's award letter is ready, so I wanted to walk you through it.
t3 PARENT: Oh, wonderful, thank you. I have it pulled up right here.
t4 COUNSELOR: Perfect. Okay, big number first. Daniel's total aid package is $31,500.
t5 PARENT: Oh, thank goodness. So it's covered.
t6 COUNSELOR: Well, not quite, it isn't all free money. $14,000 of it is loans, which get paid back, and $2,500 is work-study, which Daniel earns at a campus job.
t7 PARENT: Oh. I'm glad you said that. So how much is actually free?
t8 COUNSELOR: The grants, $15,000. That's the Westbrook Grant, $9,000, and the federal Pell Grant, $6,000. Grants never get paid back.
t9 PARENT: Okay. So $15,000 is free, and the rest is loans and his campus job.
t10 COUNSELOR: That's right. Oh, and Daniel was also selected for verification.
t11 PARENT: Oh good, so we're verified?
t12 COUNSELOR: So, on to housing. Housing and meals are estimated at $16,500 for the year, out of a total yearly cost of $38,000.
t13 BEACON: Quick check for the family: do they need to submit documents for verification?
t14 COUNSELOR: Oh, good catch, thank you. Maria, sorry, I went right past that. Verification means the school needs more documents from you, like tax return transcripts and a verification worksheet. They're due July 15, or Daniel's aid could be delayed or canceled.
t15 PARENT: Oh, I had that backwards. So we still owe paperwork, and it's due July 15.
t16 COUNSELOR: Exactly. Now, to keep the Westbrook Grant, Daniel needs to maintain SAP each term.
t17 PARENT (3.0s pause): ...Okay.
t18 COUNSELOR: Sorry, let me explain. SAP is Satisfactory Academic Progress. Each term, Daniel needs at least a 2.0 GPA, about a C average, and has to complete at least 67 percent of the credits he attempts.
t19 PARENT: Got it, a C average, and he finishes 67 percent of the credits he attempts. Um, does the work-study money have to be paid back?
t20 COUNSELOR: So, next step. You'll accept the awards in the student portal, and you can accept or decline each one separately.
t21 COUNSELOR: Once you submit, you'll get an email confirmation.
t22 BEACON: Quick check: Maria asked, “Does the work-study money have to be paid back?” Could we cover that?
t23 COUNSELOR: Oh, you're right, I skipped your question, Maria. No, work-study isn't paid back. Daniel earns the $2,500 as paychecks from a campus job. It just isn't credited to the bill upfront.
t24 PARENT: Oh, okay. So it's his paycheck, not a loan, but it won't lower the bill upfront.
t25 COUNSELOR: Right. And he qualified for work-study partly because of your SAI, which came from the FAFSA you filed.
t26 PARENT: Oh, he'll be thrilled. He's already talking about working at the campus library. He practically lives there.
t27 COUNSELOR: Ha, I love that. Tell him to apply early, those jobs go fast.
t28 PARENT: Beacon, what's a Parent PLUS loan?
t29 BEACON: A Parent PLUS loan is a federal loan the parent borrows to help pay dependent undergraduate costs.
t30 COUNSELOR: Yep, that's exactly right. And I'd underline the optional part. You don't have to decide on it today.
t31 PARENT: Okay, good. That's a big one, so I'd like to think it over.
t32 COUNSELOR: Totally fair. So here's the whole picture. The full cost is $38,000. Accepting every piece of aid, including the Parent PLUS loan, covers $31,500, which leaves $6,500 for your family to pay.
t33 PARENT: So even taking every loan and the work-study, we'd still need $6,500 of our own.
t34 COUNSELOR: Right. The letter also lists a net price of $23,000. That's the full cost minus only the grants, the free money.
t35 PARENT: Okay, $38,000 minus the $15,000 in grants. So $23,000 is what we'd cover with loans, work-study, and our own money.
t36 COUNSELOR: So, next steps. Accept or decline each award in the student portal, and send the verification documents by July 15.
t37 PARENT: Got it. Awards in the portal, documents by July 15. Thank you so much, Alex, this really helped.
t38 COUNSELOR: You're so welcome, Maria. And congratulations to Daniel!
t39 PARENT: Thank you! Bye now.

f1 MISREAD_TERM [total_aid_package_covers_everything] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
parent asked: “So how much is actually free?”
t8 answered the question from t7
f2 MISREAD_TERM [selected_for_verification_means_verified] → nudged: private card for the counselor
f2 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f2 → spoken: Beacon asked aloud
f3 UNEXPLAINED_JARGON [sap_not_explained] → nudged: private card for the counselor
f3 → resolved: the counselor clarified it
f4 UNEXPLAINED_JARGON [sap_not_explained_new] → nudged: private card for the counselor
parent asked: “Does the work-study money have to be paid back?”
f4 → resolved: the counselor clarified it
f5 UNANSWERED_QUESTION [unanswered_t19] → nudged: unanswered after 1 counselor turn(s)
f5 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f5 → spoken: Beacon asked aloud
t23 answered the question from t19
```

</details>

Run 3, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t28 | 23 | yes | G9 | A Parent PLUS loan is a federal loan that parents borrow to help pay undergraduate costs, requiring a separate application and credit check. |

<details><summary>Run 3: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi, Maria? It's Alex from financial aid at Westbrook State. Daniel's award letter is ready, so I wanted to walk you through it.
t3 PARENT: Oh, wonderful, thank you. I have it pulled up right here.
t4 COUNSELOR: Perfect. Okay, big number first. Daniel's total aid package is $31,500.
t5 PARENT: Oh, thank goodness. So it's covered.
t6 COUNSELOR: Well, not quite, it isn't all free money. $14,000 of it is loans, which get paid back, and $2,500 is work-study, which Daniel earns at a campus job.
t7 PARENT: Oh. I'm glad you said that. So how much is actually free?
t8 COUNSELOR: The grants, $15,000. That's the Westbrook Grant, $9,000, and the federal Pell Grant, $6,000. Grants never get paid back.
t9 PARENT: Okay. So $15,000 is free, and the rest is loans and his campus job.
t10 COUNSELOR: That's right. Oh, and Daniel was also selected for verification.
t11 PARENT: Oh good, so we're verified?
t12 COUNSELOR: So, on to housing. Housing and meals are estimated at $16,500 for the year, out of a total yearly cost of $38,000.
t13 BEACON: Quick check for the family: what documents are needed to finish verification?
t14 COUNSELOR: Oh, good catch, thank you. Maria, sorry, I went right past that. Verification means the school needs more documents from you, like tax return transcripts and a verification worksheet. They're due July 15, or Daniel's aid could be delayed or canceled.
t15 PARENT: Oh, I had that backwards. So we still owe paperwork, and it's due July 15.
t16 COUNSELOR: Exactly. Now, to keep the Westbrook Grant, Daniel needs to maintain SAP each term.
t17 PARENT (3.0s pause): ...Okay.
t18 COUNSELOR: Sorry, let me explain. SAP is Satisfactory Academic Progress. Each term, Daniel needs at least a 2.0 GPA, about a C average, and has to complete at least 67 percent of the credits he attempts.
t19 PARENT: Got it, a C average, and he finishes 67 percent of the credits he attempts. Um, does the work-study money have to be paid back?
t20 COUNSELOR: So, next step. You'll accept the awards in the student portal, and you can accept or decline each one separately.
t21 COUNSELOR: Once you submit, you'll get an email confirmation.
t22 BEACON: Quick check: Maria asked, “does the work-study money have to be paid back?” Could we cover that?
t23 COUNSELOR: Oh, you're right, I skipped your question, Maria. No, work-study isn't paid back. Daniel earns the $2,500 as paychecks from a campus job. It just isn't credited to the bill upfront.
t24 PARENT: Oh, okay. So it's his paycheck, not a loan, but it won't lower the bill upfront.
t25 COUNSELOR: Right. And he qualified for work-study partly because of your SAI, which came from the FAFSA you filed.
t26 PARENT: Oh, he'll be thrilled. He's already talking about working at the campus library. He practically lives there.
t27 COUNSELOR: Ha, I love that. Tell him to apply early, those jobs go fast.
t28 PARENT: Beacon, what's a Parent PLUS loan?
t29 BEACON: A Parent PLUS loan is a federal loan that parents borrow to help pay undergraduate costs, requiring a separate application and credit check.
t30 COUNSELOR: Yep, that's exactly right. And I'd underline the optional part. You don't have to decide on it today.
t31 PARENT: Okay, good. That's a big one, so I'd like to think it over.
t32 COUNSELOR: Totally fair. So here's the whole picture. The full cost is $38,000. Accepting every piece of aid, including the Parent PLUS loan, covers $31,500, which leaves $6,500 for your family to pay.
t33 PARENT: So even taking every loan and the work-study, we'd still need $6,500 of our own.
t34 COUNSELOR: Right. The letter also lists a net price of $23,000. That's the full cost minus only the grants, the free money.
t35 PARENT: Okay, $38,000 minus the $15,000 in grants. So $23,000 is what we'd cover with loans, work-study, and our own money.
t36 COUNSELOR: So, next steps. Accept or decline each award in the student portal, and send the verification documents by July 15.
t37 PARENT: Got it. Awards in the portal, documents by July 15. Thank you so much, Alex, this really helped.
t38 COUNSELOR: You're so welcome, Maria. And congratulations to Daniel!
t39 PARENT: Thank you! Bye now.

f1 MISREAD_TERM [total_aid_package_covers_everything] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
parent asked: “So how much is actually free?”
t8 answered the question from t7
f2 MISREAD_TERM [verification_means_approved] → nudged: private card for the counselor
f2 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f2 → spoken: Beacon asked aloud
f3 UNEXPLAINED_JARGON [sap_not_explained] → nudged: private card for the counselor
f3 → resolved: the counselor clarified it
parent asked: “does the work-study money have to be paid back?”
f4 UNANSWERED_QUESTION [unanswered_t19] → nudged: unanswered after 1 counselor turn(s)
ignored [sap_not_explained]: duplicate of f3
f4 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f4 → spoken: Beacon asked aloud
t23 answered the question from t19
```

</details>

## demo_call_stt_noise

| Line | Expected | Run 1 | Run 2 | Run 3 | Passed |
|---|---|---|---|---|---|
| s04 (t5) | MISREAD_TERM → resolved | MISREAD_TERM → resolved | MISREAD_TERM → resolved | MISREAD_TERM → resolved | 3/3 |
| s10 (t11) | MISREAD_TERM → spoken | MISREAD_TERM → spoken | MISREAD_TERM → spoken | MISREAD_TERM → spoken | 3/3 |
| s15 (t17) | UNEXPLAINED_JARGON → resolved | UNEXPLAINED_JARGON → resolved | UNEXPLAINED_JARGON → resolved | UNEXPLAINED_JARGON → resolved | 3/3 |
| s17 (t19) | UNANSWERED_QUESTION → spoken | UNANSWERED_QUESTION → spoken | **UNANSWERED_QUESTION → resolved (FAIL)** | **UNANSWERED_QUESTION → resolved (FAIL)** | 1/3 |
| s23 (t25) | UNEXPLAINED_JARGON → recap | none | none | none | 3/3 |
| s25 (t27) | SUMMON → answered | answered | answered | answered | 3/3 |
| s29 (t32) | no flag → none | none | none | none | 3/3 |
| s31 (t34) | no flag → none | none | none | none | 3/3 |

Run 1, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t28 | 21 | yes | G9 | A Parent PLUS Loan is an optional federal loan borrowed by the parent, requiring a credit check and a separate application. |

<details><summary>Run 1: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: hi maria it's alex from financial aid at west brook state daniel's award letter is ready so i wanted to walk you through it
t3 PARENT: oh wonderful thank you i have it pulled up right here
t4 COUNSELOR: perfect okay big number first daniel's total aid package is thirty one thousand five hundred
t5 PARENT: oh thank goodness so it's covered
t6 COUNSELOR: well not quite it isn't all free money 14,000 of it is loans which get paid back and 2500 is work study which daniel earns at a campus job
t7 PARENT: oh i'm glad you said that so how much is actually free
t8 COUNSELOR: the grants 15,000 that's the west brook grant 9,000 and the federal pal grant 6,000 grants never get paid back
t9 PARENT: okay so 15,000 is free and the rest is loans and his campus job
t10 COUNSELOR: that's right oh and daniel was also selected for verification
t11 PARENT: oh good so we're verified
t12 COUNSELOR: so on to housing housing and meals are estimated at 16,500 for the year out of a total yearly cost of 38,000
t13 BEACON: Quick check for the family: what does verification mean they need to do?
t14 COUNSELOR: oh good catch thank you maria sorry i went right past that verification means the school needs more documents from you like tax return transcripts and a verification worksheet they're due july 15th or daniel's aid could be delayed or canceled
t15 PARENT: oh i had that backwards so we still owe paperwork and it's due july 15th
t16 COUNSELOR: exactly now to keep the west brook grant daniel needs to maintain sap each term
t17 PARENT (3.0s pause): okay
t18 COUNSELOR: sorry let me explain sap is satisfactory academic progress each term daniel needs at least a 2.0 gpa about a sea average and has to complete at least 67% of the credits he attempts
t19 PARENT: got it a sea average and he finishes 67% of the credits he attempts um does the work study money have to be paid back
t20 COUNSELOR: so next step you'll accept the awards in the student portal and you can accept or decline each one separately
t21 COUNSELOR: once you submit you'll get an email confirmation
t22 BEACON: Quick check: Maria asked, “does the work study money have to be paid back” Could we cover that?
t23 COUNSELOR: oh you're right i skipped your question maria no work study isn't paid back daniel earns the 2500 as paychecks from a campus job it just isn't credited to the bill up front
t24 PARENT: oh okay so it's his paycheck not a loan but it won't lower the bill up front
t25 COUNSELOR: right and he qualified for work study partly because of your sai which came from the fafsa you filed
t26 PARENT: oh he'll be thrilled he's already talking about working at the campus library he practically lives there
t27 COUNSELOR: ha i love that tell him to apply early those jobs go fast
t28 PARENT: beacon what's a parent plus loan
t29 BEACON: A Parent PLUS Loan is an optional federal loan borrowed by the parent, requiring a credit check and a separate application.
t30 COUNSELOR: yep that's exactly right and i'd underline the optional part you don't have to decide on it today
t31 PARENT: okay good that's a big one so i'd like to think it over
t32 COUNSELOR: totally fair so here's the whole picture the full cost is $38,000 accepting every piece of aid including the parent plus loan covers $31,500 which leaves 6500 for your family to pay
t33 PARENT: so even taking every loan and the work study we'd still need 6500 of our own
t34 COUNSELOR: right the letter also lists a net price of 23,000 that's the full cost minus only the grants the free money
t35 PARENT: okay 38,000 minus the 15,000 in grants so 23,000 is what we'd cover with loans work study and our own money
t36 COUNSELOR: so next steps accept or decline each award in the student portal and send the verification documents by july 15th
t37 PARENT: got it awards in the portal documents by july 15th thank you so much alex this really helped
t38 COUNSELOR: you're so welcome maria and congratulations to daniel
t39 PARENT: thank you bye now

f1 MISREAD_TERM [total_aid_package_covers_everything] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
parent asked: “so how much is actually free”
t8 answered the question from t7
f2 MISREAD_TERM [verification_means_approved] → nudged: private card for the counselor
f2 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f2 → spoken: Beacon asked aloud
f3 UNEXPLAINED_JARGON [sap_not_explained] → nudged: private card for the counselor
f3 → resolved: the counselor clarified it
parent asked: “does the work study money have to be paid back”
f4 UNANSWERED_QUESTION [unanswered_t19] → nudged: unanswered after 1 counselor turn(s)
f4 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f4 → spoken: Beacon asked aloud
t23 answered the question from t19
```

</details>

Run 2, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t27 | 20 | yes | L15, G9 | A parent PLUS loan is an optional federal loan borrowed by the parent, requiring a separate application and credit check. |

<details><summary>Run 2: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: hi maria it's alex from financial aid at west brook state daniel's award letter is ready so i wanted to walk you through it
t3 PARENT: oh wonderful thank you i have it pulled up right here
t4 COUNSELOR: perfect okay big number first daniel's total aid package is thirty one thousand five hundred
t5 PARENT: oh thank goodness so it's covered
t6 COUNSELOR: well not quite it isn't all free money 14,000 of it is loans which get paid back and 2500 is work study which daniel earns at a campus job
t7 PARENT: oh i'm glad you said that so how much is actually free
t8 COUNSELOR: the grants 15,000 that's the west brook grant 9,000 and the federal pal grant 6,000 grants never get paid back
t9 PARENT: okay so 15,000 is free and the rest is loans and his campus job
t10 COUNSELOR: that's right oh and daniel was also selected for verification
t11 PARENT: oh good so we're verified
t12 COUNSELOR: so on to housing housing and meals are estimated at 16,500 for the year out of a total yearly cost of 38,000
t13 BEACON: Quick check for the family: what is needed to complete verification?
t14 COUNSELOR: oh good catch thank you maria sorry i went right past that verification means the school needs more documents from you like tax return transcripts and a verification worksheet they're due july 15th or daniel's aid could be delayed or canceled
t15 PARENT: oh i had that backwards so we still owe paperwork and it's due july 15th
t16 COUNSELOR: exactly now to keep the west brook grant daniel needs to maintain sap each term
t17 PARENT (3.0s pause): okay
t18 COUNSELOR: sorry let me explain sap is satisfactory academic progress each term daniel needs at least a 2.0 gpa about a sea average and has to complete at least 67% of the credits he attempts
t19 PARENT: got it a sea average and he finishes 67% of the credits he attempts um does the work study money have to be paid back
t20 COUNSELOR: so next step you'll accept the awards in the student portal and you can accept or decline each one separately
t21 COUNSELOR: once you submit you'll get an email confirmation
t22 COUNSELOR: oh you're right i skipped your question maria no work study isn't paid back daniel earns the 2500 as paychecks from a campus job it just isn't credited to the bill up front
t23 PARENT: oh okay so it's his paycheck not a loan but it won't lower the bill up front
t24 COUNSELOR: right and he qualified for work study partly because of your sai which came from the fafsa you filed
t25 PARENT: oh he'll be thrilled he's already talking about working at the campus library he practically lives there
t26 COUNSELOR: ha i love that tell him to apply early those jobs go fast
t27 PARENT: beacon what's a parent plus loan
t28 BEACON: A parent PLUS loan is an optional federal loan borrowed by the parent, requiring a separate application and credit check.
t29 COUNSELOR: yep that's exactly right and i'd underline the optional part you don't have to decide on it today
t30 PARENT: okay good that's a big one so i'd like to think it over
t31 COUNSELOR: totally fair so here's the whole picture the full cost is $38,000 accepting every piece of aid including the parent plus loan covers $31,500 which leaves 6500 for your family to pay
t32 PARENT: so even taking every loan and the work study we'd still need 6500 of our own
t33 COUNSELOR: right the letter also lists a net price of 23,000 that's the full cost minus only the grants the free money
t34 PARENT: okay 38,000 minus the 15,000 in grants so 23,000 is what we'd cover with loans work study and our own money
t35 COUNSELOR: so next steps accept or decline each award in the student portal and send the verification documents by july 15th
t36 PARENT: got it awards in the portal documents by july 15th thank you so much alex this really helped
t37 COUNSELOR: you're so welcome maria and congratulations to daniel
t38 PARENT: thank you bye now

f1 MISREAD_TERM [aid_package_covers_everything] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
parent asked: “so how much is actually free”
t8 answered the question from t7
f2 MISREAD_TERM [verification_treated_as_approval] → nudged: private card for the counselor
f2 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f2 → spoken: Beacon asked aloud
f3 UNEXPLAINED_JARGON [sap_not_explained] → nudged: private card for the counselor
f3 → resolved: the counselor clarified it
parent asked: “does the work study money have to be paid back”
f4 UNANSWERED_QUESTION [unanswered_t19] → nudged: unanswered after 1 counselor turn(s)
f4 → resolved: the counselor clarified it
t22 answered the question from t19
```

</details>

Run 3, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t27 | 20 | yes | G9 | A parent plus loan is an optional federal loan borrowed by the parent, requiring a separate application and credit check. |

<details><summary>Run 3: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: hi maria it's alex from financial aid at west brook state daniel's award letter is ready so i wanted to walk you through it
t3 PARENT: oh wonderful thank you i have it pulled up right here
t4 COUNSELOR: perfect okay big number first daniel's total aid package is thirty one thousand five hundred
t5 PARENT: oh thank goodness so it's covered
t6 COUNSELOR: well not quite it isn't all free money 14,000 of it is loans which get paid back and 2500 is work study which daniel earns at a campus job
t7 PARENT: oh i'm glad you said that so how much is actually free
t8 COUNSELOR: the grants 15,000 that's the west brook grant 9,000 and the federal pal grant 6,000 grants never get paid back
t9 PARENT: okay so 15,000 is free and the rest is loans and his campus job
t10 COUNSELOR: that's right oh and daniel was also selected for verification
t11 PARENT: oh good so we're verified
t12 COUNSELOR: so on to housing housing and meals are estimated at 16,500 for the year out of a total yearly cost of 38,000
t13 BEACON: Quick check for the family: what does being selected for verification mean they need to do?
t14 COUNSELOR: oh good catch thank you maria sorry i went right past that verification means the school needs more documents from you like tax return transcripts and a verification worksheet they're due july 15th or daniel's aid could be delayed or canceled
t15 PARENT: oh i had that backwards so we still owe paperwork and it's due july 15th
t16 COUNSELOR: exactly now to keep the west brook grant daniel needs to maintain sap each term
t17 PARENT (3.0s pause): okay
t18 COUNSELOR: sorry let me explain sap is satisfactory academic progress each term daniel needs at least a 2.0 gpa about a sea average and has to complete at least 67% of the credits he attempts
t19 PARENT: got it a sea average and he finishes 67% of the credits he attempts um does the work study money have to be paid back
t20 COUNSELOR: so next step you'll accept the awards in the student portal and you can accept or decline each one separately
t21 COUNSELOR: once you submit you'll get an email confirmation
t22 COUNSELOR: oh you're right i skipped your question maria no work study isn't paid back daniel earns the 2500 as paychecks from a campus job it just isn't credited to the bill up front
t23 PARENT: oh okay so it's his paycheck not a loan but it won't lower the bill up front
t24 COUNSELOR: right and he qualified for work study partly because of your sai which came from the fafsa you filed
t25 PARENT: oh he'll be thrilled he's already talking about working at the campus library he practically lives there
t26 COUNSELOR: ha i love that tell him to apply early those jobs go fast
t27 PARENT: beacon what's a parent plus loan
t28 BEACON: A parent plus loan is an optional federal loan borrowed by the parent, requiring a separate application and credit check.
t29 COUNSELOR: yep that's exactly right and i'd underline the optional part you don't have to decide on it today
t30 PARENT: okay good that's a big one so i'd like to think it over
t31 COUNSELOR: totally fair so here's the whole picture the full cost is $38,000 accepting every piece of aid including the parent plus loan covers $31,500 which leaves 6500 for your family to pay
t32 PARENT: so even taking every loan and the work study we'd still need 6500 of our own
t33 COUNSELOR: right the letter also lists a net price of 23,000 that's the full cost minus only the grants the free money
t34 PARENT: okay 38,000 minus the 15,000 in grants so 23,000 is what we'd cover with loans work study and our own money
t35 COUNSELOR: so next steps accept or decline each award in the student portal and send the verification documents by july 15th
t36 PARENT: got it awards in the portal documents by july 15th thank you so much alex this really helped
t37 COUNSELOR: you're so welcome maria and congratulations to daniel
t38 PARENT: thank you bye now

f1 MISREAD_TERM [total_aid_covers_everything] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
parent asked: “how much is actually free”
t8 answered the question from t7
f2 MISREAD_TERM [verification_means_approved] → nudged: private card for the counselor
f2 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f2 → spoken: Beacon asked aloud
f3 UNEXPLAINED_JARGON [sap_not_explained] → nudged: private card for the counselor
f3 → resolved: the counselor clarified it
parent asked: “does the work study money have to be paid back”
f4 UNANSWERED_QUESTION [unanswered_t19] → nudged: unanswered after 1 counselor turn(s)
t20 answered the question from t19
f4 → resolved: the counselor answered the question
```

</details>

## control_call

**Run 1: flags 0 (target ≤1) · spoken 0 (target 0) → PASS**

<details><summary>Run 1: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi, Maria, it's Alex from financial aid at Westbrook State. Is now still a good time?
t3 PARENT: Yes, hi, Alex. Perfect timing.
t4 COUNSELOR: Great. Daniel's award letter is ready. The cost of attendance, the school's estimate for the full year, is $38,000. His aid package is $31,500, and that's grants, which are free money, plus loans, plus work-study, which is pay from a campus job.
t5 PARENT: Okay. So how much of the $31,500 is actually free?
t6 COUNSELOR: The grants, $15,000. That's the Westbrook Grant, $9,000, and the federal Pell Grant, $6,000. Grants are never paid back.
t7 PARENT: Got it. And the rest is loans and work-study?
t8 COUNSELOR: Right. Loans total $14,000. With Daniel's subsidized loan, $3,500, the government covers the interest while he's in school. His unsubsidized loan, $2,000, builds interest right away. And the Parent PLUS loan, $8,500, is one you'd borrow yourself. It's optional and needs its own application and a credit check.
t9 PARENT: So the PLUS loan would be in my name, not Daniel's, and we don't have to take it.
t10 COUNSELOR: Exactly. The last piece is work-study, $2,500. Daniel earns it as paychecks from a campus job, so it's never paid back, but it isn't taken off the bill upfront.
t11 PARENT: So he earns it as he works, and we shouldn't count on it for the first bill.
t12 COUNSELOR: That's it. Next, Daniel was selected for verification. That means the school needs more documents, like tax return transcripts and a verification worksheet. They're due by July 15.
t13 PARENT: So it's paperwork we still owe, not an approval. What happens if we miss July 15?
t14 COUNSELOR: Then his aid could be delayed or canceled, so I'd send everything early. Also, to keep the Westbrook Grant, Daniel must maintain SAP, which means Satisfactory Academic Progress. That's at least a 2.0 GPA, about a C average, and completing at least 67 percent of his attempted credits, each term.
t15 PARENT: So at least a C average, and he finishes 67 percent of the credits he takes, every term, and the grant stays.
t16 COUNSELOR: Exactly. Altogether, accepting every award, including the Parent PLUS loan, covers $31,500 of the $38,000, leaving $6,500 for your family. The net price, $23,000, is the full cost minus just the grants.
t17 PARENT: So $23,000 is the real cost after the free money, and even taking everything, we'd still pay $6,500 ourselves.
t18 COUNSELOR: That's right. For next steps, accept or decline each award in the student portal. You'll get an email confirmation once you submit.
t19 PARENT: Mm-hm.
t20 COUNSELOR: And send the verification documents by July 15. Call me anytime with questions.
t21 PARENT: Will do. Awards in the portal, documents by July 15. Thanks, Alex, that was really clear.
t22 COUNSELOR: My pleasure, Maria. Congratulations to Daniel, and take care.

parent asked: “So how much of the $31,500 is actually free?”
t6 answered the question from t5
parent asked: “What happens if we miss July 15?”
t14 answered the question from t13
```

</details>

**Run 2: flags 0 (target ≤1) · spoken 0 (target 0) → PASS**

<details><summary>Run 2: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi, Maria, it's Alex from financial aid at Westbrook State. Is now still a good time?
t3 PARENT: Yes, hi, Alex. Perfect timing.
t4 COUNSELOR: Great. Daniel's award letter is ready. The cost of attendance, the school's estimate for the full year, is $38,000. His aid package is $31,500, and that's grants, which are free money, plus loans, plus work-study, which is pay from a campus job.
t5 PARENT: Okay. So how much of the $31,500 is actually free?
t6 COUNSELOR: The grants, $15,000. That's the Westbrook Grant, $9,000, and the federal Pell Grant, $6,000. Grants are never paid back.
t7 PARENT: Got it. And the rest is loans and work-study?
t8 COUNSELOR: Right. Loans total $14,000. With Daniel's subsidized loan, $3,500, the government covers the interest while he's in school. His unsubsidized loan, $2,000, builds interest right away. And the Parent PLUS loan, $8,500, is one you'd borrow yourself. It's optional and needs its own application and a credit check.
t9 PARENT: So the PLUS loan would be in my name, not Daniel's, and we don't have to take it.
t10 COUNSELOR: Exactly. The last piece is work-study, $2,500. Daniel earns it as paychecks from a campus job, so it's never paid back, but it isn't taken off the bill upfront.
t11 PARENT: So he earns it as he works, and we shouldn't count on it for the first bill.
t12 COUNSELOR: That's it. Next, Daniel was selected for verification. That means the school needs more documents, like tax return transcripts and a verification worksheet. They're due by July 15.
t13 PARENT: So it's paperwork we still owe, not an approval. What happens if we miss July 15?
t14 COUNSELOR: Then his aid could be delayed or canceled, so I'd send everything early. Also, to keep the Westbrook Grant, Daniel must maintain SAP, which means Satisfactory Academic Progress. That's at least a 2.0 GPA, about a C average, and completing at least 67 percent of his attempted credits, each term.
t15 PARENT: So at least a C average, and he finishes 67 percent of the credits he takes, every term, and the grant stays.
t16 COUNSELOR: Exactly. Altogether, accepting every award, including the Parent PLUS loan, covers $31,500 of the $38,000, leaving $6,500 for your family. The net price, $23,000, is the full cost minus just the grants.
t17 PARENT: So $23,000 is the real cost after the free money, and even taking everything, we'd still pay $6,500 ourselves.
t18 COUNSELOR: That's right. For next steps, accept or decline each award in the student portal. You'll get an email confirmation once you submit.
t19 PARENT: Mm-hm.
t20 COUNSELOR: And send the verification documents by July 15. Call me anytime with questions.
t21 PARENT: Will do. Awards in the portal, documents by July 15. Thanks, Alex, that was really clear.
t22 COUNSELOR: My pleasure, Maria. Congratulations to Daniel, and take care.

parent asked: “So how much of the $31,500 is actually free?”
t6 answered the question from t5
parent asked: “What happens if we miss July 15?”
t14 answered the question from t13
```

</details>

**Run 3: flags 1 (target ≤1) · spoken 0 (target 0) → PASS**

Run 3, flags not matched to a planted moment:

- f1 UNANSWERED_QUESTION `unanswered_t13` → resolved, evidence ['t13']

<details><summary>Run 3: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi, Maria, it's Alex from financial aid at Westbrook State. Is now still a good time?
t3 PARENT: Yes, hi, Alex. Perfect timing.
t4 COUNSELOR: Great. Daniel's award letter is ready. The cost of attendance, the school's estimate for the full year, is $38,000. His aid package is $31,500, and that's grants, which are free money, plus loans, plus work-study, which is pay from a campus job.
t5 PARENT: Okay. So how much of the $31,500 is actually free?
t6 COUNSELOR: The grants, $15,000. That's the Westbrook Grant, $9,000, and the federal Pell Grant, $6,000. Grants are never paid back.
t7 PARENT: Got it. And the rest is loans and work-study?
t8 COUNSELOR: Right. Loans total $14,000. With Daniel's subsidized loan, $3,500, the government covers the interest while he's in school. His unsubsidized loan, $2,000, builds interest right away. And the Parent PLUS loan, $8,500, is one you'd borrow yourself. It's optional and needs its own application and a credit check.
t9 PARENT: So the PLUS loan would be in my name, not Daniel's, and we don't have to take it.
t10 COUNSELOR: Exactly. The last piece is work-study, $2,500. Daniel earns it as paychecks from a campus job, so it's never paid back, but it isn't taken off the bill upfront.
t11 PARENT: So he earns it as he works, and we shouldn't count on it for the first bill.
t12 COUNSELOR: That's it. Next, Daniel was selected for verification. That means the school needs more documents, like tax return transcripts and a verification worksheet. They're due by July 15.
t13 PARENT: So it's paperwork we still owe, not an approval. What happens if we miss July 15?
t14 COUNSELOR: Then his aid could be delayed or canceled, so I'd send everything early. Also, to keep the Westbrook Grant, Daniel must maintain SAP, which means Satisfactory Academic Progress. That's at least a 2.0 GPA, about a C average, and completing at least 67 percent of his attempted credits, each term.
t15 PARENT: So at least a C average, and he finishes 67 percent of the credits he takes, every term, and the grant stays.
t16 COUNSELOR: Exactly. Altogether, accepting every award, including the Parent PLUS loan, covers $31,500 of the $38,000, leaving $6,500 for your family. The net price, $23,000, is the full cost minus just the grants.
t17 PARENT: So $23,000 is the real cost after the free money, and even taking everything, we'd still pay $6,500 ourselves.
t18 COUNSELOR: That's right. For next steps, accept or decline each award in the student portal. You'll get an email confirmation once you submit.
t19 PARENT: Mm-hm.
t20 COUNSELOR: And send the verification documents by July 15. Call me anytime with questions.
t21 PARENT: Will do. Awards in the portal, documents by July 15. Thanks, Alex, that was really clear.
t22 COUNSELOR: My pleasure, Maria. Congratulations to Daniel, and take care.

parent asked: “So how much of the $31,500 is actually free?”
t6 answered the question from t5
parent asked: “What happens if we miss July 15?”
f1 UNANSWERED_QUESTION [unanswered_t13] → nudged: unanswered after 1 counselor turn(s)
f1 → resolved: the counselor clarified it
t14 answered the question from t13
```

</details>

## adversarial_clean

**Run 1: flags 0 (target ≤1) · spoken 0 (target 0) → PASS**

<details><summary>Run 1: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi Maria, it's Alex from financial aid at Westbrook State. Do you have Daniel's award letter handy?
t3 PARENT: I do, it's right here.
t4 COUNSELOR: Great. His total aid package is $31,500. Before you get excited, that's a mix: $15,000 in grants, which are free money, $14,000 in loans, which get paid back, and $2,500 in work-study he earns at a campus job.
t5 PARENT: Okay, so the loans we pay back, and the grants we don't.
t6 COUNSELOR: Exactly right.
t7 PARENT: Wait, is the Parent PLUS loan part of that $31,500?
t8 COUNSELOR: Yes, it is. The Parent PLUS is $8,500 of the $14,000 in loans. It's in your name, it's optional, and it needs its own application and a credit check.
t9 PARENT: Got it, so that one would be mine to repay, and we can say no to it.
t10 COUNSELOR: Right. Your SAI, the Student Aid Index, is a number calculated from your FAFSA. It's not what you'll pay, it's just used to figure out what he qualifies for.
t11 PARENT: Mm-hm, okay.
t12 COUNSELOR: Daniel was also selected for verification. That's not an approval, it just means the school needs more paperwork, like tax return transcripts, by July 15.
t13 PARENT (2.6s pause): So we still have to send the tax transcripts, and the deadline is July 15.
t14 COUNSELOR: That's it. To keep the Westbrook Grant he needs SAP, Satisfactory Academic Progress: at least a 2.0 GPA and finishing 67 percent of the credits he attempts, every term.
t15 PARENT: Okay. He's a good student, so a C average shouldn't be a problem. What happens if he drops a class?
t16 COUNSELOR: One dropped class is usually fine, as long as he still completes at least 67 percent of what he attempts that term.
t17 PARENT: Okay, that makes sense.
t18 COUNSELOR: You'll accept or decline each award in the student portal. You'll get an email when it's submitted.
t19 PARENT: Mm-hm.
t20 COUNSELOR: The net price is $23,000, that's the full $38,000 cost minus the $15,000 in grants.
t21 PARENT: Okay, so the $23,000 is what's left before loans and work-study, and the loans we pay back.
t22 COUNSELOR: Exactly. Any other questions for me today?
t23 PARENT: No, I think that's everything. Thank you, Alex.

parent asked: “Wait, is the Parent PLUS loan part of that $31,500?”
t8 answered the question from t7
parent asked: “What happens if he drops a class?”
t16 answered the question from t15
```

</details>

**Run 2: flags 0 (target ≤1) · spoken 0 (target 0) → PASS**

<details><summary>Run 2: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi Maria, it's Alex from financial aid at Westbrook State. Do you have Daniel's award letter handy?
t3 PARENT: I do, it's right here.
t4 COUNSELOR: Great. His total aid package is $31,500. Before you get excited, that's a mix: $15,000 in grants, which are free money, $14,000 in loans, which get paid back, and $2,500 in work-study he earns at a campus job.
t5 PARENT: Okay, so the loans we pay back, and the grants we don't.
t6 COUNSELOR: Exactly right.
t7 PARENT: Wait, is the Parent PLUS loan part of that $31,500?
t8 COUNSELOR: Yes, it is. The Parent PLUS is $8,500 of the $14,000 in loans. It's in your name, it's optional, and it needs its own application and a credit check.
t9 PARENT: Got it, so that one would be mine to repay, and we can say no to it.
t10 COUNSELOR: Right. Your SAI, the Student Aid Index, is a number calculated from your FAFSA. It's not what you'll pay, it's just used to figure out what he qualifies for.
t11 PARENT: Mm-hm, okay.
t12 COUNSELOR: Daniel was also selected for verification. That's not an approval, it just means the school needs more paperwork, like tax return transcripts, by July 15.
t13 PARENT (2.6s pause): So we still have to send the tax transcripts, and the deadline is July 15.
t14 COUNSELOR: That's it. To keep the Westbrook Grant he needs SAP, Satisfactory Academic Progress: at least a 2.0 GPA and finishing 67 percent of the credits he attempts, every term.
t15 PARENT: Okay. He's a good student, so a C average shouldn't be a problem. What happens if he drops a class?
t16 COUNSELOR: One dropped class is usually fine, as long as he still completes at least 67 percent of what he attempts that term.
t17 PARENT: Okay, that makes sense.
t18 COUNSELOR: You'll accept or decline each award in the student portal. You'll get an email when it's submitted.
t19 PARENT: Mm-hm.
t20 COUNSELOR: The net price is $23,000, that's the full $38,000 cost minus the $15,000 in grants.
t21 PARENT: Okay, so the $23,000 is what's left before loans and work-study, and the loans we pay back.
t22 COUNSELOR: Exactly. Any other questions for me today?
t23 PARENT: No, I think that's everything. Thank you, Alex.

parent asked: “Wait, is the Parent PLUS loan part of that $31,500?”
t8 answered the question from t7
parent asked: “What happens if he drops a class?”
t16 answered the question from t15
```

</details>

**Run 3: flags 0 (target ≤1) · spoken 0 (target 0) → PASS**

<details><summary>Run 3: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi Maria, it's Alex from financial aid at Westbrook State. Do you have Daniel's award letter handy?
t3 PARENT: I do, it's right here.
t4 COUNSELOR: Great. His total aid package is $31,500. Before you get excited, that's a mix: $15,000 in grants, which are free money, $14,000 in loans, which get paid back, and $2,500 in work-study he earns at a campus job.
t5 PARENT: Okay, so the loans we pay back, and the grants we don't.
t6 COUNSELOR: Exactly right.
t7 PARENT: Wait, is the Parent PLUS loan part of that $31,500?
t8 COUNSELOR: Yes, it is. The Parent PLUS is $8,500 of the $14,000 in loans. It's in your name, it's optional, and it needs its own application and a credit check.
t9 PARENT: Got it, so that one would be mine to repay, and we can say no to it.
t10 COUNSELOR: Right. Your SAI, the Student Aid Index, is a number calculated from your FAFSA. It's not what you'll pay, it's just used to figure out what he qualifies for.
t11 PARENT: Mm-hm, okay.
t12 COUNSELOR: Daniel was also selected for verification. That's not an approval, it just means the school needs more paperwork, like tax return transcripts, by July 15.
t13 PARENT (2.6s pause): So we still have to send the tax transcripts, and the deadline is July 15.
t14 COUNSELOR: That's it. To keep the Westbrook Grant he needs SAP, Satisfactory Academic Progress: at least a 2.0 GPA and finishing 67 percent of the credits he attempts, every term.
t15 PARENT: Okay. He's a good student, so a C average shouldn't be a problem. What happens if he drops a class?
t16 COUNSELOR: One dropped class is usually fine, as long as he still completes at least 67 percent of what he attempts that term.
t17 PARENT: Okay, that makes sense.
t18 COUNSELOR: You'll accept or decline each award in the student portal. You'll get an email when it's submitted.
t19 PARENT: Mm-hm.
t20 COUNSELOR: The net price is $23,000, that's the full $38,000 cost minus the $15,000 in grants.
t21 PARENT: Okay, so the $23,000 is what's left before loans and work-study, and the loans we pay back.
t22 COUNSELOR: Exactly. Any other questions for me today?
t23 PARENT: No, I think that's everything. Thank you, Alex.

parent asked: “Wait, is the Parent PLUS loan part of that $31,500?”
t8 answered the question from t7
parent asked: “What happens if he drops a class?”
t16 answered the question from t15
```

</details>

## live_regressions

| Line | Expected | Run 1 | Run 2 | Run 3 | Passed |
|---|---|---|---|---|---|
| r05 (t6) | MISREAD_TERM → resolved | **none (FAIL)** | MISREAD_TERM → resolved | MISREAD_TERM → resolved | 2/3 |
| r08 (t9) | SUMMON → answered | answered | answered | answered | 3/3 |
| r10 (t12) | SUMMON → answered | answered | answered | answered | 3/3 |

Run 1, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t9 | 18 | yes | L3, L9, L19 | The documents cover Daniel's estimated costs, grants, loans, and work-study. Would you like to know the net price? |
| t12 | 18 | yes | L3, L9, L19 | The documents cover Daniel's estimated costs, grants, loans, and work-study. Would you like to know the net price? |

<details><summary>Run 1: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR (4.2s pause): testing testing
t3 PARENT (5.1s pause): polar
t4 PARENT (3.8s pause): be
t5 COUNSELOR (4.6s pause): Daniel's total aid package is $31,500
t6 PARENT (3.9s pause): Oh, thank goodness, so it's covered
t7 COUNSELOR (4.4s pause): Well, not all of it. $14,000 of that is loans you'd pay back, and $2,500 is work-study he earns at a campus job.
t8 PARENT (3.6s pause): Oh, okay. So the loans get paid back later.
t9 PARENT (4.8s pause): Beacon, what is all the info that you have
t10 BEACON: The documents cover Daniel's estimated costs, grants, loans, and work-study. Would you like to know the net price?
t11 COUNSELOR (4.1s pause): Good question. We can go through any part of the letter you want.
t12 PARENT (5.2s pause): Beacon, can you explain everything on the award letter?
t13 BEACON: The documents cover Daniel's estimated costs, grants, loans, and work-study. Would you like to know the net price?

```

</details>

Run 2, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t9 | 18 | yes | L3, L9, L21, G4 | My documents cover costs, aid offers, requirements, and definitions. Would you like details on the cost of attendance? |
| t12 | 18 | yes | L3, L9, L21 | My documents cover costs, aid offers, and requirements. Would you like to start with the cost of attendance? |

<details><summary>Run 2: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR (4.2s pause): testing testing
t3 PARENT (5.1s pause): polar
t4 PARENT (3.8s pause): be
t5 COUNSELOR (4.6s pause): Daniel's total aid package is $31,500
t6 PARENT (3.9s pause): Oh, thank goodness, so it's covered
t7 COUNSELOR (4.4s pause): Well, not all of it. $14,000 of that is loans you'd pay back, and $2,500 is work-study he earns at a campus job.
t8 PARENT (3.6s pause): Oh, okay. So the loans get paid back later.
t9 PARENT (4.8s pause): Beacon, what is all the info that you have
t10 BEACON: My documents cover costs, aid offers, requirements, and definitions. Would you like details on the cost of attendance?
t11 COUNSELOR (4.1s pause): Good question. We can go through any part of the letter you want.
t12 PARENT (5.2s pause): Beacon, can you explain everything on the award letter?
t13 BEACON: My documents cover costs, aid offers, and requirements. Would you like to start with the cost of attendance?

f1 MISREAD_TERM [total_aid_covers_everything] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
```

</details>

Run 3, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t9 | 23 | yes | L3, L9, L21, L22 | The award letter details Daniel's costs, $31,500 in aid, verification rules, and requirements. Would you like to hear about the cost of attendance? |
| t12 | 22 | yes | L3, L9, L21, L22, L23 | The award letter details costs, $31,500 in aid, verification rules, and requirements. Would you like to hear about the cost of attendance? |

<details><summary>Run 3: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR (4.2s pause): testing testing
t3 PARENT (5.1s pause): polar
t4 PARENT (3.8s pause): be
t5 COUNSELOR (4.6s pause): Daniel's total aid package is $31,500
t6 PARENT (3.9s pause): Oh, thank goodness, so it's covered
t7 COUNSELOR (4.4s pause): Well, not all of it. $14,000 of that is loans you'd pay back, and $2,500 is work-study he earns at a campus job.
t8 PARENT (3.6s pause): Oh, okay. So the loans get paid back later.
t9 PARENT (4.8s pause): Beacon, what is all the info that you have
t10 BEACON: The award letter details Daniel's costs, $31,500 in aid, verification rules, and requirements. Would you like to hear about the cost of attendance?
t11 COUNSELOR (4.1s pause): Good question. We can go through any part of the letter you want.
t12 PARENT (5.2s pause): Beacon, can you explain everything on the award letter?
t13 BEACON: The award letter details costs, $31,500 in aid, verification rules, and requirements. Would you like to hear about the cost of attendance?

f1 MISREAD_TERM [total_aid_covers_everything] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
```

</details>

## summon_checks

| Line | Expected | Run 1 | Run 2 | Run 3 | Passed |
|---|---|---|---|---|---|
| q02 (t3) | SUMMON → answered | answered | answered | answered | 3/3 |
| q03 (t5) | SUMMON → answered | answered | answered | answered | 3/3 |
| q04 (t7) | SUMMON → answered | **none (FAIL)** | **none (FAIL)** | answered | 1/3 |
| q05 (t9) | SUMMON → answered | answered | answered | answered | 3/3 |
| q06 (t11) | SUMMON → answered | answered | answered | answered | 3/3 |
| q07 (t13) | SUMMON → answered | answered | answered | answered | 3/3 |
| q08 (t15) | SUMMON → answered | answered | answered | answered | 3/3 |
| q09 (t17) | SUMMON → answered | answered | answered | answered | 3/3 |
| q10 (t19) | SUMMON → declined | declined | **none (FAIL)** | **none (FAIL)** | 1/3 |
| q11 (t20) | SUMMON → declined | declined | declined | declined | 3/3 |

Run 1, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t3 | 20 | yes | G7, G8 | A subsidized loan does not accrue interest while the student is in school, whereas an unsubsidized loan accrues interest immediately. |
| t5 | 19 | yes | L11 | The Federal Pell Grant is six thousand dollars, which is free money and does not need to be repaid. |
| t8 | 16 | yes | L21 | The verification documents are due by July 15 to ensure aid is not delayed or canceled. |
| t10 | 21 | yes | L14 | No, work-study is earned through a campus job and paid as paychecks, so it is not credited to the bill upfront. |
| t12 | 21 | yes | G2 | The Student Aid Index or SAI is an eligibility number calculated from the FAFSA used by schools to figure out aid. |
| t14 | 15 | yes | L19 | The net price, which is the cost of attendance minus grants, is twenty-three thousand dollars. |
| t16 | 12 | yes | L3 | The cost of attendance is thirty-eight thousand dollars total for the year. |
| t18 | 16 | no | — | The documents do not state the interest rate on the Parent PLUS loan. Please ask Alex. |
| t20 | 15 | no | — | The documents do not state when the first tuition payment is due. Please ask Alex. |

<details><summary>Run 1: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi Maria, it's Alex. I have Daniel's award letter here; ask me or Beacon anything.
t3 PARENT: Beacon, what's the difference between a subsidized and an unsubsidized loan?
t4 BEACON: A subsidized loan does not accrue interest while the student is in school, whereas an unsubsidized loan accrues interest immediately.
t5 PARENT: Beacon, how much is the Pell Grant, and do we pay it back?
t6 BEACON: The Federal Pell Grant is six thousand dollars, which is free money and does not need to be repaid.
t7 PARENT: Beacon, what does SAP mean?
t8 PARENT: Beacon, when are the verification documents due?
t9 BEACON: The verification documents are due by July 15 to ensure aid is not delayed or canceled.
t10 PARENT: Beacon, does work-study come off the bill?
t11 BEACON: No, work-study is earned through a campus job and paid as paychecks, so it is not credited to the bill upfront.
t12 PARENT: Beacon, what is the SAI on the FAFSA?
t13 BEACON: The Student Aid Index or SAI is an eligibility number calculated from the FAFSA used by schools to figure out aid.
t14 PARENT: Beacon, what's the net price?
t15 BEACON: The net price, which is the cost of attendance minus grants, is twenty-three thousand dollars.
t16 PARENT: Beacon, what is the cost of attendance?
t17 BEACON: The cost of attendance is thirty-eight thousand dollars total for the year.
t18 PARENT: Beacon, what's the interest rate on the Parent PLUS loan?
t19 BEACON: The documents do not state the interest rate on the Parent PLUS loan. Please ask Alex.
t20 PARENT: Beacon, when is the first tuition payment due?
t21 BEACON: The documents do not state when the first tuition payment is due. Please ask Alex.

```

</details>

Run 2, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t3 | 20 | yes | G7, G8 | A subsidized loan does not accrue interest while the student is in school, but an unsubsidized loan accrues interest immediately. |
| t5 | 20 | yes | L11 | The Federal Pell Grant is six thousand dollars, and it is free money that does not need to be repaid. |
| t8 | 15 | yes | L21 | Verification documents are due by July 15 to prevent aid from being delayed or canceled. |
| t10 | 14 | yes | L14 | Federal work-study is paid through earnings and is not credited to the bill upfront. |
| t12 | 20 | yes | G2 | The Student Aid Index is an eligibility number calculated from the FAFSA that schools use to figure out aid eligibility. |
| t14 | 15 | yes | L19 | The net price is twenty-three thousand dollars, which is the cost of attendance minus grants. |
| t16 | 12 | yes | L3 | The total cost of attendance is thirty-eight thousand dollars for the year. |
| t19 | 15 | no | — | I don't have information on when the first tuition payment is due. Please ask Alex. |

<details><summary>Run 2: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi Maria, it's Alex. I have Daniel's award letter here; ask me or Beacon anything.
t3 PARENT: Beacon, what's the difference between a subsidized and an unsubsidized loan?
t4 BEACON: A subsidized loan does not accrue interest while the student is in school, but an unsubsidized loan accrues interest immediately.
t5 PARENT: Beacon, how much is the Pell Grant, and do we pay it back?
t6 BEACON: The Federal Pell Grant is six thousand dollars, and it is free money that does not need to be repaid.
t7 PARENT: Beacon, what does SAP mean?
t8 PARENT: Beacon, when are the verification documents due?
t9 BEACON: Verification documents are due by July 15 to prevent aid from being delayed or canceled.
t10 PARENT: Beacon, does work-study come off the bill?
t11 BEACON: Federal work-study is paid through earnings and is not credited to the bill upfront.
t12 PARENT: Beacon, what is the SAI on the FAFSA?
t13 BEACON: The Student Aid Index is an eligibility number calculated from the FAFSA that schools use to figure out aid eligibility.
t14 PARENT: Beacon, what's the net price?
t15 BEACON: The net price is twenty-three thousand dollars, which is the cost of attendance minus grants.
t16 PARENT: Beacon, what is the cost of attendance?
t17 BEACON: The total cost of attendance is thirty-eight thousand dollars for the year.
t18 PARENT: Beacon, what's the interest rate on the Parent PLUS loan?
t19 PARENT: Beacon, when is the first tuition payment due?
t20 BEACON: I don't have information on when the first tuition payment is due. Please ask Alex.

```

</details>

Run 3, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t3 | 20 | yes | G7, G8 | A subsidized loan does not accrue interest while the student is in school, whereas an unsubsidized loan accrues interest immediately. |
| t5 | 18 | yes | L11 | The Federal Pell Grant is $6,000, and it is free money that does not need to be repaid. |
| t7 | 19 | yes | L22, G12 | SAP stands for Satisfactory Academic Progress, requiring at least a 2.0 GPA and completion of 67% of attempted credits. |
| t9 | 15 | yes | L21 | Verification documents are due by July 15 to avoid any delay or cancellation of aid. |
| t11 | 21 | yes | L14 | No, work-study is earned through a campus job and paid as paychecks, so it is not credited to the bill upfront. |
| t13 | 21 | yes | G1, G2 | The SAI, or Student Aid Index, is an eligibility number calculated from your FAFSA that schools use to figure out aid. |
| t15 | 13 | yes | L19 | The net price is $23,000, which is the cost of attendance minus grants. |
| t17 | 17 | yes | L3 | The cost of attendance is thirty-eight thousand dollars, which is the estimated full cost for one year. |
| t20 | 11 | no | — | I don't have that information in the documents. Please ask Alex. |

<details><summary>Run 3: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi Maria, it's Alex. I have Daniel's award letter here; ask me or Beacon anything.
t3 PARENT: Beacon, what's the difference between a subsidized and an unsubsidized loan?
t4 BEACON: A subsidized loan does not accrue interest while the student is in school, whereas an unsubsidized loan accrues interest immediately.
t5 PARENT: Beacon, how much is the Pell Grant, and do we pay it back?
t6 BEACON: The Federal Pell Grant is $6,000, and it is free money that does not need to be repaid.
t7 PARENT: Beacon, what does SAP mean?
t8 BEACON: SAP stands for Satisfactory Academic Progress, requiring at least a 2.0 GPA and completion of 67% of attempted credits.
t9 PARENT: Beacon, when are the verification documents due?
t10 BEACON: Verification documents are due by July 15 to avoid any delay or cancellation of aid.
t11 PARENT: Beacon, does work-study come off the bill?
t12 BEACON: No, work-study is earned through a campus job and paid as paychecks, so it is not credited to the bill upfront.
t13 PARENT: Beacon, what is the SAI on the FAFSA?
t14 BEACON: The SAI, or Student Aid Index, is an eligibility number calculated from your FAFSA that schools use to figure out aid.
t15 PARENT: Beacon, what's the net price?
t16 BEACON: The net price is $23,000, which is the cost of attendance minus grants.
t17 PARENT: Beacon, what is the cost of attendance?
t18 BEACON: The cost of attendance is thirty-eight thousand dollars, which is the estimated full cost for one year.
t19 PARENT: Beacon, what's the interest rate on the Parent PLUS loan?
t20 PARENT: Beacon, when is the first tuition payment due?
t21 BEACON: I don't have that information in the documents. Please ask Alex.

```

</details>

## LLM calls

- Requests: 305 (network: 305, from cache: 0, never sent: 0)
- Analyzer latency over 253 network calls: mean 1460 ms, max 5650 ms
- Summon latency over 38 network calls: mean 929 ms, max 1750 ms
- Errors: 14
  - analysis t3: LLMError: rate limited (429); pausing LLM calls for 20s
  - analysis t16: LLMError: rate limited (429); pausing LLM calls for 20s
  - analysis t9: LLMError: rate limited (429); pausing LLM calls for 20s
  - analysis t6: LLMError: rate limited (429); pausing LLM calls for 20s
  - analysis t7: LLMError: rate limited (429); pausing LLM calls for 20s
  - analysis t8: LLMError: rate limited (429); pausing LLM calls for 20s
  - analysis t8: LLMError: rate limited (429); pausing LLM calls for 20s
  - summon t7: rate limited (429); pausing LLM calls for 20s
  - analysis t14: LLMError: rate limited (429); pausing LLM calls for 20s
  - summon t7: rate limited (429); pausing LLM calls for 20s
  - analysis t7: LLMError: rate limited (429); pausing LLM calls for 20s
  - summon t18: rate limited (429); pausing LLM calls for 20s
  - analysis t9: LLMError: rate limited (429); pausing LLM calls for 20s
  - summon t19: rate limited (429); pausing LLM calls for 20s
