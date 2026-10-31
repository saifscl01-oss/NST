# Project Brief (condensed)

The full brief was given in the session that started this project (2026-10-31). This is the durable
summary future sessions work from.

## Vision
Football Manager is the brain, FIFA is the body, FM-FC Hybrid is the nervous system. FM stays the source
of truth for the football universe (players, attributes, development, transfers, finances, fixtures,
tactics). FIFA / EA Sports FC provides the playable match engine for **the managed club's fixtures
only**. All other fixtures stay simulated by FM.

## Target experience
Manage in FM → press a button in FM → the bridge prepares the FIFA fixture (players, lineups,
attributes, formations, tactical behaviour) → play it (control your team, or watch AI vs AI) → result,
events and performances flow back → FM processes the match and its consequences → continue the career.
It should eventually feel like one game.

## Constraints
Windows PC, offline, single-player, managed club only, FM as the main interface, both user-controlled
and AI-vs-AI matches.

## Available versions
FM15–FM24, FM26; FIFA 15–22. Research candidates: FM24/FM26 and FIFA 20/FIFA 22. Final pairing chosen
on evidence (access to internals, frameworks, data extraction, engine control, event retrieval, FM
integration, stability, gameplay quality), not recency.

## Stated authorization (recorded as stated, not verified)
The user states they possess **publisher-supplied, launcher-independent game files** from Sports
Interactive and Electronic Arts, provided **for this isolated research purpose**, and that the publishers
authorized this isolated use.

**Scope as recorded:** offline, single-player research and development of FM-FC Hybrid on the user's
own machine. This record does **not** extend the authorization to: redistributing game files or derived
assets, committing proprietary binaries to any repository, circumventing DRM, authentication or
anti-cheat, using online EA or SI services, or any multiplayer or commercial use. Where a distribution
requires unsupported authentication or licensing functionality, the limitation is documented rather than
worked around.

**Open scope question:** running in-process community loaders (BepInEx in FM26, the FIFA Live Editor)
inside processes protected by Denuvo, without altering the protection. The user should confirm this is
covered (see [OPEN_PROBLEMS](OPEN_PROBLEMS.md) P-05).

## Success definition
Take one real fixture from an FM career, prepare the correct teams in FIFA, play it, capture events and
statistics, return them to FM, and verify that the same career continues with all relevant consequences
processed. Gates 0–7 are tracked in the [README](../README.md). A gate is complete only with evidence
or a working test; score editing is never described as full integration.

## Standards
Evidence classes (CONFIRMED / SOURCE VERIFIED / DOCUMENTED / INFERRED / UNKNOWN / BLOCKED), source over
summaries, licence checks before reuse, game-specific code isolated behind adapters, typed and tested
code, no proprietary material in git, read-only reconnaissance on copies, never modify valuable saves.
