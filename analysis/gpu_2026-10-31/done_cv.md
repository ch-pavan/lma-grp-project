| fold | held-out rows | not done | own best threshold | F1 there |
|---|---|---|---|---|
| fold0 | 679 | 112 | 0.169 | 0.520 |
| fold1 | 690 | 145 | 0.316 | 0.616 |
| fold2 | 700 | 138 | 0.469 | 0.555 |
| fold3 | 630 | 109 | 0.411 | 0.518 |
| fold4 | 642 | 118 | 0.871 | 0.590 |

Pooled out-of-fold scores: 3341 train turn ends, 622 not done. Best threshold 0.561 (out-of-fold F1 0.538).

| threshold on validation (495 turn ends) | how chosen | precision | recall | F1 |
|---|---|---|---|---|
| 0.561 | out-of-fold on train (this item) | 0.553 | 0.514 | 0.533 |
| 0.500 | default, as in the live runs | 0.537 | 0.523 | 0.530 |
| 0.984 | dev split of 8 scenarios (job 49265) | 0.926 | 0.225 | 0.362 |
