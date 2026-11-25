# Why the views dropped, and the test to find out (25 Nov 2026)

Courtney, 25 Nov: "muse is now making the videos and the views aren't anywhere near as high compare to when you were
making. Are you able to see what the difference, why they have dropped off?? I just don't understand??"
Then: "So yeah let's test. Put everything mentioned in repo and see what muse can do??"

## What the data is

`results/titles-current.csv`: all 44 public videos on @nnethermind with lifetime views, pulled by Muse from the Data
API on 25 Nov. The handover date is assumed to be about 21 Nov, where the studio records change style. Muse: correct
that date here if it is wrong.

## What it shows

| Group | Videos | Median views | Range |
|---|---|---|---|
| Shorts, 20 Sep to 19 Nov | 26 | 1,585 | 8 to 11,882 |
| Shorts, 21 to 22 Nov | 4 | 1,133 | 1,079 to 1,305 |
| Shorts, 24 Nov (one day old when pulled) | 5 | 231 | 2 to 444 |
| Long-form, all | 9 | 5 | 1 to 830 |

1. The 24 Nov Shorts had about a day to collect views. They cannot be compared with older videos yet.
2. The 21 to 22 Nov Shorts sit about 30% under the older median. Four videos; could be noise.
3. Seven of the 14 uploads since 21 Nov are long-form, and five of those have 5 views or fewer. Long-form gets no feed
   push on a 55-subscriber channel. This mix is the largest part of the drop.
4. About 57,000 of the 59,000 views on the public videos came from Shorts.

## What changed in the Shorts (from titles and records only; the videos were not watched)

| | Before 21 Nov | From 21 Nov |
|---|---|---|
| The idea | One surprising fact, stated plainly | A clever line or an opinion |
| On screen | A big question in capitals ("WAS HULK GREY FIRST?") | Not recorded |
| Title | "Jujutsu Kaisen Was Supposed to End in 2023" (11,882) | "Benimaru Doesn't Have Rivals. He Has Witnesses." (1,079) |
| Range | Marvel, DC, anime, gaming | Narrower: Fire Force, Bleach, One Piece |
| Job | Stand alone | Several cut to funnel to a long-form |
| Voice | The old factory voice | Courtney's cloned voice |
| Posting | About one a day | Four on 24 Nov |

Working guess, not proven: the plain surprising-fact Short was what worked, and the plan moved off it to chase
long-form watch hours.

## What nobody has looked at yet

Whether viewers swipe away sooner, or YouTube shows the Shorts to fewer people. Only Studio has it; the Analytics API
is off for the project.

## Job 1 for Muse: read six Shorts in Studio

Three from before 21 Nov and three from after, picked from the middle of each group (not the best or the worst).
For each, off the Studio screen: shown in feed, viewed vs swiped away %, average % viewed, views in the first 48
hours if Studio shows it, subscribers gained. Put them in a table at the bottom of this file. A cell Studio does not
show stays blank.

## Job 2: the test

Six Shorts over six days, one a day at the same hour, alternating.

- **Style A, the old way (three Shorts):** one surprising fact from an opened source, stated plainly. A big question
  in capitals on screen in the first second. 30 to 45 seconds. Stands alone, no pointer to a long-form. Broad
  subjects: one Marvel or DC, one big anime, one gaming.
- **Style B, the current way (three Shorts):** as Muse makes them now.
- **Held the same in both:** Courtney's cloned voice (his rule), length within 10 seconds of each other, the
  thumbnail template, the posting hour, three hashtags, titles through `packaging/title_check.py`. Subjects of
  similar size (do not put Naruto against an obscure series).
- **Read at 48 hours after each goes public:** views, shown in feed, viewed vs swiped away %, average % viewed,
  subscribers gained. Log each as a row in `results/log.csv`, with `series` set to `test-A` or `test-B`.
- **Call it:** if one style's median views are at least 30% higher and its swipe-away number is better too, that
  style becomes the daily Short. If they are close, the style was not the problem and the Studio numbers from Job 1
  decide what to look at next. Six videos is a small test: it can show a big difference, not a small one.
- All the standing gates apply: storyboard approved by Courtney, Private upload, he publishes.

## Meanwhile

Keep one fact Short a day going in the old style while long-form builds, so views do not dry up during the test.
That is Courtney's call to confirm; it is proposed here, not decided.

## Studio readings (Muse fills this in)

| video_id | group | shown in feed | viewed vs swiped % | avg % viewed | 48h views | subs gained |
|---|---|---|---|---|---|---|
