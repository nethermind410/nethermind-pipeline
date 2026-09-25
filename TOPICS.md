# Topic backlog

The queue the pipeline pulls from. Each line is a video: the hook, the format, and where to verify it. **Nothing here is pre-verified** — the source column is where to check, not proof. Verify before scripting; that step is the channel's whole defence.

Formats: `fact` = narrated story · `ice` = iceberg chart (no media needed) · `creature` = animal reveal

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

## Iceberg — cheapest format, no media at all

| Hook | Format | Verify at |
|---|---|---|
| The Unsolved Signals Iceberg | ice | Per-tier, individually |
| The Extinction Iceberg | ice | Museum / IUCN sources |
| The Sleep Iceberg | ice | Peer-reviewed sleep research only — health claims need care |
| The Video Game Cancellation Iceberg | ice | Developer interviews, not fan wikis |
| The Heavy Metal Iceberg | ice | Band interviews, documented history |
| The Ocean Trench Iceberg | ice | NOAA |
| The Lost Media Iceberg | ice | Lost Media Wiki → then find the primary source |

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
