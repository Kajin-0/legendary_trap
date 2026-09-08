# you_missed_it failure analysis

Only lines with missing or partial direct ASR token support are listed.

| Line | Match | Confidence | Window | Suspected class |
|---|---:|---:|---:|---|
| `section_001_line_001` [(Yeah) | 0/0 | 0.12 | 0.00–7.88 | ASR deletion / low vocal SNR / instrumental gap |
| `section_001_line_002` (Phew, phew) | 0/0 | 0.12 | 0.00–7.88 | ASR deletion / low vocal SNR / instrumental gap |
| `section_001_line_003` (Luh crank) | 0/0 | 0.12 | 0.00–7.88 | ASR deletion / low vocal SNR / instrumental gap |
| `section_001_line_004` (Ding! bell sound) | 0/0 | 0.12 | 0.00–7.88 | ASR deletion / low vocal SNR / instrumental gap |
| `section_001_line_005` (Yeah, yeah, yeah!)] | 0/0 | 0.12 | 0.00–7.88 | ASR deletion / low vocal SNR / instrumental gap |
| `section_002_line_001` Yeah, she blowing up my phone, but I’m riding in a Tonka (skrrt, yeah) | 1/12 | 0.66 | 0.00–15.58 | partial ASR substitution/deletion |
| `section_002_line_002` She had her chance back then, now I'm moving like a monster (phew, phew) | 0/12 | 0.12 | 3.88–15.58 | ASR deletion / low vocal SNR / instrumental gap |
| `section_002_line_003` She want the twizzy now, but the twizzy getting commas (cash, yeah) | 0/10 | 0.12 | 3.88–15.58 | ASR deletion / low vocal SNR / instrumental gap |
| `section_002_line_004` I can't even look her way, I’m avoiding all the drama (nah, nah) | 0/11 | 0.12 | 3.88–15.58 | ASR deletion / low vocal SNR / instrumental gap |
| `section_002_line_005` Yeah, you missed it (yeah), now my wrist is (yeah) | 1/8 | 0.68 | 3.88–31.96 | partial ASR substitution/deletion |
| `section_002_line_006` Flawless, shining, bitch I'm gifted (shining!) | 3/5 | 0.81 | 11.58–33.14 | partial ASR substitution/deletion |
| `section_003_line_003` Big Prada shades, you can't even see (phew) | 6/7 | 0.90 | 41.40–49.00 | partial ASR substitution/deletion |
| `section_003_line_004` She text my phone like "Can you make some time for me?" (No!) | 10/12 | 0.92 | 45.00–52.86 | partial ASR substitution/deletion |
| `section_003_line_005` I just booted up, I’m getting geeked up out my mind (geeked) | 10/11 | 0.95 | 48.26–56.36 | partial ASR substitution/deletion |
| `section_003_line_006` I don't got no time for you, I left you far behind (skrrt) | 11/12 | 0.96 | 51.96–59.82 | partial ASR substitution/deletion |
| `section_003_line_007` Big body truck, yeah the windows got the blinds (Tonka!) | 7/9 | 0.85 | 54.50–62.20 | partial ASR substitution/deletion |
| `section_003_line_008` You thought you was the one, but luh shawty you was blind (yeah!) | 10/12 | 0.91 | 58.20–65.28 | partial ASR substitution/deletion |
| `section_003_line_009` Now she see the diamonds and she see the brand new coupe (coupe) | 11/12 | 0.95 | 61.28–68.50 | partial ASR substitution/deletion |
| `section_003_line_010` Trying to get up in my section, trying to join the troop (nah) | 11/12 | 0.94 | 64.50–72.06 | partial ASR substitution/deletion |
| `section_003_line_012` You can't get a taste, no, you out the loop (phew!) | 7/10 | 0.86 | 70.86–77.72 | partial ASR substitution/deletion |
| `section_004_line_001` Yeah, she blowing up my phone, but I’m riding in a Tonka (skrrt, yeah) | 8/12 | 0.83 | 73.36–80.56 | partial ASR substitution/deletion |
| `section_004_line_002` She had her chance back then, now I'm moving like a monster (phew, phew) | 11/12 | 0.95 | 76.54–83.54 | partial ASR substitution/deletion |
| `section_004_line_004` I can't even look her way, I’m avoiding all the drama (nah, nah) | 9/11 | 0.92 | 82.96–90.90 | partial ASR substitution/deletion |
| `section_004_line_008` But I’m way too far up, my whole life just shifted (up, up!) | 9/11 | 0.92 | 95.66–103.72 | partial ASR substitution/deletion |
| `section_005_line_001` Yeah, she crying in the club, tears falling on the floor (cry) | 10/11 | 0.93 | 98.60–106.50 | partial ASR substitution/deletion |
| `section_005_line_004` Countin' up this paper 'til my fingers getting sore (cash!) | 7/9 | 0.88 | 108.90–116.46 | partial ASR substitution/deletion |
| `section_005_line_005` She remember when she curved me, now she feel the pain (pain) | 10/11 | 0.95 | 111.76–119.56 | partial ASR substitution/deletion |
| `section_005_line_008` Luh twizzy going crazy, I can never be the same (phew, phew) | 9/10 | 0.95 | 121.52–129.48 | partial ASR substitution/deletion |
| `section_006_line_002` She had her chance back then, now I'm moving like a monster (phew, phew) | 10/12 | 0.91 | 128.54–136.02 | partial ASR substitution/deletion |
| `section_006_line_003` She want the twizzy now, but the twizzy getting commas (cash, yeah) | 9/10 | 0.94 | 131.74–138.92 | partial ASR substitution/deletion |
| `section_006_line_004` I can't even look her way, I’m avoiding all the drama (nah, nah) | 10/11 | 0.95 | 134.60–143.12 | partial ASR substitution/deletion |
| `section_006_line_005` Yeah, you missed it (yeah), now my wrist is (yeah) | 7/8 | 0.90 | 138.06–147.16 | partial ASR substitution/deletion |
| `section_006_line_006` Flawless, shining, bitch I'm gifted (shining!) | 4/5 | 0.85 | 142.64–148.54 | partial ASR substitution/deletion |
| `section_006_line_007` She want a piece of me, she say she really miss it (phew) | 11/12 | 0.93 | 144.46–151.80 | partial ASR substitution/deletion |
| `section_006_line_010` (Yeah, you missed it) | 0/0 | 0.12 | 164.08–169.63 | ASR deletion / low vocal SNR / instrumental gap |
| `section_006_line_011` (Luh geek) | 0/0 | 0.12 | 164.08–169.63 | ASR deletion / low vocal SNR / instrumental gap |
| `section_006_line_012` (We way too up) | 0/0 | 0.12 | 164.08–169.63 | ASR deletion / low vocal SNR / instrumental gap |
| `section_006_line_013` (Can't catch me now) | 0/0 | 0.12 | 164.08–169.63 | ASR deletion / low vocal SNR / instrumental gap |
| `section_006_line_014` (bell ringing) | 0/0 | 0.12 | 164.08–169.63 | ASR deletion / low vocal SNR / instrumental gap |
| `section_006_line_015` (Phew, phew) | 0/0 | 0.12 | 164.08–169.63 | ASR deletion / low vocal SNR / instrumental gap |
| `section_006_line_016` (Yeah, we out)] | 0/0 | 0.12 | 164.08–169.63 | ASR deletion / low vocal SNR / instrumental gap |
