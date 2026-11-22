"""Edits of the lifted C after the lift writes it (nx2/lift.py, nx2/chunks.py edit_c): none in Inhale.

Upstream's file of this name holds text matched against another game's lifted code. That text is not carried here: this
stand-in keeps the names the lift calls, with empty tables, so the lift's edit passes run and change nothing. A game
patch for Inhale goes in a file of its own (a kirby_ module of nx2/), gated on this game's build id. (Not
written with a star before .py: make_game.py's PY_MADE takes that for a module's name made at run time, and the lift
key then hashes every module whole.)
"""
import collections

LIFE_BUILD_ID = None   # (no build is "the supported build" of these patches: a build id never equals None)
OUT_EDITS = []


def patch_file(s, name, protect_hearts=False):
    """One lifted file: (its text, the places counted in it, the lines to print)"""
    return s, collections.Counter(), []


def report(paths, counts, protect_hearts=False):
    """The warnings from the files' counts: none"""


def output_size_file(s, name):
    """One lifted file: (its text, each place's count in it, the lines to print)"""
    return s, [], []


def check_output_size(found, required=False):
    """found: each place's count over all the files"""


def touches(text):
    """(nx2/guest_locals.py) Whether the edits here would change this lifted function's text: never"""
    return False


def mentioned_addresses():
    """(nx2/guest_locals.py) The guest code addresses the edits here are pinned to: none"""
    return set()
