# Roadmap — what's locked in for after the current build

Written 25 Sep 2026 at Courtney's request. Read this before starting new architecture work.

## Next: finish Nethermind
- ~~16:9 long-form renderer~~ — done 25 Sep (make_long.py; Sundays plan + render automatically).
- First real runs of the Content agent (drafter.py), Intelligence scouts and a real long-form render on the
  Mac; fix what breaks. (Tested in the cloud with stand-in narration, images and a stand-in Claude.)

## When it's making money: scale
- Give the Content agent its own Anthropic API key (drafter.py) instead of Courtney's Claude subscription,
  so drafts never stop at the weekly usage limit (hit on 25 Sep 2026). Keep the login as a fallback.
  Until then: drafts share the subscription limit; a limit error shows on the Content agent with Retry.

## Later: more channels on the same structure
Once Nethermind is fully built and running, reuse the same multi-agent system (agents + sub-agents,
the brain, Draft → approve → build, the learning loop, never posting without approval) for:

1. **Ultra long-form ambience channel.** Hours-long videos of ocean, rain, grass/nature and similar,
   with music. Different Production needs: long seamless loops, audio mixing/mastering, very long
   renders, and rights-safe footage and music. Monetises through watch hours, so it pairs with the
   long-form plan.
2. **Kids videos channel.** Needs YouTube "Made for Kids" rules (COPPA: no personalised ads, comments
   off), age-appropriate fact-checking, and a separate brand, voice and packaging.

Design note: build channels as a setting of the system (one brain per channel, shared agents), not
copies of the code.
