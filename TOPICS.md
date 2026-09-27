# Topic backlog

The queue the pipeline pulls from. Each line is a video: the hook, the format, and where to verify it. **Nothing here is pre-verified** — the source column is where to check, not proof. Verify before scripting; that step is the channel's whole defence.

Formats: `fact` = narrated story · `creature` = animal reveal · `iceberg` = long-form iceberg essay (never a Short)

## Space — assets are public domain, easiest to produce

| Hook | Format | Verify at |
|---|---|---|
| NASA turned the centre of the galaxy into music | fact | chandra.si.edu sonifications |
| The Voyager probes are still sending data from interstellar space | fact | voyager.jpl.nasa.gov |
| There's a cloud in space made of alcohol | fact | ESO — Sagittarius B2 |
| The Wow! signal: 72 seconds we still can't explain | fact | Ohio State / Big Ear archives |
| Betelgeuse could already have exploded | fact | NASA/ESA — check the distance/lag claim carefully |
| The Pillars of Creation may no longer exist | fact | Hubble/Webb — this claim is contested, say so |
| A planet made of diamond | fact | NASA — 55 Cancri e, heavily overstated in press |
| The coldest place in the universe is man-made | fact | NIST / Cold Atom Lab on ISS |
| It rains diamonds on Neptune | fact | Lab study, Kraus et al. — inferred, not observed |

## Iceberg — the long-form template: any topic, 5 tiers of obscurity

The proven video-essay format: Tier 1 is what everyone knows, Tier 5 is what almost nobody does. Works for any subject in the channel's lanes — pick an iceberg here or type any topic under Make → Iceberg. Each tier is verified entry by entry.

| Hook | Format | Verify at |
|---|---|---|
| The Marvel Iceberg | iceberg | Marvel publishing history, creator interviews |
| The X-Men Iceberg | iceberg | Comic issues + Claremont/Lee interviews |
| The Spider-Man Iceberg | iceberg | Issue history, Sony/Marvel deal reporting |
| The Dragon Ball Iceberg | iceberg | Toriyama interviews, Shueisha / Toei records |
| The Pokémon Iceberg | iceberg | Game Freak / Nintendo interviews, Iwata Asks |
| The Studio Ghibli Iceberg | iceberg | Miyazaki/Suzuki interviews, Ghibli books |
| The Nintendo Iceberg | iceberg | Iwata Asks, company history |
| The Cancelled Video Games Iceberg | iceberg | Developer interviews, not fan wikis |
| The Real-Life Superpowers Iceberg | iceberg | Peer-reviewed biology — animals with comic-book powers |

## Creatures — NOAA and Smithsonian imagery is public domain

| Hook | Format | Verify at |
|---|---|---|
| This jellyfish can reset its own age | creature | Turritopsis dohrnii — "immortal" is badly overstated |
| A fish with a transparent head | creature | MBARI — barreleye |
| The bird that sleeps while flying | creature | Rattenborg et al. — frigatebirds |
| This octopus guarded her eggs for 4½ years | creature | MBARI — Graneledone boreopacifica |
| The animal that survives being frozen solid | creature | Wood frog — cryobiology literature |
| A parasite that replaces a fish's tongue | creature | Cymothoa exigua — museum sources |
| Tardigrades survived the vacuum of space | creature | Jönsson et al. 2008, Current Biology (FOTON-M3 mission) |
| The peregrine falcon dives faster than a Formula 1 car | creature | Published dive-speed measurements — check the exact figure and method |

## Marvel / Hero — original AI art only, real comic/production history

| Hook | Format | Verify at |
|---|---|---|
| Spider-Man almost didn't happen — publishers thought teens could only be sidekicks | hero | Stan Lee interviews, Amazing Fantasy #15 publication history |
| The raspy "Batman voice" isn't from the comics — one actor invented it for a cartoon | hero | Kevin Conroy interviews, Batman: The Animated Series production history |
| Mystique's shapeshifting is real — the mimic octopus impersonates other animals | hero | Norman, Finn & Tregenza 2001, Proc. R. Soc. B (mimic octopus) |
| Electro's power is real — the electric eel's record 860-volt shock | hero | de Santana et al. 2019, Nature Communications (Volta's electric eel) |
| Iceman's power is real — the wood frog freezes solid and thaws back to life | hero | Storey & Storey cryobiology papers, Carleton University |
| Daredevil's radar sense is real — blind people who see with echoes | hero | Thaler, Arnott & Goodale 2011, PLoS ONE (human echolocation) |
| Spider-Man's webs vs real spider silk — tougher than steel by weight | hero | Darwin's bark spider silk, Agnarsson et al. 2010, PLoS ONE |

## Gaming — needs your own footage

| Hook | Format | Verify at |
|---|---|---|
| The Halo ring would kill everyone standing on it | fact | Physics of the design; needs 20s of your footage |
| Dead Space's Marker is closer to real science than you think | fact | Developer commentary |
| The Mass Effect relays break one specific law of physics | fact | Codex + real physics |
| A speedrun trick that took 15 years to find | fact | Speedrun.com history, developer confirmation |
| The Lost Marvel Games Iceberg — cancelled Marvel video games | ice | Developer interviews and publisher announcements, not fan wikis |
| Pac-Man was nearly called Puck-Man — renamed so vandals couldn't change one letter on arcade cabinets | hero | Namco history, Toru Iwatani interviews |
| Mario is named after Nintendo of America's warehouse landlord | hero | Nintendo of America history, Mario Segale obituaries (2018) |
| Minecraft's Creeper was a broken pig model | hero | Notch's own posts/interviews — dimensions typed the wrong way round |
| Tails' real name, Miles Prower, is a pun on "miles per hour" | hero | Sega / Sonic Team history |

## Anime — original AI art only, real production history

Same rules as Marvel: no official art, stills or clips — Gemini art by archetype, pose and palette, never a named character or exact design. Same "comic power that's real biology" angle works here.

| Hook | Format | Verify at |
|---|---|---|
| The Kamehameha is named after a Hawaiian king — Toriyama's wife picked it | hero | Akira Toriyama interviews (Dragon Ball guidebooks) |
| One Pokémon episode sent hundreds of kids in Japan to hospital | hero | Dec 1997 "Dennō Senshi Porygon" — news reports, the ~685 figure varies by source, say so |
| Pokémon exists because its creator collected bugs as a kid | hero | Satoshi Tajiri interviews |
| Studio Ghibli is named after a WWII Italian plane — and they mispronounce it | hero | Ghibli's own history; Caproni Ca.309 "Ghibli", the Saharan wind |
| Titans from Attack on Titan couldn't stand up — the square-cube law | fact | Real physics (Galileo's square-cube law); no show footage, AI art only |
| The beetle that fires boiling chemicals — anime fire-types are real biology | creature | Bombardier beetle — Eisner, Aneshansley et al.; PD insect photos on Commons |

## Nerdosphere mix — keep Marvel the lead lane

Marvel/comics averages ~1,400 YouTube views per Short vs ~800 for space/ocean (Buffer, 8–24 Sep 2026). Suggested weekly mix while that holds: **3 Marvel/comics · 1 anime · 1 gaming · 1 science-crossover** ("the power that's real biology"). Re-check the split against `stats.py` monthly — move slots toward whatever lane wins.

## Long-form — weekly episode ideas (Idea Farm, scored /60, imported 2026-09-27)

One weekly ~15–25 min episode Courtney voices herself, cut into 3 Shorts after. Format `long` here always means
this weekly slot, never the daily Shorts above. Score = audience-fit + pillar-fit + fandom-depth fit + depth +
specificity + evergreen value, each 0–10. Source column keeps the idea's status/note from the Idea Farm backlog.

| Hook | Format | Verify at |
|---|---|---|
| What Happens When a Whale Dies Two Miles Down | long | 55/60 · made (EP01, episodes/ep_whale_fall_two_miles_down.json) · own-Short (bone worm) + API-90d |
| The Star That Keeps Dimming and Nobody Knows Why | long | 53/60 · ready · own-Short (Boyajian) + comment ("OH HELL NO!") |
| Marvel's Biggest Hero Started Out Grey | long | 52/60 · ready · own-Short (Hulk, top video) |
| The Video Game America Buried in the Desert | long | 52/60 · ready · evergreen (Atari landfill) |
| Scientists Still Can't Agree What This Fossil Is | long | 50/60 · ready · API-90d (Tully monster) |
| 72 Seconds in 1977 Nobody Has Explained | long | 50/60 · ready · evergreen (Wow! signal) |
| The Anime That Ran Out of Money Before Its Ending | long | 49/60 · ready · evergreen (Evangelion) |
| Marvel Almost Never Existed | long | 48/60 · needs verification (the Hindenburg claim) · own-Short (rendered, unpublished) |
| Nintendo Tried Taxis and Love Hotels First | long | 48/60 · ready (verify the love-hotel claim) · evergreen |
| The Object That Came From Another Star and Left | long | 48/60 · ready · evergreen (ʻOumuamua) |
| The Voice in Rudeus's Dreams Was Lying | long | 47/60 · ready (spoiler warning in cold open) · API-90d (Mushoku Tensei) + July-plan |
| The Hero Who Beat Doctor Doom in Her First Comic | long | 47/60 · ready · API-90d (Squirrel Girl vs Dr Doom origin) |
| The Real Falcon Punch Lives Underwater | long | 45/60 · ready (incl. the "super colour vision" myth-bust) · comment + own-Short (mantis shrimp) |
| Ichigo Was Never Just a Soul Reaper | long | 44/60 · ready · API-90d (Bleach) + July-plan |
| What If You Fell Into the Mariana Trench | long | 43/60 · ready · evergreen (pillar demand not measured) |
| Strange True Facts to Fall Asleep To | long | 42/60 · parked (long compilations come at Month 4+) · API-90d |
| What Would Actually Happen If the Moon Vanished | long | 41/60 · ready · evergreen |
| What a Real Gamma Dose Would Do to You | long | 40/60 · ready · own-Short (Hulk) cross-pillar |
| The Animal That Survived Open Space | long | 39/60 · ready (crowded topic: needs a fresh angle) · evergreen (tardigrades) |
| Things Invented by Accident That Run Your Life | long | 33/60 · weak (list format: lists don't retain; recast or kill) · evergreen |
| GTA 6's Story, Before It Even Releases | long | 32/60 · parked (clip-heavy, clashes with Format Spec v2 §9; verify release date) · July-plan |

## Intelligence picks — topics you said "make it" to in Studio

| Hook | Format | Verify at |
|---|---|---|

## Made — already turned into videos

| Hook | Format | Verify at |
|---|---|---|
| A star that dimmed for years and nobody knows why | fact | boyajian_star (made) |
| The Antarctica Iceberg | ice | antarctica_iceberg (made) |
| A worm that eats bone and has no mouth | creature | bone_eating_worm (made) |
| The shrimp that punches at the speed of a bullet | creature | mantis_shrimp_punch (made) |
| Wolverine's claws were originally a mechanical part of his costume, not bone | hero | wolverine_not_always_mutant (made) |

## Rules for adding to this list

A topic earns a slot if it has: **a verifiable primary source**, **one hard number**, **a real payoff** (a sound, an image, a reveal), and **a gap between the popular version and the true one**. That last one is the most valuable — "the number everyone quotes is the ceiling of a range" is a better video than the myth.

Reject: anything where the only sources are listicles, anything needing copyrighted footage, and any health or safety claim you can't source to peer-reviewed work.
