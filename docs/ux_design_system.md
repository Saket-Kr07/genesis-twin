# Genesis Twin: UX and design system (Part E)

*Simulation for research and education. Not medical advice.*

## 1. Design principles
1. **Evidence first.** Every number sits next to its source, version or uncertainty.
2. **Calm, not decorative.** Dark neutral surfaces, one accent, status colours used only for status.
3. **Never colour alone.** Status is always colour plus a word (Healthy, Watch, Impaired).
4. **Direct manipulation.** Sliders change the model immediately, nothing needs a Submit button.

## 2. Personas (hypothetical, based on intended users; replace with interview findings)
**Ananya, 23, MSc biology student.** Goal: understand how lifestyle and infection affect organs for a seminar. Pain: textbook diagrams are static. Needs: a 3D body, plain-language labels, a clear "this is a simulation" message.
**Dr. Mehta, 38, computational biologist.** Goal: test whether a new pathogen's time series behaves like a known one. Pain: black-box tools with no uncertainty. Needs: CSV upload, fitted parameters with ranges, citations, exportable records.

## 3. User journeys
| Step | Ananya (public) | Dr. Mehta (pro) |
|---|---|---|
| 1 | Opens Overview, reads the four pillars | Logs in, accepts the consent text |
| 2 | Body explorer: rotates the body, picks Respiratory | Starts the Pro plan (test mode) |
| 3 | Moves smoking and age sliders, watches lung gauge | Pathogen lab: uploads a CSV |
| 4 | Pathogen lab: runs a respiratory virus, drags the day slider | Reads fitted growth, decay, peak with ranges and reliability |
| 5 | Evidence page: opens a source DOI | Compares with a preset, saves the experiment |
| Success | Can explain which organs react first | Has a reproducible record (parameters, seed, model version) |

## 4. Wireframes (low fidelity)
```
Explorer                                         Pathogen lab
+------+---------------------------------+       +------+--------------------------------+
| nav  | top bar: page | role | account  |       | nav  | top bar                        |
|      +------------------+--------------+       |      +-----------+--------------------+
|      |                  | sliders      |       |      | controls  | load chart + peak  |
|      |   3D viewer      | system chips |       |      | pathogen  |                    |
|      |   (sticky)       | organ cards  |       |      | day       | most affected (3)  |
|      |                  | (gauges)     |       |      | treatment +--------------------+
+------+------------------+--------------+       |      |           | all organs (grid)  |
| disclaimer strip, always visible       |       | disclaimer strip                      |
```

## 5. Design tokens (map one-to-one to Figma variables)
Colour: background `#060b17`, surface `rgba(255,255,255,.035)`, border `rgba(255,255,255,.09)`, text `#e7ecf6`, muted `#8d9bb8`, accent `#5eead4`, accent 2 `#8b9cff`, healthy `#34d399`, watch `#fbbf24`, impaired `#f87171`.
Type: Inter (fallback system-ui). Display 44/48 semibold, section 20 semibold, body 14, caption 12. Numbers in a monospace face.
Shape and space: radius 8 (controls), 12 (cards), 14 (plans); spacing scale 4, 8, 12, 16, 24, 28.

## 6. Components
Nav item, top bar chip, button (default, primary), slider with live value, organ card (gauge + status + vitals), system chip, tile, plan card, load chart (axes, peak marker, day cursor), data panel, disclaimer strip.

## 7. Accessibility checklist
- [ ] Text contrast at least 4.5:1 (muted text `#8d9bb8` on `#060b17` is about 6:1)
- [ ] Every control reachable by keyboard, visible focus ring
- [ ] Sliders have text labels and show their value
- [ ] Status never relies on colour alone
- [ ] Respect reduced-motion for the infection animation
- [ ] Layout works at 1280 px and at phone width (sidebar becomes a top block)

## 8. Consent and disclaimer text
Disclaimer (every screen): "Simulation for research and education. Not medical advice. Vitals are model outputs, not measurements."
Consent (registration and uploads): "I understand this platform is for research and education only. I will upload only anonymised data, and I consent to my account data being stored. I can delete my data at any time."

## 9. Usability test (5 to 10 classmates, 15 minutes each)
Tasks: (1) find the heart's score; (2) raise smoking to 20 a day and say what changed; (3) run the respiratory virus to day 10 and name the most affected organ; (4) find the source behind the model version; (5) upload the sample CSV and read the peak day.
Record per task: success (Y/N), time, errors, quote. Finish with the 10-question System Usability Scale. Report the success rate, median time, SUS score and the three biggest fixes.

| Participant | T1 | T2 | T3 | T4 | T5 | SUS | Main problem |
|---|---|---|---|---|---|---|---|
| P1 | | | | | | | |
