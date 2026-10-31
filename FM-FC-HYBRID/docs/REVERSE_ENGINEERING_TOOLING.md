# Reverse-Engineering Tooling: REA ("Reverse Engineer Anything")

Audit date: 2026-10-31. Audited version: **rea-agents 6.8.0** (npm `latest` on the audit date).
Projects in scope: FM-FC Hybrid targets Football Manager 24 (native C++ x64), Football Manager 26
(reportedly Unity, possibly IL2CPP) and FIFA 20/22 (Frostbite, native C++ x64).

> **Audit method and its limits.** This was a **read-only documentation and source audit**. The
> npm tarball was downloaded and unpacked with `tar` into an isolated scratch directory. Its files
> were read with `cat`, `grep` and `sed`, and the JSON catalogs were parsed as data. **No REA code,
> script, binary or dependency was executed, installed (`npm install`) or `require`d.** The cloud
> container's permission policy refused that. REA is **not** installed in the cloud container
> (no `~/.claude/skills/reverse-engineer-anything`, no `rea` binary). The user reports that REA is
> installed in their local Windows Claude Code environment. That claim has **not** been checked.
> Because nothing ran, **no claim in this document is CONFIRMED.** The labels used are:
>
> | Label | Meaning |
> |---|---|
> | SOURCE VERIFIED | Read directly in the 6.8.0 tarball's shipped code, manifests or generated catalog |
> | DOCUMENTED | Stated in REA docs at tag `rea-agents-6.8.0`, or in the shipped SKILL.md or README |
> | INFERRED | Our reasoning from verified or documented facts; not stated by REA |
> | UNKNOWN | Not determinable without running tools or inspecting the actual game files |
> | BLOCKED | Could not be done here because of policy or access |

---

## 1. Identity

| Item | Value | Label |
|---|---|---|
| Name | REA, "Reverse engineer anything from your terminal or agent with one CLI and MCP server." | SOURCE VERIFIED (package.json) |
| Author / copyright | `morluto`, "Copyright (c) 2026 morluto" | SOURCE VERIFIED (LICENSE) |
| Licence | MIT, plus `DISCLAIMER.md` (responsible-use policy, which does not change the licence) and `THIRD_PARTY_NOTICES.md` | SOURCE VERIFIED |
| Source repository | `https://github.com/morluto/rea` (`repository.url` = `git+https://github.com/morluto/rea.git`) | SOURCE VERIFIED |
| MCP registry name | `io.github.morluto/rea` (`mcpName`) | SOURCE VERIFIED |
| npm package | `rea-agents`, latest `6.8.0`, published 2026-10-25T09:07:31Z; earlier: 6.7.0, 6.5.0, 6.4.0, 6.3.0 (6.6.0 was tagged but not published to npm) | SOURCE VERIFIED (registry metadata); the 6.6.0 note is DOCUMENTED (release notes) |
| Tarball | `https://registry.npmjs.org/rea-agents/-/rea-agents-6.8.0.tgz`, sha1 `6a2cc197e4ff7f11ba937125b3ca7e4de939906a`, integrity `sha512-9QDeRnGqEDzABZyr04eLnBXBv/c6I9/TWu/6M0MD4pEfkySI/BIgwTODIbAReX3C1x6hjw9+Jlx4A2yUSPZ9ww==` | SOURCE VERIFIED (local sha1 matches the registry shasum) |
| `gitHead` | **Absent** from the registry version metadata | SOURCE VERIFIED |
| Git tag / commit | Tag `rea-agents-6.8.0` → commit `160d821ac9a0310afcb8d1fc427862dd6508add5`, marked "Latest" on the GitHub releases page | DOCUMENTED (GitHub releases page via WebFetch); the tag exists because raw files resolve at `rea-agents-6.8.0` |
| Binaries | `rea` and `rea-agents` → `scripts/rea.mjs` | SOURCE VERIFIED |
| Node requirement | `^22.23.4 \|\| ^24.22.1 \|\| >=26.12.1` | SOURCE VERIFIED (engines) |
| Install-time scripts | No `preinstall`/`install`/`postinstall`. `prepare` exists but does nothing when `src/` is absent, as in a registry install. The optional dependency `frida@17.23.2` may run its own install step | SOURCE VERIFIED for REA; frida behaviour INFERRED |
| Bundled Windows native addon | `native/windows/build/rea-windows-x64.node` (win32/x64, Node-API 8). Its SHA-256 `6a015bfe…b6ff7b` matches its manifest | SOURCE VERIFIED (hashed, not loaded) |
| Catalog | 229 MCP tools, 175 CLI commands, 6 prompts; tools digest `a98940ba…e5e9` | SOURCE VERIFIED (`dist/mcp-catalog.json`) |

### 1.1 Where the skill actually lives (why the 404 happened)

* The skill registry path `skills/reverse-engineer-anything/SKILL.md` **does not exist in the git
  repository**. It returns 404 at `main` and at the tag. The repository keeps the skill source at
  **`.agents/skills/reverse-engineer-anything/SKILL.md`**. — SOURCE VERIFIED (raw fetches: 200 vs 404)
* The npm tarball ships a generated copy at **`skills/reverse-engineer-anything/`**: `SKILL.md`
  plus 7 references (`native-and-artifacts`, `runtime-observation`, `evidence-workflows`,
  `connection-and-recovery`, `javascript-applications`, `android-applications`, `environments`).
  — SOURCE VERIFIED
* There are three different copies, and the frontmatter `metadata.version` tells them apart:

  | Copy | `metadata.version` | Notes |
  |---|---|---|
  | npm 6.8.0 tarball | `"49"`, `tool_count: 229` | Same as the tag, but with commands pinned to `rea-agents@6.8.0` |
  | git tag `rea-agents-6.8.0` | `"49"` | Uses `rea-agents@latest` |
  | git `main` (fetched 2026-10-31) | `"58"` | Newer and unreleased. Adds a Claude Code / Codex **plugin** install mode (`.claude-plugin/`), which does not exist at the 6.8.0 tag |

  — SOURCE VERIFIED (SHA-256 of each copy differs; diffs reviewed)
* INFERRED: a skill installed through the skills registry (`npx skills add morluto/rea --skill
  reverse-engineer-anything`) may be the newer `main` copy, while a skill installed by `rea setup`
  is the copy that matches the package. The skill itself warns: "a skill installed from repository
  main may describe capabilities absent from an older npm release." (DOCUMENTED)

### 1.2 Install locations on Windows (documented for `~`; Windows expansion inferred)

| What | Location | Label |
|---|---|---|
| Global CLI (`npm install --global rea-agents`) | npm global prefix, e.g. `%APPDATA%\npm\rea.cmd` | Command DOCUMENTED; path INFERRED (npm default) |
| Claude Code skill installed by `rea setup` | `~/.claude/skills/reverse-engineer-anything`, which on Windows is `%USERPROFILE%\.claude\skills\reverse-engineer-anything\SKILL.md` (or `%CLAUDE_CONFIG_DIR%\skills\…` when that is set) | DOCUMENTED (`~` form); Windows form INFERRED |
| Claude Code MCP registration | `mcpServers.rea` in `~/.claude.json`, i.e. `%USERPROFILE%\.claude.json` | DOCUMENTED / INFERRED |
| Skill with no client selected | `~/.agents/skills` | DOCUMENTED |
| Ghidra/Java (needed only for deep native analysis) | Installed by the operator. Examples: `GHIDRA_INSTALL_DIR=C:\tools\ghidra_12.1.4_PUBLIC`, `JAVA_HOME=C:\tools\jdk-21` | DOCUMENTED |

### 1.3 Verify the user's local install (read-only, PowerShell)

```powershell
# 1. CLI present and version (prints the version; starts no provider, reads no target)
where.exe rea
rea --version
rea --version --json            # name, version, runtime, platform, supported_runtime.satisfied
npm ls -g rea-agents
npm view rea-agents dist-tags.latest

# 2. Skill copy and which revision it is (expect version "49" for npm 6.8.0)
Test-Path "$env:USERPROFILE\.claude\skills\reverse-engineer-anything\SKILL.md"
Get-Content "$env:USERPROFILE\.claude\skills\reverse-engineer-anything\SKILL.md" -TotalCount 8
Get-ChildItem "$env:USERPROFILE\.claude\skills\reverse-engineer-anything\references"

# 3. Registration and readiness (doctor is documented as strictly read-only)
claude mcp list
rea doctor --client claude_code --json
rea doctor --skill --json       # identity.skill.state / installed_version / installed_tool_count
rea doctor --provider ghidra --json   # only if Ghidra is meant to be used
rea providers --json
rea capabilities --json
```

All command names above are SOURCE VERIFIED in `dist/cliCommandNames.js` (`doctor`, `providers`,
`capabilities`) or DOCUMENTED (`--version`, `--version --json`, `doctor --skill`,
`doctor --provider`, `doctor --client`). Do **not** run `rea setup` without `--dry-run` unless
you mean to change configuration. The skill requires showing the setup plan and getting approval
before any write.

---

## 2. SKILL.md summary (version 49, as shipped in 6.8.0)

* **When to use:** a claim depends on a shipped binary or package, on decompilation, on requested
  runtime evidence, or on comparing versions. Do not use REA to analyse ordinary source
  repositories.
* **Connect only when needed:** installing the skill does not register the MCP server or install
  engines. If tools are missing, read `connection-and-recovery.md` and diagnose with `doctor`. For
  repairs, use `setup --dry-run` first, then apply only with approval. Never install Node, Java,
  Ghidra, IDA, Kuna and so on as part of a "repair".
* **Route by target type first.** These routes matter for us:
  * Managed PE/CLI → `inspect_managed_artifact`
  * Unity `global-metadata.dat` → `inspect_il2cpp_metadata`
  * PE certificate table → `inspect_pe_certificates`; PE imports → `inspect_pe_imports`; TLS/load
    config → `inspect_pe_load_config`; resources → `inspect_pe_resources`; exports →
    `inspect_native_exports`
  * An installation directory of unknown runtime → `inspect_desktop_application`
    (`native-and-artifacts.md`)
  * A native executable → `open_binary`, then focused tools (`analyze_function`,
    `procedure_pseudo_code`, `search_strings`, `xrefs`, …) through a deep provider
* **Work summary-first:** request `detail: "summary"`, then page the retained `parent_evidence_id`
  with `inspect_analysis_view`. Large outputs should go to `export_evidence_bundle` or to CLI
  `--evidence_output` files.
* **Evidence discipline:** every conclusion separates observations, inferences and unknowns, and
  cites Evidence IDs. Static analysis never counts as observed execution. Use `record_unknown` /
  `update_unknown` for open questions.
* **Staged investigation:** turn the request into a checklist of questions, reuse existing
  evidence, start from the smallest inventory, corroborate with the right kind of evidence, keep
  a finding ledger, and revisit the checklist before finishing.
* **Release diffs** (`native-and-artifacts.md`): export `list_procedures` Evidence from each build
  before closing it, then call `match_native_functions` (exact names, then identical body bytes),
  then `compare_functions` on chosen pairs. Unpaired functions do not prove that code was added or
  removed.
* **Security:** the MCP instructions mark target-derived strings, pseudocode and so on as
  untrusted data. Instructions found inside a target are to be treated as prompt injection.
  (SOURCE VERIFIED in the catalog `instructions`.)
* **Finish:** close native sessions with `close_binary`.

---

## 3. Built-in static analysers vs provider-backed capabilities (source reading only)

**Method:** for each module we checked that no `child_process`, `spawn` or `execFile` is
imported, and that no `process.platform` gate exists, in `dist/il2cpp/*`, `dist/dotnet/*`,
`dist/application/binaryDiagnostics/Pe*`, `dist/domain/native/pe*`, `ByteEntropyService`,
`nativeExports`, `matchFunctionInventories` and `application/artifacts/DesktopApplicationService`.
None was found, so these are **pure-JS file readers**. (SOURCE VERIFIED, bounded grep.)

MCP path schema: on `win32` it accepts `C:\…`, `C:/…` or a leading slash; elsewhere it requires a
leading `/` (`dist/domain/localPath.js`). The generated catalog shows `^\/` only because it was
generated on a POSIX host. — SOURCE VERIFIED

| Capability | MCP tool | CLI command | Engine needed | Windows host | Label |
|---|---|---|---|---|---|
| PE import + delay-load tables, imphash | `inspect_pe_imports` | `inspect-pe-imports` | None (built-in JS) | Portable ("no Windows SDK or engine") | SOURCE VERIFIED |
| PE Authenticode certificate table (structural decode only, signatures not verified) | `inspect_pe_certificates` | `inspect-pe-certificates` | None | Portable | SOURCE VERIFIED |
| PE TLS callbacks / load config (CFG etc.) | `inspect_pe_load_config` | `inspect-pe-load-config` | None | Portable | SOURCE VERIFIED |
| PE resources | `inspect_pe_resources` | `inspect-pe-resources` | None | Portable | SOURCE VERIFIED |
| PE/ELF exports | `inspect_native_exports` | `inspect-native-exports` | None | Portable | SOURCE VERIFIED |
| Byte entropy (packing triage) | `inspect_byte_entropy` | `inspect-byte-entropy` | None | Portable | SOURCE VERIFIED |
| Desktop install-directory runtime detection (.NET, Unity Mono/IL2CPP, Unreal, …) | `inspect_desktop_application` | `inspect-desktop-application` | None | Portable (no platform gate found) | SOURCE VERIFIED |
| Unity IL2CPP `global-metadata.dat` (v24/27/29/31/39) + optional `GameAssembly.dll` address linking | `inspect_il2cpp_metadata` | `inspect-il2cpp-metadata` | None | Portable | SOURCE VERIFIED (`IL2CPP_METADATA_VERSIONS = [24, 27, 29, 31, 39]`) |
| .NET PE/CLI metadata, members, CIL, cross-build member diff | `inspect_managed_artifact`, `inspect_managed_members`, `compare_managed_members` | `inspect-managed-artifact`, `inspect-managed-members`, `compare-managed-members` | None | Code is portable, **but REA states the managed workflow "has not been verified on a Windows host"** | SOURCE VERIFIED + DOCUMENTED |
| Native function inventory matching (two builds) | `match_native_functions` | `match-native-functions` | None for matching; **the inputs (`list_procedures` Evidence) need a provider** | Portable | SOURCE VERIFIED |
| Evidence bundle membership comparison | `compare_bundles` | `compare` | None | Portable | DOCUMENTED |
| Decompilation, functions, xrefs, strings, callers/callees | `open_binary` + `analyze_function`, `procedure_pseudo_code`, `xrefs`, `search_strings`, … | `analyze`, `inspect`, `decompile`, `function`, `xrefs`, `search`, `trace` | **Ghidra / Hopper / IDA / Kuna** | **Ghidra only:** "experimental Windows x64 P0", read-only (26 operations). Hopper is not on Windows. **Kuna: "Windows is not supported yet; PE rejected."** IDA: verified with IDA Pro 9.3 on Windows | DOCUMENTED |
| PDB / debug symbols | Reported in Ghidra Evidence (PDB file, GUID, age, "PDB Loaded") | — | Ghidra | REA **does not accept a caller-supplied PDB companion and does not query symbol servers** | DOCUMENTED |
| Runtime: Frida instrumentation | `start_frida_session`, `load_frida_script`, … | `instrument-with-frida` | frida (optional dependency) | Real verifier "covers Linux"; **Windows behaviour UNKNOWN** | DOCUMENTED / UNKNOWN |
| Runtime: process capture | `capture_process_scenario` | `capture-process` | PTY | **Unavailable on native Windows**. Comparing existing captures works on Windows | DOCUMENTED |
| Runtime: GDB / Rizin debug | `start_gdb_session`, `start_rizin_debug_session` | `debug-with-gdb`, `debug-with-rizin` | gdb / rizin | **Linux only** | DOCUMENTED |
| Runtime: LLDB call observation / native UI | `observe_native_calls`, `observe_native_ui` | `observe-native-calls`, `observe-native-ui` | LLDB / macOS | **macOS only** | DOCUMENTED |
| Ghidra function seeds from IL2CPP | `inspect-il2cpp-metadata --ghidra-seeds FILE` (CLI only), then `REA_GHIDRA_SEED_FILE` | — | Writes the file statically; using it needs Ghidra | Portable to write | DOCUMENTED |

---

## 4. Capability map for FM-FC Hybrid targets

Classes: **CLOUD-OK-IN-PRINCIPLE** means static pure JS that could run on Linux, given the
user's own copies of the files, *but was not executed here because policy refused it*.
**LOCAL-WINDOWS** means it needs the user's Windows machine (game files live there, or a
Windows-only path is involved). **PROVIDER** means it needs Ghidra (Windows P0), IDA, or similar
installed by the operator.

| Need | REA route | Class | Fit for our targets | Label |
|---|---|---|---|---|
| Windows PE header facts, imports, delay-loads, imphash | `inspect-pe-imports` | CLOUD-OK-IN-PRINCIPLE; practically LOCAL-WINDOWS (game files) | FM24 exe, FIFA20/22 exe, FM26 `GameAssembly.dll` / `UnityPlayer.dll`. Default limit is **64 MiB**; raise with `--max-file-bytes` (max **512 MiB**). Game executables may exceed the default; actual sizes UNKNOWN | SOURCE VERIFIED (limits) |
| Authenticode certificates | `inspect-pe-certificates` | Same as above | Identifies the signer. **Does not verify** signatures, chains or timestamps | SOURCE VERIFIED |
| TLS callbacks / CFG / load config | `inspect-pe-load-config` | Same as above | Useful pre-entry-point facts; mitigation flags are labelled inferred | SOURCE VERIFIED |
| Resources / version info / icons | `inspect-pe-resources` | Same as above | Build identification (payloads are opaque but hashed) | SOURCE VERIFIED |
| Exports | `inspect-native-exports` (default limit 256 MiB, max 512 MiB) | Same as above | e.g. `il2cpp_*` exports of `GameAssembly.dll` | SOURCE VERIFIED |
| Packing/encryption triage | `inspect-byte-entropy` | Same as above | Flags high-entropy regions. "Cannot distinguish compression from encryption" | SOURCE VERIFIED |
| Runtime family of an install directory | `inspect-desktop-application` | LOCAL-WINDOWS (needs the install tree) | Decides **whether FM26 is Unity Mono or IL2CPP**. Also labels EAC/BattlEye path markers (no bypass) | SOURCE VERIFIED |
| Debug symbols / PDB | Ghidra handshake reporting only | PROVIDER + LOCAL-WINDOWS | Retail games rarely ship PDBs (INFERRED). REA cannot be pointed at a PDB | DOCUMENTED |
| .NET assemblies | `inspect-managed-artifact`, `inspect-managed-members`, `compare-managed-members` | CLOUD-OK-IN-PRINCIPLE | Relevant **only if** FM26 turns out to be Unity Mono (`*_Data/Managed/Assembly-CSharp.dll`) or ships other managed DLLs. Not verified on a Windows host | DOCUMENTED |
| Unity IL2CPP metadata | `inspect-il2cpp-metadata [--binary GameAssembly.dll]` | CLOUD-OK-IN-PRINCIPLE | Supported: **24, 27, 29, 31, 39** (examples: Unity 2019.4→24, 2020.3→27, 2022.3.30→29, 2022.3.62→31, 6000.4.2→39). **FM26's Unity version and metadata version are UNKNOWN.** Any other version → `unsupported-version`. Encrypted or obfuscated metadata → `unrecognized-magic` (**not decrypted**). Windows x64 `GameAssembly.dll` linking was verified against a v29 build. Size guards: 256 MiB metadata, 1 GiB binary. 32-bit images are unsupported | SOURCE VERIFIED (versions) + DOCUMENTED (examples, verification) |
| Binary comparison / diffing | PE level: run the `inspect-pe-*` commands on both builds and diff the JSON externally. Managed: `compare-managed-members`. Native functions: `list_procedures` (provider) → `match_native_functions` → `compare_functions`. Evidence sets: `compare` | Mixed. Native diff needs PROVIDER | **No built-in IL2CPP-metadata comparator** in the 229-tool catalog; diff two `inspect-il2cpp-metadata` outputs externally | SOURCE VERIFIED (tool list) / INFERRED (external diff) |
| Decompilation | `rea decompile/function/analyze … --provider ghidra` or MCP `open_binary` | PROVIDER + LOCAL-WINDOWS | Windows Ghidra P0: Ghidra 12.1.x (verified 12.1.4), JDK 21+, Windows 10+ x64, **local NTFS only (no UNC, no reparse points, no SUBST)**, native non-managed PE. Cold import of large binaries can take a very long time: verified small samples took 400–600 s. Raise `REA_GHIDRA_STARTUP_TIMEOUT_MS` and `GHIDRA_HEADLESS_MAXMEM`. **Packed or protected code decompiles as the stub only** | DOCUMENTED |
| Runtime evidence / tracing on Windows | Effectively only Frida (Windows UNKNOWN). Process capture, GDB, Rizin and LLDB are unavailable on Windows | LOCAL-WINDOWS, unverified | Also limited by game EULAs and by REA's DISCLAIMER (no game cheats, anti-cheat or DRM work). **Treat as out of scope unless explicitly authorised** | DOCUMENTED / INFERRED |
| Evidence records | Every tool returns Evidence. Commands: `evidence-import`, `evidence-export`, `inspect-evidence-bundle`, `inspect-analysis-view`, `export_evidence_bundle` | Portable | Use as our provenance format: artifact SHA-256, file ranges, coverage, limitations | SOURCE VERIFIED (commands) / DOCUMENTED |
| Frostbite data (`.toc`/`.sb`/`.cas`), FM databases | None | — | **No Frostbite or game-archive support** in source (grep negative). Needs separate tooling | SOURCE VERIFIED (bounded negative) |

---

## 5. Local Windows command templates (read-only, placeholders)

Assumptions: PowerShell, `rea` on PATH (otherwise use `npx -y rea-agents@6.8.0 <command>`).
Every command name below is in `dist/cliCommandNames.js` (SOURCE VERIFIED). Flag spellings come
from the docs or from the CLI registrations in `dist/cli/*.js`. Incur accepts both the schema key
and its kebab-case form; for example, `--max-file-bytes` is documented.

Recommendations (INFERRED):
* Copy the target binaries to a scratch folder without spaces or parentheses on a local NTFS
  drive, such as `C:\re\…`. Analyse the copies, never the live Steam/EA install.
* Write JSON with `--evidence_output` where the command supports it. Otherwise pipe to
  `Set-Content -Encoding utf8`, because Windows PowerShell 5.1 `>` writes UTF-16.
* REA never overwrites existing output files.

```powershell
# ---- placeholders ----
$RE    = "C:\re"                                   # scratch (local NTFS, no spaces)
$FM26  = "D:\Games\Football Manager 26"           # install dir (placeholder)
$FM24  = "D:\Games\Football Manager 2024"         # install dir (placeholder)
$FIFA  = "D:\Games\FIFA 22"                        # install dir (placeholder)
New-Item -ItemType Directory -Force "$RE\fm26","$RE\fm24","$RE\fifa22","$RE\fifa20","$RE\out" | Out-Null
```

### 5.1 Readiness

See section 1.3. Minimum set:
`rea --version --json`, `rea doctor --client claude_code --json`, `rea doctor --skill --json`,
`rea providers --json`, and, only for deep analysis, `rea doctor --provider ghidra --json`.

### 5.2 FM26: identify the runtime, then IL2CPP metadata and GameAssembly.dll

```powershell
# a) What runtime is this? (Unity Mono vs IL2CPP vs other; no execution)
rea inspect-desktop-application "$FM26" --detail summary --evidence_output "$RE\out\fm26-desktop.json" --json

# b) If IL2CPP: copy the pair (paths below are the usual Unity layout - verify via step a)
Copy-Item "$FM26\GameAssembly.dll" "$RE\fm26\"
Copy-Item "$FM26\<Game>_Data\il2cpp_data\Metadata\global-metadata.dat" "$RE\fm26\"

# c) Metadata only (reports metadata_version; fails with unsupported-version / unrecognized-magic otherwise)
rea inspect-il2cpp-metadata "$RE\fm26\global-metadata.dat" --detail summary --evidence_output "$RE\out\fm26-metadata.json" --json

# d) Link method addresses from GameAssembly.dll (static read; never loaded)
rea inspect-il2cpp-metadata "$RE\fm26\global-metadata.dat" --binary "$RE\fm26\GameAssembly.dll" --detail summary --evidence_output "$RE\out\fm26-metadata-linked.json" --json

# e) Optional: generic instances + Ghidra seed file (writes a NEW file only)
rea inspect-il2cpp-metadata "$RE\fm26\global-metadata.dat" --binary "$RE\fm26\GameAssembly.dll" --generic-instances --ghidra-seeds "$RE\out\fm26-seeds.tsv" --json | Out-Null

# f) Page saved rows without re-decoding (request JSON per docs/cli.md "inline"/"evidence-file" source)
#    {"source":{"kind":"evidence-file","path":"C:\\re\\out\\fm26-metadata.json"},"view":{"kind":"il2cpp-metadata","collection":"types","offset":0,"limit":64}}
rea inspect-analysis-view "$RE\out\fm26-view.json" --json

# g) PE facts of the IL2CPP binary
rea inspect-pe-imports      "$RE\fm26\GameAssembly.dll" --max-file-bytes 536870912 --json | Set-Content -Encoding utf8 "$RE\out\fm26-ga-imports.json"
rea inspect-native-exports  "$RE\fm26\GameAssembly.dll" --detail summary --evidence_output "$RE\out\fm26-ga-exports.json" --json
rea inspect-pe-certificates "$RE\fm26\GameAssembly.dll" --max-file-bytes 536870912 --json | Set-Content -Encoding utf8 "$RE\out\fm26-ga-certs.json"

# h) If instead Unity Mono / managed DLLs exist:
rea inspect-managed-artifact "$FM26\<Game>_Data\Managed\Assembly-CSharp.dll" --json
rea inspect-managed-members  "$FM26\<Game>_Data\Managed\Assembly-CSharp.dll" --detail summary --evidence-bundle "$RE\out\fm26-members.json" --json
```

Notes: the `--detail summary` + `--evidence_output` pairing is DOCUMENTED for il2cpp, desktop and
exports. Managed uses `--evidence-bundle` (DOCUMENTED). `--max-file-bytes` on exports is
SOURCE VERIFIED as an option. The data-folder name `<Game>_Data` is a placeholder; its real name
is UNKNOWN.

### 5.3 FM24: executable imports, certificates, load config, resources

```powershell
Copy-Item "$FM24\fm.exe" "$RE\fm24\"            # executable name is a placeholder - confirm locally
rea inspect-desktop-application "$FM24" --detail summary --evidence_output "$RE\out\fm24-desktop.json" --json
rea inspect-pe-imports      "$RE\fm24\fm.exe" --max-file-bytes 536870912 --json | Set-Content -Encoding utf8 "$RE\out\fm24-imports.json"
rea inspect-pe-certificates "$RE\fm24\fm.exe" --max-file-bytes 536870912 --json | Set-Content -Encoding utf8 "$RE\out\fm24-certs.json"
rea inspect-pe-load-config  "$RE\fm24\fm.exe" --max-file-bytes 536870912 --json | Set-Content -Encoding utf8 "$RE\out\fm24-loadcfg.json"
rea inspect-pe-resources    "$RE\fm24\fm.exe" --max-file-bytes 536870912 --json | Set-Content -Encoding utf8 "$RE\out\fm24-resources.json"
rea inspect-byte-entropy    "$RE\fm24\fm.exe" --block-size 65536 --json | Set-Content -Encoding utf8 "$RE\out\fm24-entropy.json"   # CLI has no --detail (MCP does)
```

### 5.4 FIFA 20 / FIFA 22: executable imports (plus certificates and entropy)

```powershell
Copy-Item "$FIFA\FIFA22.exe" "$RE\fifa22\"      # name is a placeholder; same pattern for FIFA20
rea inspect-pe-imports      "$RE\fifa22\FIFA22.exe" --max-file-bytes 536870912 --json | Set-Content -Encoding utf8 "$RE\out\fifa22-imports.json"
rea inspect-pe-certificates "$RE\fifa22\FIFA22.exe" --max-file-bytes 536870912 --json | Set-Content -Encoding utf8 "$RE\out\fifa22-certs.json"
rea inspect-pe-load-config  "$RE\fifa22\FIFA22.exe" --max-file-bytes 536870912 --json | Set-Content -Encoding utf8 "$RE\out\fifa22-loadcfg.json"
rea inspect-byte-entropy    "$RE\fifa22\FIFA22.exe" --block-size 65536 --json | Set-Content -Encoding utf8 "$RE\out\fifa22-entropy.json"
```

A file larger than 512 MiB cannot be read by the PE tools at all (SOURCE VERIFIED maximum).
Whether these executables are packed or protected is UNKNOWN. High-entropy results would
indicate that deep decompilation is not meaningful, and REA's DISCLAIMER forbids circumventing
protection.

### 5.5 Compare two builds (e.g. two FM26 patches, or FIFA 20 vs FIFA 22 imports)

```powershell
# PE-level: same command on both builds, diff outside REA (INFERRED approach)
rea inspect-pe-imports "$RE\build-a\GameAssembly.dll" --max-file-bytes 536870912 --json | Set-Content -Encoding utf8 "$RE\out\a-imports.json"
rea inspect-pe-imports "$RE\build-b\GameAssembly.dll" --max-file-bytes 536870912 --json | Set-Content -Encoding utf8 "$RE\out\b-imports.json"
git diff --no-index "$RE\out\a-imports.json" "$RE\out\b-imports.json"

# IL2CPP metadata: no built-in comparator - export both, diff names/counts externally
rea inspect-il2cpp-metadata "$RE\build-a\global-metadata.dat" --detail summary --evidence_output "$RE\out\a-meta.json" --json
rea inspect-il2cpp-metadata "$RE\build-b\global-metadata.dat" --detail summary --evidence_output "$RE\out\b-meta.json" --json

# Managed (only if Mono/managed DLLs exist): positional left/right paths (SOURCE VERIFIED leftPath/rightPath)
rea compare-managed-members "$RE\build-a\Assembly-CSharp.dll" "$RE\build-b\Assembly-CSharp.dll" --json

# Native function matching (needs Ghidra): in MCP, open_binary + list_procedures on each build,
# export_evidence_bundle each, then:
#   rea match-native-functions "$RE\out\match-input.json" --source_bundle "$RE\out\a.json" --source_bundle "$RE\out\b.json" --evidence_output "$RE\out\match.json"
# Evidence-bundle membership comparison:
rea compare "$RE\out\a.json" "$RE\out\b.json" --json
```

### 5.6 Deep native analysis (optional; requires Ghidra Windows P0)

```powershell
$env:GHIDRA_INSTALL_DIR = "C:\tools\ghidra_12.1.4_PUBLIC"
$env:JAVA_HOME          = "C:\tools\jdk-21"
$env:REA_ANALYSIS_PROVIDER = "ghidra"
$env:REA_GHIDRA_STARTUP_TIMEOUT_MS = "1800000"   # large games: cold import is slow (example budget)
$env:GHIDRA_HEADLESS_MAXMEM = "8G"               # placeholder; size to the host
rea doctor --provider ghidra --json
rea analyze "$RE\fm24\fm.exe" --provider ghidra --snapshot "$RE\out\fm24-snapshot.json" --json
rea decompile "$RE\fm24\fm.exe" 0x140001000 --provider ghidra --json   # address placeholder
```

---

## 6. Limitations and policy boundaries

1. **Nothing was executed here.** The cloud container refused to install or run REA (BLOCKED).
   Every capability is described from source and docs. The first local run is the real
   verification.
2. **REA's DISCLAIMER** (SOURCE VERIFIED, `DISCLAIMER.md`) says the project "does not support,
   and will not help with":
   * circumventing DRM, licence checks or anti-cheat;
   * developing game cheats or tampering with online services;
   * copying proprietary software or reproducing its protected code and assets.

   FM-FC Hybrid work must stay within interoperability and analysis of legally owned copies, and
   must not redistribute decompiled code or assets. The user is responsible for EULA compliance.
   REA labels anti-cheat paths only and states "No bypass is provided."
3. **Windows deep analysis is experimental:** Ghidra P0 is read-only (no annotations or renames).
   Admission is local NTFS only; reparse points, UNC paths and SUBST drives are rejected; managed
   images are rejected. Kuna does not support Windows or PE. Hopper is not available on Windows.
4. **IL2CPP:** only metadata versions 24/27/29/31/39. Encrypted or obfuscated metadata is
   unsupported. 32-bit binaries are unsupported. Linking proves static structure, not same-build
   pairing or runtime behaviour. Names come from metadata only.
5. **Size limits:** PE tools default to 64 MiB (maximum 512 MiB). Exports default to 256 MiB.
   IL2CPP allows 256 MiB metadata and a 1 GiB binary. The desktop scan defaults to 20,000 entries
   (maximum 100,000).
6. **No PDB ingestion** and no symbol-server lookup. **No Frostbite archive support.**
7. **Runtime tracing on Windows** is essentially unavailable or unverified (see section 4).
8. **Version drift:** repository `main` (skill v58) documents features absent from npm 6.8.0
   (skill v49), such as the plugin install mode. Use the connected server's `tools/list`, or
   `rea --help`, as the source of truth locally.
9. Certificate inspection does **not** verify signatures. A missing table is "observed absence",
   not proof that the file is unsigned or has no imports.

---

## 7. Evidence ledger

| # | Claim | Evidence | Label |
|---|---|---|---|
| E1 | Package `rea-agents` 6.8.0 is npm latest, published 2026-10-25 | registry JSON `dist-tags`, `time` | SOURCE VERIFIED |
| E2 | Tarball sha1 `6a2cc197…906a` matches registry shasum | local `sha1sum` vs registry `dist.shasum` | SOURCE VERIFIED |
| E3 | `gitHead` absent | registry version object | SOURCE VERIFIED |
| E4 | Tag `rea-agents-6.8.0` → `160d821ac9a0…add5`, Latest | GitHub releases page (WebFetch summary) | DOCUMENTED |
| E5 | MIT, © 2026 morluto; DISCLAIMER forbids DRM, anti-cheat and cheat work | `LICENSE`, `DISCLAIMER.md` | SOURCE VERIFIED |
| E6 | Skill source at `.agents/skills/…`; npm copy at `skills/…`; versions 49 (6.8.0) vs 58 (main) | raw fetch codes, SHA-256 of three copies, frontmatter | SOURCE VERIFIED |
| E7 | 229 MCP tools / 175 CLI commands; names as listed in sections 3–5 | `dist/mcp-catalog.json`, `dist/cliCommandNames.js` | SOURCE VERIFIED |
| E8 | PE/IL2CPP/managed/desktop/entropy/exports analysers spawn no processes and have no platform gate | grep of listed `dist/` modules | SOURCE VERIFIED (bounded) |
| E9 | Windows MCP paths accept drive-letter paths | `dist/domain/localPath.js` | SOURCE VERIFIED |
| E10 | IL2CPP versions `[24, 27, 29, 31, 39]`; magic `0xFAB11BAF`; encrypted input not decoded | `dist/domain/il2cpp/il2cppMetadata.js`, `dist/il2cpp/Il2cppMetadataFile.js` | SOURCE VERIFIED |
| E11 | IL2CPP Windows x64 `GameAssembly.dll` linking verified on a v29 build; 256 MiB / 1 GiB guards | `docs/il2cpp-metadata.md` @tag; catalog description | DOCUMENTED / SOURCE VERIFIED |
| E12 | PE tools default 64 MiB, max 512 MiB; `maxFileBytes` CLI option | catalog input schemas; `dist/cli/binaryDiagnosticsCommands.js` | SOURCE VERIFIED |
| E13 | Windows Ghidra P0: experimental, read-only, Ghidra 12.1.x + JDK 21, local NTFS, native PE only | `docs/windows-ghidra-p0.md` @tag | DOCUMENTED |
| E14 | Kuna: Windows unsupported, PE rejected | `docs/kuna-provider.md` @tag | DOCUMENTED |
| E15 | IDA verified on Windows with IDA Pro 9.3 (via `mrexodia/ida-pro-mcp`) | `docs/ida-provider.md` @tag | DOCUMENTED |
| E16 | Ghidra reports PDB state; REA admits no caller PDB, no symbol servers | `docs/ghidra-provider.md` @tag | DOCUMENTED |
| E17 | Managed workflow not verified on a Windows host | `docs/managed-code-analysis.md` @tag | DOCUMENTED |
| E18 | Process capture unavailable on native Windows; GDB/Rizin Linux-only; LLDB/native UI macOS-only; Frida verifier Linux | `runtime-observation.md` (skill), `process-capture.md`, `reverse-engineering-tools.md`, `frida-instrumentation.md` | DOCUMENTED |
| E19 | No Frostbite/Denuvo handling in source; EAC/BattlEye only as path labels | grep of `dist/` | SOURCE VERIFIED (bounded negative) |
| E20 | `rea --version [--json]`, `doctor --skill/--provider/--client` exist and are read-only | `docs/cli.md`, `docs/installation.md` @tag | DOCUMENTED |
| E21 | Skill path on Windows = `%USERPROFILE%\.claude\skills\reverse-engineer-anything` | docs give `~/.claude/skills`; Windows expansion | INFERRED |
| E22 | User's local install exists, and its version/skill revision | — | UNKNOWN (user-reported; run section 1.3) |
| E23 | FM26 engine (Unity? IL2CPP?), Unity version, metadata version | — | UNKNOWN (run section 5.2a/c) |
| E24 | Game binary sizes vs 512 MiB limit; packing or protection status | — | UNKNOWN |
| E25 | Running or installing REA in the cloud container | permission system refusal | BLOCKED |

Audit artefacts (scratch, not part of the repo): the extracted tarball at
`/tmp/claude-0/-home-user-NST/953f70f4-169d-559b-9007-0495bfe4f535/scratchpad/rea_pkg/package/`
and the tag docs at
`/tmp/claude-0/-home-user-NST/953f70f4-169d-559b-9007-0495bfe4f535/scratchpad/rea_docs/tag/`.
