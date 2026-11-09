test steps: 7214 sampled, 7214 scored by every system (5171 calls, 2043 closing messages); 9B unparsed after the rejudge 136; 100 scenarios

| labels | system | off track F1 | false claim F1 | primary | − 9B, F1 points [95% CI] | − Laya frozen [95% CI] |
|---|---|---|---|---|---|---|
| DeepSeek v3 | 9B SLM judge | 0.25 (1142) | 0.25 (91) | 0.246 |  |  |
| DeepSeek v3 | Laya frozen | 0.09 (1142) | 0.06 (91) | 0.076 | -17.0 [-22.0, -11.2] |  |
| DeepSeek v3 | Laya typed (after freeze) | 0.63 (1142) | 0.24 (91) | 0.436 | +19.0 [+12.8, +24.8] | +36.0 [+28.6, +42.5] |
| GLM v3 | 9B SLM judge | 0.25 (1015) | 0.24 (76) | 0.245 |  |  |
| GLM v3 | Laya frozen | 0.10 (1015) | 0.06 (76) | 0.078 | -16.7 [-22.0, -10.4] |  |
| GLM v3 | Laya typed (after freeze) | 0.56 (1015) | 0.19 (76) | 0.376 | +13.1 [+7.7, +18.6] | +29.8 [+23.6, +35.6] |
| both agree | 9B SLM judge | 0.23 (775) | 0.25 (49) | 0.240 |  |  |
| both agree | Laya frozen | 0.08 (775) | 0.04 (49) | 0.063 | -17.7 [-23.7, -10.4] |  |
| both agree | Laya typed (after freeze) | 0.62 (775) | 0.19 (49) | 0.405 | +16.5 [+9.9, +22.8] | +34.2 [+26.7, +41.1] |

Positives in brackets. Proposal bar: Laya ahead of the 9B by at least 9 points with the CI above 0.

| labels | steps | off track positives | 9B F1 | Laya frozen F1 | Laya typed F1 |
|---|---|---|---|---|---|
| DeepSeek v3 | tool calls | 162 | 0.21 | 0.28 | 0.28 |
| DeepSeek v3 | closing messages | 980 | 0.27 | 0.00 | 0.71 |
| GLM v3 | tool calls | 210 | 0.21 | 0.25 | 0.25 |
| GLM v3 | closing messages | 805 | 0.28 | 0.00 | 0.65 |
| both agree | tool calls | 108 | 0.17 | 0.23 | 0.23 |
| both agree | closing messages | 667 | 0.29 | 0.00 | 0.72 |
