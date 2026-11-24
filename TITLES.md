# Titles: the system (24 Nov 2026)

How every title on @nnethermind, @vicerat, @talk.nojutsu and @32bitshonen gets written, checked and tested, so it is
the same method every time and it gets better with each batch. Courtney asked for this on 24 Nov: "research titles for
our videos and how we create consistent viral titles for all videos."

One rule sits above all of it: **a title Courtney writes is used character-exact.** This system makes the options he
picks from. It never rewrites his words.

## What this is built on

| Source | What it is | How far to trust it |
|---|---|---|
| 72 breakout videos | vidIQ's outlier search, 24 Nov 2026: long-form anime and manga lore and essay videos from the last year, channels under 150K subscribers, 20K+ views. "Breakout" is views against that channel's usual video. 75 came back; 3 non-English or spam titles were dropped. | Real data from our lane. But it is winners only: there are no flops to compare against, so it shows what breakouts look like, not what causes one. |
| YouTube's own title test | YouTube Help, "A/B test titles & thumbnails" (support.google.com/youtube/answer/16391400) | Read as a search summary only. The page would not open from this session. Confirm in Studio before relying on the details. |
| Title length studies | OverseerOS (about 2,600 videos), vidIQ Research (July 2026), AIR Media Tech | Search summaries only, not opened. Used for one point: no study found agrees on a magic length. |
| Our own videos | `results/log.csv` | Titles are logged but the views and click-through columns are empty. Nothing can be learned from our own results until Muse fills them. |

## What the 72 breakouts show

**They are short.** The 30 that beat their channel by 10 times or more have a median of 41.5 characters and 7.5 words.
27 of those 30 are 60 characters or under. The 18 weakest (under 3 times) average 59 characters.

**They are statements, not questions.** 2 of the 72 end in a question mark. Two of our three long-form essay titles do.

**They rarely shout.** One of the top 30 has three or more words in capitals. Chapter-spoiler titles in capitals with
"!!" and a chapter number sit at the bottom: 1.2 to 2.4 times.

**Label words drag.** "Explained", "Analysis" or "Deep Dive" is in 5 of the top 30 and in 7 of the bottom 18.

### The eight patterns

Each line is a real title from the 72, with how many times it beat its channel's usual video and the channel's size.

| # | Pattern | The shape | Real examples |
|---|---|---|---|
| 1 | **The person, not the show** | The [someone] Who [did the thing that should not be possible]. No series name; the thumbnail carries it. | "The Boxer Who Burned His Tomorrow" 169x (3K subs) · "They Owned Akira Toriyama" 91x (4.3K) · "The Monster Who Only Wants to Talk" 20x (3K) |
| 2 | **The show meets a big idea** | [Series] and [something from real life the viewer already cares about]. | "Chainsaw Man And The Male Loneliness Epidemic" 124x, 753K views (7K) · "One Piece Thinks Cynicism Isn't Maturity" 104x (1.5K) · "Japan's Lovecraft: The Manga Where Gods Are \"Failed Experiments\"" 291x (12K) |
| 3 | **The biggest claim** | [Series] has the greatest / does [thing] better than any other. | "Berserk Has The Greatest Call To Action In All Of Fiction" 100x (2K) · "The GREATEST Tournament Arc in Shonen(That I know of)" 58x (3.2K) · "What Kagurabachi Does Better Than Any Other Shonen" 6.8x (2K) |
| 4 | **Why it works, with a sting** | Why [character] works (and the rest do not) / How [unlikely person] made [series]. | "Why Zoro Works (And Everyone Else Fails)" 25x (1.9K) · "How a Furniture Designer Created Kagurabachi" 7x (26K) |
| 5 | **The hidden reason** | The real / brutal / dark reason [thing fans already wonder about]. | "THE BRUTAL REASON WE NEVER GOT YU YU HAKUSHO'S REAL ENDING" 29x (6K) · "The Dark Reality of HxH." 7.5x (22K) · "The Lore Of Bleach Is Sinister" 4.9x (67K) |
| 6 | **Dare the viewer** | Watch this before / If you like this, you are wrong. | "Watch This Anime Before You Regret It" 68x (2.8K) · "If You Like This Ending, You Are Wrong. (Chainsaw Man)" 3.3x (5.8K) |
| 7 | **The complete guide** | All [number] / the entire [thing] explained. Lower multiples, big steady views, found by search. | "All 17 Anime Studios Explained" 4.6x but 947K views (6.2K) · "The My Hero Academia Iceberg Explained" 2.8x, 259K views (4.5K) |
| 8 | **Lore to sleep to** | [Hours] of [series] lore to help you sleep. | "4 Hours Of One Piece Lore To Help You Sleep" 75x, 149K views (1.5K) · "One Piece 4 Emperors Explained to Fall Asleep to" 5.7x (1.5K) |

Patterns 1 to 3 hold the biggest multiples and almost all come from channels under 10K subscribers, which is where
we are. Pattern 8 matters for the Anime Ambience videos: the lore-to-sleep version beat its channel 75 times over on
1.5K subscribers.

## The rules

1. **Title before script.** Already in `PLAYBOOK.md`. No strong title, no video.
2. **Five options, from at least three different patterns above.** Never five versions of the same sentence.
3. **A statement, 60 characters or under, about 8 words.** The subject the fan knows (the series or the character)
   or the idea they care about is in the first 40 characters.
4. **One promise.** The title says one thing, and the first 30 seconds of the video pays it. If the video cannot pay
   it, the title is wrong, however good it sounds.
5. **Every word true.** "Greatest", "real reason" and "nobody noticed" are claims. They need the same opened source
   as any fact in the script.
6. **No capitals for shouting, no chapter numbers, no label tails** ("| Analysis", "- Explained") on an essay.
   The complete-guide pattern is the one place "Explained" belongs.
7. **His locked rules:** no em dashes, Australian spelling, ordinal-first gears ("2nd Gear"), none of his banned words.
8. **Title and thumbnail are one sentence between them.** The thumbnail text never repeats the title; it adds the
   half the title left out. The thumbnail look itself is locked (`PLAYBOOK.md`).

## The steps, every video

1. Write five options across three or more patterns.
2. Run the gate: `python3 packaging/title_check.py long "option one" "option two" ...` (or `short`). A FAIL is fixed.
   A WARN is fixed or explained.
3. Courtney picks, or writes his own. His pick is final and character-exact.
4. Long-form: put his pick and the two next best into YouTube's title test in Studio (up to three titles; the search
   summary says the winner is chosen by watch time and the test does not run on Shorts). Confirm that on the Studio
   screen the first time.
5. Log it: the title, which pattern number it used, and the test winner, beside the 7-day numbers in
   `results/log.csv`.
6. At each batch review, rank the patterns by our own click-through and views. The best two get most of the next
   batch; the worst is dropped for a batch. That is how it compounds.

## Shorts

- The title test does not run on Shorts, so the first line of the Short does the title's job. The title backs it up.
- Same rules, same gate. A Short that funnels to a long-form uses that long-form's subject in its first words so the
  two read as a pair.
- No tested length rule was found that could be opened. Until our own numbers say otherwise: 60 characters or under.

## Our current titles against this

| Title | Gate | Note |
|---|---|---|
| Who Is Marvel's Sun King? | WARN | A question about a name most viewers do not know. Patterns 1 or 5 would lead with what he did, not his name. |
| Bruce Wayne Isn't the Mask. Neither Is Batman. | PASS | A statement with a sting, 46 characters. This is the shape to repeat. |
| Why Did Luffy Stop Using 2nd Gear? | WARN | The topic is one fans already wonder about. As a statement (pattern 5): "The Real Reason Luffy Stopped Using 2nd Gear" passes at 44 characters. An option for him, not a change. |
| Anime Rain Ambience (two videos) | FAIL | 99 characters and an em dash, which breaks his own rule. Ambience is found by search, so keywords matter, but the dash has to go. Pattern 8 is the stronger idea for this lane. |
| I Waited 13 Years For GTA 6. The Biggest Shock Wasn't Vice City | WARN | 63 characters, 3 over. Strong shape otherwise. |

These are live videos. Changing a live title is Courtney's call and Muse's job; nothing here has been changed.

## Not yet known

- Whether any of this holds on our channels. The log has no numbers yet.
- The exact rules of YouTube's title test (who is eligible, how long it runs). The page would not open.
- Marvel, DC and GTA 6 titles: the 72 are anime and manga. The patterns should carry, but that is a guess until a
  second outlier pull is done for those lanes (vidIQ credits reset on 30 Nov).
