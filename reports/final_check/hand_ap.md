# AP@5 worked step by step

Validation user **1026253314001693311**, the minimum-nonzero strict-training viewer from the rebuilt cohort. Method: validation-trained final **007 hybrid**.

## Inputs

True five-ID set (raw-source counts independently checked): **2400508 2400480 240081 400357 10002514**.
Predicted order: **400357 2400467 2400508 2400480 400361**.

A hit means membership anywhere in the true set. Its frequency order is not a required matching rank. Denominator is min(5, five distinct true IDs) = **5**.

| Rank | Predicted ID | Hit? | Hits so far | Precision at this rank | Added AP credit |
|---:|---:|---|---:|---|---|
| 1 | 400357 | yes | 1 | 1 | 1/5 |
| 2 | 2400467 | no | 1 | 1/2 | 0 |
| 3 | 2400508 | yes | 2 | 2/3 | 2/15 |
| 4 | 2400480 | yes | 3 | 3/4 | 3/20 |
| 5 | 400361 | no | 3 | 3/5 | 0 |

## Arithmetic

AP@5 = (1 + 0 + 2/3 + 3/4 + 0) / 5

= (1 + 2/3 + 3/4) / 5

= ((12 + 8 + 9) / 12) / 5

= **29/60 = 0.483333333333**.

Ranks 2 and 5 consume positions but add zero credit. The two later hits receive precision 2/3 and 3/4; they are not each automatically worth 1/5. The evaluator and the scratch per-user CSV independently agree with the worked fraction.

CSV worksheets: hand_ap_ranks.csv and hand_ap_truth.csv. This is assistant-worked arithmetic for the student to inspect; student-personal verification is not claimed.
