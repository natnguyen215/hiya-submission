# Eval results

2026-10-09 00:15 · model `gemini-3.5-flash-lite` · thinking `low` · cache on · 1 run(s) per script

| Script | Result |
|---|---|
| demo_call | 7/7 moments pass in every run; all moments pass in 1/1 runs; 1/1 quiet moments (never spoken) stay quiet in every run |
| demo_call_stt_noise | 7/7 moments pass in every run; all moments pass in 1/1 runs; 1/1 quiet moments (never spoken) stay quiet in every run |
| control_call | flags per run 1 (target ≤1), spoken 0 (target 0) → PASS |
| adversarial_clean | flags per run 0 (target ≤1), spoken 0 (target 0) → PASS |
| live_regressions | 3/3 moments pass in every run; all moments pass in 1/1 runs |
| live_patterns | 7/7 moments pass in every run; all moments pass in 1/1 runs |
| summon_checks | 10/10 moments pass in every run; all moments pass in 1/1 runs |

## demo_call

| Line | Expected | Run 1 | Passed |
|---|---|---|---|
| d04 (t5) | MISREAD_TERM → resolved | MISREAD_TERM → resolved | 1/1 |
| d10 (t11) | MISREAD_TERM → spoken | MISREAD_TERM → spoken | 1/1 |
| d15 (t17) | UNEXPLAINED_JARGON → resolved | UNEXPLAINED_JARGON → resolved | 1/1 |
| d17 (t19) | UNANSWERED_QUESTION → spoken | UNANSWERED_QUESTION → spoken | 1/1 |
| d23 (t27) | no flag → quiet | none | 1/1 |
| d25 (t29) | SUMMON → answered | answered | 1/1 |
| d29 (t34) | no flag → none | none | 1/1 |
| d31 (t36) | no flag → none | none | 1/1 |

Run 1, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t29 | 21 | yes | G9 | A Parent PLUS loan is an optional federal loan borrowed by the parent, requiring a separate application, credit check, and repayment. |

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
t13 BEACON: Quick check for the family: does being selected mean verification is finished or that documents are still needed?
t14 COUNSELOR: Oh, good catch, thank you. Maria, sorry, I went right past that. Verification means the school needs more documents from you, like tax return transcripts and a verification worksheet. They're due July 15, or Daniel's aid could be delayed or canceled.
t15 PARENT: Oh, I had that backwards. So we still owe paperwork, and it's due July 15.
t16 COUNSELOR: Exactly. Now, to keep the Westbrook Grant, Daniel needs to maintain SAP each term.
t17 PARENT (3.0s pause): ...Okay.
t18 COUNSELOR: Sorry, let me explain. SAP is Satisfactory Academic Progress. Each term, Daniel needs at least a 2.0 GPA, about a C average, and has to complete at least 67 percent of the credits he attempts.
t19 PARENT: Got it, a C average, and he finishes 67 percent of the credits he attempts. Um, does the work-study money have to be paid back?
t20 COUNSELOR: So, next step. You'll accept the awards in the student portal, and you can accept or decline each one separately.
t21 COUNSELOR: Once you submit, you'll get an email confirmation.
t22 COUNSELOR: And you can change your mind on any award until the first day of classes.
t23 BEACON: Quick check: Maria asked, “does the work-study money have to be paid back” Could we cover that?
t24 COUNSELOR: Oh, you're right, I skipped your question, Maria. No, work-study isn't paid back. Daniel earns the $2,500 as paychecks from a campus job. It just isn't credited to the bill upfront.
t25 PARENT: Oh, okay. So it's his paycheck, not a loan, but it won't lower the bill upfront.
t26 COUNSELOR: Right. And he qualified for work-study partly because of your SAI, which came from the FAFSA you filed.
t27 PARENT: Oh, he'll be thrilled. He's already talking about working at the campus library. He practically lives there.
t28 COUNSELOR: Ha, I love that. Tell him to apply early, those jobs go fast.
t29 PARENT: Beacon, what's a Parent PLUS loan?
t30 BEACON: A Parent PLUS loan is an optional federal loan borrowed by the parent, requiring a separate application, credit check, and repayment.
t31 COUNSELOR: Yep, that's exactly right. And I'd underline the optional part. You don't have to decide on it today.
t32 PARENT: Okay, good. That's a big one, so I'd like to think it over.
t33 COUNSELOR: Totally fair. So here's the whole picture. The full cost is $38,000. Accepting every piece of aid, including the Parent PLUS loan, covers $31,500, which leaves $6,500 for your family to pay.
t34 PARENT: So even taking every loan and the work-study, we'd still need $6,500 of our own.
t35 COUNSELOR: Right. The letter also lists a net price of $23,000. That's the full cost minus only the grants, the free money.
t36 PARENT: Okay, $38,000 minus the $15,000 in grants. So $23,000 is what we'd cover with loans, work-study, and our own money.
t37 COUNSELOR: So, next steps. Accept or decline each award in the student portal, and send the verification documents by July 15.
t38 PARENT: Got it. Awards in the portal, documents by July 15. Thank you so much, Alex, this really helped.
t39 COUNSELOR: You're so welcome, Maria. And congratulations to Daniel!
t40 PARENT: Thank you! Bye now.

f1 MISREAD_TERM [total_aid_covers_everything] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
parent asked: “So how much is actually free”
t8 answered the question from t7
f2 MISREAD_TERM [verification_selected_means_completed] → nudged: private card for the counselor
f2 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f2 → spoken: Beacon asked aloud
f3 UNEXPLAINED_JARGON [sap_not_explained] → nudged: private card for the counselor
f3 → resolved: the counselor clarified it
parent asked: “does the work-study money have to be paid back”
f4 UNANSWERED_QUESTION [unanswered_t19] → nudged: unanswered after 2 counselor turn(s)
f4 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f4 → spoken: Beacon asked aloud
t24 answered the question from t19
```

</details>

## demo_call_stt_noise

| Line | Expected | Run 1 | Passed |
|---|---|---|---|
| s04 (t5) | MISREAD_TERM → resolved | MISREAD_TERM → resolved | 1/1 |
| s10 (t11) | MISREAD_TERM → spoken | MISREAD_TERM → spoken | 1/1 |
| s15 (t17) | UNEXPLAINED_JARGON → resolved | UNEXPLAINED_JARGON → resolved | 1/1 |
| s17 (t19) | UNANSWERED_QUESTION → spoken | UNANSWERED_QUESTION → spoken | 1/1 |
| s23 (t27) | no flag → quiet | none | 1/1 |
| s25 (t29) | SUMMON → answered | answered | 1/1 |
| s29 (t34) | no flag → none | none | 1/1 |
| s31 (t36) | no flag → none | none | 1/1 |

Run 1, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t29 | 18 | yes | G9 | A Parent PLUS Loan is an optional federal loan borrowed by parents to help cover dependent undergraduate costs. |

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
t13 BEACON: Quick check for the family: what does being selected for verification mean they need to do?
t14 COUNSELOR: oh good catch thank you maria sorry i went right past that verification means the school needs more documents from you like tax return transcripts and a verification worksheet they're due july 15th or daniel's aid could be delayed or canceled
t15 PARENT: oh i had that backwards so we still owe paperwork and it's due july 15th
t16 COUNSELOR: exactly now to keep the west brook grant daniel needs to maintain sap each term
t17 PARENT (3.0s pause): okay
t18 COUNSELOR: sorry let me explain sap is satisfactory academic progress each term daniel needs at least a 2.0 gpa about a sea average and has to complete at least 67% of the credits he attempts
t19 PARENT: got it a sea average and he finishes 67% of the credits he attempts um does the work study money have to be paid back
t20 COUNSELOR: so next step you'll accept the awards in the student portal and you can accept or decline each one separately
t21 COUNSELOR: once you submit you'll get an email confirmation
t22 COUNSELOR: and you can change your mind on any award until the first day of classes
t23 BEACON: Quick check: Maria asked, “does the work study money have to be paid back” Could we cover that?
t24 COUNSELOR: oh you're right i skipped your question maria no work study isn't paid back daniel earns the 2500 as paychecks from a campus job it just isn't credited to the bill up front
t25 PARENT: oh okay so it's his paycheck not a loan but it won't lower the bill up front
t26 COUNSELOR: right and he qualified for work study partly because of your sai which came from the fafsa you filed
t27 PARENT: oh he'll be thrilled he's already talking about working at the campus library he practically lives there
t28 COUNSELOR: ha i love that tell him to apply early those jobs go fast
t29 PARENT: beacon what's a parent plus loan
t30 BEACON: A Parent PLUS Loan is an optional federal loan borrowed by parents to help cover dependent undergraduate costs.
t31 COUNSELOR: yep that's exactly right and i'd underline the optional part you don't have to decide on it today
t32 PARENT: okay good that's a big one so i'd like to think it over
t33 COUNSELOR: totally fair so here's the whole picture the full cost is $38,000 accepting every piece of aid including the parent plus loan covers $31,500 which leaves 6500 for your family to pay
t34 PARENT: so even taking every loan and the work study we'd still need 6500 of our own
t35 COUNSELOR: right the letter also lists a net price of 23,000 that's the full cost minus only the grants the free money
t36 PARENT: okay 38,000 minus the 15,000 in grants so 23,000 is what we'd cover with loans work study and our own money
t37 COUNSELOR: so next steps accept or decline each award in the student portal and send the verification documents by july 15th
t38 PARENT: got it awards in the portal documents by july 15th thank you so much alex this really helped
t39 COUNSELOR: you're so welcome maria and congratulations to daniel
t40 PARENT: thank you bye now

f1 MISREAD_TERM [total_aid_package_covers_everything] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
parent asked: “so how much is actually free”
t8 answered the question from t7
f2 MISREAD_TERM [verification_means_approval] → nudged: private card for the counselor
ignored [verification_means_done]: same MISREAD_TERM moment as f2 (same parent turn)
f2 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f2 → spoken: Beacon asked aloud
f3 UNEXPLAINED_JARGON [sap_not_explained] → nudged: private card for the counselor
f3 → resolved: the counselor clarified it
ignored [sap_not_explained_relapse]: same UNEXPLAINED_JARGON moment as f3 (same parent turn)
parent asked: “does the work study money have to be paid back”
f4 UNANSWERED_QUESTION [unanswered_t19] → nudged: unanswered after 2 counselor turn(s)
f4 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f4 → spoken: Beacon asked aloud
t24 answered the question from t19
```

</details>

## control_call

**Run 1: flags 1 (target ≤1) · spoken 0 (target 0) → PASS**

Run 1, flags not matched to a planted moment:

- f1 UNANSWERED_QUESTION `unanswered_t13` → resolved, evidence ['t13']

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
f1 UNANSWERED_QUESTION [unanswered_t13] → nudged: unanswered after 2 counselor turn(s)
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
t20 COUNSELOR: And for the tax transcripts, you'll get an email with the link.
t21 PARENT (2.6s pause): Okay.
t22 COUNSELOR: The net price is $23,000, that's the full $38,000 cost minus the $15,000 in grants.
t23 PARENT: Okay, so the $23,000 is what's left before loans and work-study, and the loans we pay back.
t24 COUNSELOR: Exactly. Any other questions for me today?
t25 PARENT: No, I think that's everything. Thank you, Alex.

parent asked: “is the Parent PLUS loan part of that $31,500”
t8 answered the question from t7
parent asked: “What happens if he drops a class”
t16 answered the question from t15
```

</details>

## live_regressions

| Line | Expected | Run 1 | Passed |
|---|---|---|---|
| r05 (t6) | MISREAD_TERM → resolved | MISREAD_TERM → resolved | 1/1 |
| r08 (t9) | SUMMON → answered | answered | 1/1 |
| r10 (t12) | SUMMON → answered | answered | 1/1 |

Run 1, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t9 | 19 | yes | L3, L9, L21, G4 | The documents list costs, grants, loans, work-study, requirements, and definitions. Would you like to know the cost of attendance? |
| t12 | 18 | yes | L3, L9, L16, L17, L18, L21, L22, L23 | The documents list costs, grants, loans, work-study, and requirements. Would you like to know the cost of attendance? |

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
t10 BEACON: The documents list costs, grants, loans, work-study, requirements, and definitions. Would you like to know the cost of attendance?
t11 COUNSELOR (4.1s pause): Good question. We can go through any part of the letter you want.
t12 PARENT (5.2s pause): Beacon, can you explain everything on the award letter?
t13 BEACON: The documents list costs, grants, loans, work-study, and requirements. Would you like to know the cost of attendance?

f1 MISREAD_TERM [total_aid_means_fully_covered] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
```

</details>

## live_patterns

| Line | Expected | Run 1 | Passed |
|---|---|---|---|
| l04 (t5) | MISREAD_TERM → resolved | MISREAD_TERM → resolved | 1/1 |
| l07 (t8) | MISREAD_TERM → nudged or spoken | MISREAD_TERM → spoken | 1/1 |
| l12 (t14) | MISREAD_TERM → spoken | MISREAD_TERM → spoken | 1/1 |
| l22 (t25) | MISREAD_TERM → spoken | MISREAD_TERM → spoken | 1/1 |
| l23 (t26) | MISREAD_TERM → quiet (a flag must exist) | MISREAD_TERM → resolved | 1/1 |
| l29 (t33) | no flag → none | none | 1/1 |
| l34 (t38) | no flag → none | none | 1/1 |

<details><summary>Run 1: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi Maria, it's Alex at Westbrook State again. Let's finish the loan part of Daniel's letter.
t3 PARENT: Sure, I've got the letter open.
t4 COUNSELOR: Daniel's Federal Direct Unsubsidized Loan is $2,000.
t5 PARENT: Oh good, so that one won't grow at all while he's still in school.
t6 COUNSELOR: Actually, it's the other way around. Interest on the unsubsidized loan starts adding up right away, even during school. Only the subsidized one has its interest covered while he's enrolled.
t7 COUNSELOR: So do you want to keep both loans, or only the subsidized one?
t8 PARENT: Both, I think. Neither of them grows until he graduates, so there's no hurry.
t9 COUNSELOR: Okay. Next on the letter is the work-study award.
t10 BEACON: Quick check for the family: does interest start on the unsubsidized loan while he's in school?
t11 COUNSELOR: Thanks for flagging that. Maria, the unsubsidized loan does grow while Daniel is in school, because its interest starts as soon as the money goes out.
t12 PARENT: Oh, okay. So only the subsidized one waits until after school. Got it now.
t13 COUNSELOR: Right. So, Daniel's Federal Work-Study award is $2,500 for the year.
t14 PARENT: That's great, so that $2,500 comes off the tuition bill right away.
t15 PARENT: Oh,
t16 PARENT: that helps a lot,
t17 PARENT: honestly.
t18 COUNSELOR: Great. Moving on, the Westbrook Grant is $9,000 for the year.
t19 BEACON: Quick check for the family: does the work-study amount come off the bill upfront or get paid in paychecks?
t20 COUNSELOR: Good question, thank you. Maria, work-study isn't taken off the bill. Daniel earns it as paychecks from a campus job, for the hours he works.
t21 PARENT: Oh, so it's his paycheck as he works. We still pay the bill ourselves.
t22 COUNSELOR: Exactly. To keep the Westbrook Grant, Daniel needs Satisfactory Academic Progress: at least a 2.0 GPA and finishing 67 percent of the credits he attempts, every term.
t23 PARENT: Okay, so a C average, and he has to finish most of his classes each term.
t24 COUNSELOR: That's it. Now, the Parent PLUS loan on the letter is $8,500, offered to you. And the net price is $23,000.
t25 PARENT: Oh nice, so Daniel pays that loan back once he's working.
t26 PARENT: And the $23,000 is what's left after the loans come off.
t27 COUNSELOR: Last thing on the money: accept each award in the student portal.
t28 BEACON: Quick check for the family: who is responsible for repaying the Parent PLUS loan?
t29 COUNSELOR: Right, that loan is yours to repay, Maria.
t30 COUNSELOR: And one correction: the net price only takes off the grants. The loans still count toward it.
t31 PARENT: Oh, I see. So the $23,000 is before any loans.
t32 COUNSELOR: Exactly. Do you have any other questions about the letter?
t33 PARENT: Yes, when do the verification papers have to be in?
t34 PARENT: Oh never mind, I see it on the letter. July 15.
t35 COUNSELOR: Perfect. The transcripts and the worksheet both go to our office.
t36 COUNSELOR: We'll review them within a couple of weeks.
t37 COUNSELOR: You'll get an email with the link.
t38 PARENT (2.6s pause): Okay.
t39 COUNSELOR: That's everything for today. Congratulations again to Daniel.
t40 PARENT: Thank you, Alex. Bye now.

f1 MISREAD_TERM [unsubsidized_loan_interest_accrues_in_school] → nudged: private card for the counselor
f1 → resolved: the counselor clarified it
f2 MISREAD_TERM [neither_loan_grows_until_graduation] → nudged: private card for the counselor
ignored [neither_loan_grows_until_graduation_relapse]: same MISREAD_TERM moment as f2 (same parent turn)
f2 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f2 → spoken: Beacon asked aloud
f3 MISREAD_TERM [work_study_deducted_from_bill_upfront] → nudged: private card for the counselor
ignored resolution of f3: no counselor turn after its evidence
ignored [work_study_deducted_from_bill_upfront_relapse]: same MISREAD_TERM moment as f3 (same parent turn)
ignored resolution of f3: no counselor turn after its evidence
ignored [work_study_deducted_from_bill_upfront_relapse]: same MISREAD_TERM moment as f3 (same parent turn)
f3 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f3 → spoken: Beacon asked aloud
f4 MISREAD_TERM [parent_plus_loan_repaid_by_student] → nudged: private card for the counselor
ignored resolution of f4: no counselor turn after its evidence
ignored [parent_plus_loan_repaid_by_student_relapse]: same MISREAD_TERM moment as f4 (same parent turn)
f5 MISREAD_TERM [net_price_includes_loans_subtracted] → nudged: private card for the counselor
f4 escalates: not clarified after 1 counselor turn(s); speaking at the next pause
f4 → spoken: Beacon asked aloud
f5 due, waiting: one interjection at a time
f5 due, waiting: cooldown 16s left
f5 → resolved: the counselor clarified it
parent asked: “when do the verification papers have to be in”
t34 withdrew the question from t33
```

</details>

## summon_checks

| Line | Expected | Run 1 | Passed |
|---|---|---|---|
| q02 (t3) | SUMMON → answered | answered | 1/1 |
| q03 (t5) | SUMMON → answered | answered | 1/1 |
| q04 (t7) | SUMMON → answered | answered | 1/1 |
| q05 (t9) | SUMMON → answered | answered | 1/1 |
| q06 (t11) | SUMMON → answered | answered | 1/1 |
| q07 (t13) | SUMMON → answered | answered | 1/1 |
| q08 (t15) | SUMMON → answered | answered | 1/1 |
| q09 (t17) | SUMMON → answered | answered | 1/1 |
| q10 (t19) | SUMMON → declined | declined | 1/1 |
| q11 (t21) | SUMMON → declined | declined | 1/1 |

Run 1, summon answers:

| Turn | Words | From documents | Refs | Answer |
|---|---|---|---|---|
| t3 | 17 | yes | G7, G8 | A subsidized loan does not accrue interest while in school, but an unsubsidized loan accrues interest immediately. |
| t5 | 19 | yes | L11 | The Federal Pell Grant is six thousand dollars. It is free money and does not need to be repaid. |
| t7 | 20 | yes | L22, G12 | SAP means Satisfactory Academic Progress, requiring at least a two point zero GPA and completion of sixty-seven percent of credits. |
| t9 | 8 | yes | L21 | The verification documents are due by July fifteenth. |
| t11 | 21 | yes | L14 | No, work-study is earned through a campus job and paid as paychecks, so it is not credited to the bill upfront. |
| t13 | 21 | yes | G2 | The SAI, or Student Aid Index, is an eligibility number calculated from the FAFSA used by schools to figure out aid. |
| t15 | 15 | yes | L19 | The net price is twenty-three thousand dollars, which is the cost of attendance minus grants. |
| t17 | 17 | yes | L3 | The cost of attendance is thirty-eight thousand dollars, which is the estimated full cost of one year. |
| t19 | 18 | no | — | I do not have the interest rate for the Parent PLUS loan in my documents. Please ask Alex. |
| t21 | 18 | no | — | I do not have the due date for the first tuition payment in my documents. Please ask Alex. |

<details><summary>Run 1: transcript and decisions</summary>

```
t1 BEACON: Hi, I'm Beacon, an AI assistant listening to help keep things clear. Ask me about anything on the award letter: just start with my name.
t2 COUNSELOR: Hi Maria, it's Alex. I have Daniel's award letter here; ask me or Beacon anything.
t3 PARENT: Beacon, what's the difference between a subsidized and an unsubsidized loan?
t4 BEACON: A subsidized loan does not accrue interest while in school, but an unsubsidized loan accrues interest immediately.
t5 PARENT: Beacon, how much is the Pell Grant, and do we pay it back?
t6 BEACON: The Federal Pell Grant is six thousand dollars. It is free money and does not need to be repaid.
t7 PARENT: Beacon, what does SAP mean?
t8 BEACON: SAP means Satisfactory Academic Progress, requiring at least a two point zero GPA and completion of sixty-seven percent of credits.
t9 PARENT: Beacon, when are the verification documents due?
t10 BEACON: The verification documents are due by July fifteenth.
t11 PARENT: Beacon, does work-study come off the bill?
t12 BEACON: No, work-study is earned through a campus job and paid as paychecks, so it is not credited to the bill upfront.
t13 PARENT: Beacon, what is the SAI on the FAFSA?
t14 BEACON: The SAI, or Student Aid Index, is an eligibility number calculated from the FAFSA used by schools to figure out aid.
t15 PARENT: Beacon, what's the net price?
t16 BEACON: The net price is twenty-three thousand dollars, which is the cost of attendance minus grants.
t17 PARENT: Beacon, what is the cost of attendance?
t18 BEACON: The cost of attendance is thirty-eight thousand dollars, which is the estimated full cost of one year.
t19 PARENT: Beacon, what's the interest rate on the Parent PLUS loan?
t20 BEACON: I do not have the interest rate for the Parent PLUS loan in my documents. Please ask Alex.
t21 PARENT: Beacon, when is the first tuition payment due?
t22 BEACON: I do not have the due date for the first tuition payment in my documents. Please ask Alex.

```

</details>

## LLM calls

- Requests: 129 (network: 15, from cache: 114, never sent: 0)
- Analyzer latency over 15 network calls: mean 1376 ms, max 2396 ms
- Summon latency: no network calls
- Errors: 0
