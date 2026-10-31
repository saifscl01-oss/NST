"""Identifier conventions at the adapter boundary.

Game adapters only know game identifiers. In contracts produced by an FM
adapter, player references are written ``fm:<fm_player_id>``; the bridge binds
them to Hybrid Player IDs through the identity registry before anything else
sees the fixture. Fixture ids are derived by the bridge from the career and the
FM fixture reference so they are stable across re-detection.
"""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Mapping

from ..contracts.models import Fixture, LineupSlot, MatchdaySquad
from ..errors import IdentityError

FM_PREFIX = "fm:"


def fm_ref(fm_player_id: int) -> str:
    return f"{FM_PREFIX}{fm_player_id}"


def parse_fm_ref(ref: str) -> int:
    if not ref.startswith(FM_PREFIX) or not ref[len(FM_PREFIX):].isdigit():
        raise IdentityError(f"not an FM player reference: {ref!r}")
    return int(ref[len(FM_PREFIX):])


def stable_fixture_id(career_id: str, fm_fixture_ref: str) -> str:
    return "FX-" + hashlib.sha256(f"{career_id}|{fm_fixture_ref}".encode("utf-8")).hexdigest()[:20]


def bind_fixture(fixture: Fixture, hybrid_by_fm: Mapping[int, str]) -> Fixture:
    """Rewrite every ``fm:<id>`` reference in a fixture to its Hybrid Player ID."""

    def b(ref: str) -> str:
        fm_id = parse_fm_ref(ref)
        try:
            return hybrid_by_fm[fm_id]
        except KeyError:
            raise IdentityError(f"FM player {fm_id} in fixture was not captured/registered") from None

    def squad(sq: MatchdaySquad) -> MatchdaySquad:
        return replace(
            sq,
            starters=tuple(LineupSlot(s.slot, b(s.hybrid_player_id), s.position) for s in sq.starters),
            bench=tuple(b(p) for p in sq.bench),
            captain_id=b(sq.captain_id) if sq.captain_id else None,
            set_piece_takers={k: b(v) for k, v in sq.set_piece_takers.items()},
        )

    return replace(fixture, home=squad(fixture.home), away=squad(fixture.away))
