#!/usr/bin/env python3
"""Title gate. Checks title options against the rules in TITLES.md before they go to Courtney.

  python3 packaging/title_check.py long "Title one" "Title two" ...
  python3 packaging/title_check.py short "Title one" ...

A FAIL breaks one of his locked rules or a hard platform limit. A WARN is a pattern the breakout titles rarely show:
fix it or say why it stays. A title Courtney wrote himself is never changed by this; the check only informs him.
Exit code 1 if any title fails. No network, nothing generated."""
import re, sys

BANNED = ['mate', 'bastard', 'bloke', 'hype']          # his voice bans
LABELS = ['explained', 'analysis', 'analyzing', 'analysing', 'deep dive', 'review', 'breakdown']
LIMIT = {'long': (60, 100), 'short': (60, 100)}        # (aim, hard limit) in characters


def check(kind, t):
    fails, warns = [], []; aim, hard = LIMIT[kind]; low = t.lower()
    if len(t) > hard: fails.append(f'{len(t)} characters, YouTube cuts off at {hard}')
    if '—' in t or '–' in t: fails.append('has a long dash (his rule: no em dashes)')
    for w in BANNED:
        if re.search(rf'\b{w}\b', low): fails.append(f'banned word "{w}"')
    if re.search(r'\bgear\s+(second|third|fourth|fifth|2nd|3rd|4th|5th|\d)\b', low): fails.append('gear naming is ordinal-first: "2nd Gear"')
    if len(t) > aim: warns.append(f'{len(t)} characters, aim is {aim} or under')
    if len(re.findall(r"\b[A-Z][A-Z']{2,}\b", t)) >= 3: warns.append('three or more words in capitals')
    if '|' in t or ' - ' in t: warns.append('has a label after a bar or dash')
    if t.rstrip().endswith('?'): warns.append('is a question: 2 of the 72 breakout titles were')
    if any(low.rstrip('.!? ').endswith(l) for l in LABELS) and kind == 'long': warns.append('ends on a label word: fine for a complete guide, weak for an essay')
    if t.count('!') > 1 or '!!' in t: warns.append('more than one exclamation mark')
    if '#' in t and kind == 'long': warns.append('hashtag in a long-form title')
    return fails, warns


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in LIMIT: raise SystemExit(__doc__)
    bad = 0
    for t in sys.argv[2:]:
        fails, warns = check(sys.argv[1], t); bad += bool(fails)
        print(('FAIL' if fails else 'WARN' if warns else 'PASS') + f'  [{len(t)}]  {t}')
        for x in fails: print('   FAIL: ' + x)
        for x in warns: print('   warn: ' + x)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
