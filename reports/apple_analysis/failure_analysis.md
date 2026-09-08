# Apple baseline failure analysis

Control timing: `output/apple/timing.json`; model `base.en` int8 CPU. 19 lines have partial or missing acoustic token matches; five are below the 0.45 low-confidence threshold.

| Line | Time | Match | Class | Window |
|---|---:|---:|---|---|
| `section_001_line_001` Apple | 0.000–2.312 | 0/1 (0.12) | instrumental gap / intro vocal not recognized | 0.000–13.560 |
| `section_002_line_002` Now you're bitter like apple, oh-oh | 15.480–19.520 | 6/7 (0.73) | partial ASR substitution/deletion | 13.160–27.680 |
| `section_002_line_003` I thought you was my girl, girl, girl | 19.520–21.060 | 0/8 (0.12) | ASR deletion or low vocal SNR | 17.520–27.680 |
| `section_002_line_004` Now you are just an apple, oh-oh | 25.680–25.680 | 2/8 (0.98) | partial ASR substitution/deletion | 17.520–31.980 |
| `section_003_line_001` Nineteen, thought I found my wife | 25.680–27.113 | 0/6 (0.12) | ASR deletion or low vocal SNR | 23.680–31.980 |
| `section_003_line_002` Shorty got a new job, workin' at the Five Guys | 27.113–28.547 | 0/10 (0.12) | ASR deletion or low vocal SNR | 23.680–31.980 |
| `section_003_line_008` Thought she was a saint, but she a sinner | 40.900–42.680 | 8/9 (0.72) | partial ASR substitution/deletion | 38.680–45.180 |
| `section_003_line_009` My good girl turned to a | 43.180–44.280 | 5/6 (0.79) | partial ASR substitution/deletion | 40.680–46.280 |
| `section_004_line_001` How could you be so cold, cold, cold? | 70.820–73.840 | 7/8 (0.73) | partial ASR substitution/deletion | 68.820–75.840 |
| `section_004_line_004` Now you are just an apple, oh-oh | 80.500–83.040 | 7/8 (0.82) | partial ASR substitution/deletion | 78.500–85.880 |
| `section_005_line_002` You turned enemy, got me in disbelief | 86.800–89.300 | 6/7 (0.69) | partial ASR substitution/deletion | 84.800–91.300 |
| `section_006_line_001` She broke my heart | 110.900–112.560 | 0/4 (0.12) | repeated-line / ASR deletion | 108.900–114.560 |
| `section_006_line_002` How could you be so cold? | 112.560–112.560 | 3/6 (0.99) | partial ASR substitution/deletion | 108.900–115.020 |
| `section_006_line_004` How could you be so cold? | 114.520–116.180 | 5/6 (0.71) | partial ASR substitution/deletion | 111.960–118.180 |
| `section_006_line_006` How could you be so cold? | 117.780–119.480 | 5/6 (0.98) | partial ASR substitution/deletion | 115.220–121.580 |
| `section_006_line_008` How could you be so cold? | 121.040–122.820 | 5/6 (0.99) | partial ASR substitution/deletion | 118.600–125.240 |
| `section_006_line_012` Not to mention they don't really look like you | 129.480–131.460 | 7/9 (0.91) | partial ASR substitution/deletion | 126.900–133.880 |
| `section_006_line_015` On some of my old hoes | 135.900–136.840 | 5/6 (0.57) | partial ASR substitution/deletion | 133.240–138.840 |
| `section_006_line_021` But now you got me singing, got me singing | 147.560–165.900 | 8/9 (0.81) | partial ASR substitution/deletion | 145.360–169.632 |

Interpretation: the five zero-match regions are concentrated in the intro, the first chorus/verse transition, and the repeated `She broke my heart` line. Several other lines have high confidence but one missing token, so coverage and confidence must be improved without lowering thresholds. Repeated verse-2 lines already remain chronological in the baseline.
