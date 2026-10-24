# Off the shelf judges offline on the 9B val steps

1,772 val steps (calls and closing messages) from the Qwen3.5 9B no judge run (release data-2026-10-24), scored with code/offline_eval.py against four label sources: replay oracle, DeepSeek V4.1 Flash, GLM 5.3 Flash and the steps where both agree. Each judge is scored only on the classes it can express. CIs are a bootstrap over the 15 val scenarios. Primary is the mean F1 of off track and false claim, as in the proposal.

| judge | labels | n steps judged | Q1 off_track F1 [CI] (P/R) | Q2 false_claim F1 [CI] (P/R) | Q2 made_up F1 | primary mean F1 [CI] |
|---|---|---|---|---|---|---|
| rules | oracle | 1772 | 0.0426 [0.017, 0.0634] (0.0301/0.0726) | 0.1034 [0.0, 0.2769] (0.375/0.06) | 1.0 | 0.073 [0.0151, 0.1612] |
| rules | deepseek | 1772 | 0.1947 [0.0725, 0.3451] (0.1706/0.2267) | 0.0 [0.0, 0.0] (0.0/0.0) | 0.2979 | 0.0973 [0.0363, 0.1726] |
| rules | glm | 1772 | 0.1741 [0.068, 0.3174] (0.1304/0.2617) | 0.0541 [0.0, 0.1765] (0.125/0.0345) | 0.2632 | 0.1141 [0.0456, 0.1933] |
| rules | both | 1772 | 0.1823 [0.0586, 0.3447] (0.1307/0.3008) | 0.0 [0.0, 0.0] (0.0/0.0) | 0.4 | 0.0911 [0.0293, 0.1723] |
| laya | oracle | 1772 | 0.0293 [0.0103, 0.0456] (0.0268/0.0323) | 0.2 [0.1219, 0.2754] (0.1128/0.88) | 0.0178 | 0.1147 [0.0736, 0.154] |
| laya | deepseek | 1772 | 0.2086 [0.0154, 0.413] (0.2617/0.1733) | 0.2036 [0.1466, 0.2595] (0.1163/0.8182) | 0.0331 | 0.2061 [0.0977, 0.3152] |
| laya | glm | 1772 | 0.1946 [0.0091, 0.372] (0.1946/0.1946) | 0.1256 [0.0857, 0.188] (0.0675/0.8966) | 0.0 | 0.1601 [0.0644, 0.2483] |
| laya | both | 1772 | 0.2031 [0.0, 0.4059] (0.1955/0.2114) | 0.0932 [0.0547, 0.1456] (0.049/0.9444) | 0.0 | 0.1481 [0.0415, 0.2496] |
| kev | oracle | 1772 | 0.112 [0.068, 0.1595] (0.0657/0.379) | 0.1915 [0.0908, 0.28] (0.2045/0.18) | 0.0267 | 0.1518 [0.097, 0.1913] |
| kev | deepseek | 1772 | 0.1555 [0.1222, 0.181] (0.1022/0.3244) | 0.0808 [0.02, 0.1519] (0.0909/0.0727) | 0.0422 | 0.1181 [0.0838, 0.1593] |
| kev | glm | 1772 | 0.1115 [0.086, 0.1359] (0.0674/0.3221) | 0.0278 [0.0, 0.0845] (0.0233/0.0345) | 0.0266 | 0.0696 [0.0462, 0.1038] |
| kev | both | 1772 | 0.0962 [0.0686, 0.1233] (0.057/0.3089) | 0.0345 [0.0, 0.1] (0.025/0.0556) | 0.0146 | 0.0653 [0.0355, 0.1033] |
| lettuce | oracle | 1772 | not expressed | 0.1812 [0.0968, 0.2792] (0.1106/0.5) | n/a | 0.1812 [0.0968, 0.2792] |
| lettuce | deepseek | 1772 | not expressed | 0.2151 [0.1327, 0.2946] (0.1339/0.5455) | n/a | 0.2151 [0.1327, 0.2946] |
| lettuce | glm | 1772 | not expressed | 0.152 [0.0853, 0.236] (0.086/0.6552) | n/a | 0.152 [0.0853, 0.236] |
| lettuce | both | 1772 | not expressed | 0.1284 [0.0727, 0.1928] (0.07/0.7778) | n/a | 0.1284 [0.0727, 0.1928] |

- No judge is reliably ahead: primary F1 sits between 0.07 and 0.21 and every CI overlaps. Val has only 12 to 55 false claim positives, so the test labels are needed for a ranking.
- Laya as is flags false claim on most closing messages (recall 0.82 to 0.94, precision 0.05 to 0.12) and predicts 205 made up values with no hits. Kev made up value F1 is 0.01 to 0.04.
- Rules score made up value F1 1.0 against the oracle only because the oracle uses the same evidence rule; against the annotators it is 0.26 to 0.40.
- Not run yet: Granite Guardian (needs a bigger GPU), Jev on the full set, and the SLM judge and Gemma 4 12B (offline_eval.py --judge llm takes any OpenAI compatible endpoint).
