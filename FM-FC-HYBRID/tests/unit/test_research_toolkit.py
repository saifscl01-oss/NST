"""Tests for the read-only Windows research toolkit, on synthetic directory trees (no game files)."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

import tests  # noqa: F401
from fmfc_research.cli import main as research_main
from fmfc_research.compare import compare_inventories
from fmfc_research.discovery import classify, discover, steam_library_roots
from fmfc_research.inventory import build_inventory, sha256_file, summarize
from fmfc_research.report import EvidenceBundle, verify_bundle
from fmfc_research.safety import SafetyError, ensure_output_outside


def touch(root: Path, rel: str, content: bytes = b"x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


class ToolkitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.fm26 = self.tmp / "games" / "FM26"
        for rel in ("fm.exe", "game_plugin.dll", "GameAssembly.dll", "UnityPlayer.dll",
                    "fm_Data/il2cpp_data/Metadata/global-metadata.dat"):
            touch(self.fm26, rel)
        self.fm24 = self.tmp / "games" / "FM24"
        touch(self.fm24, "FM.EXE")  # case-insensitive match, as on Windows
        self.fifa = self.tmp / "games" / "FIFA 22"
        touch(self.fifa, "FIFA22.exe")
        touch(self.fifa, "Data/layout.toc")

    def test_classification(self):
        self.assertEqual(classify(self.fm26).games, ["fm26"])
        self.assertEqual(classify(self.fm26).layouts, ["unity_il2cpp"])
        self.assertEqual(classify(self.fm24).games, ["fm_native"])
        fifa = classify(self.fifa)
        self.assertEqual((fifa.games, fifa.layouts), (["fifa22"], ["frostbite_like"]))

    def test_discover_depth_limited(self):
        found = {Path(i.root).name: i.games for i in discover([self.tmp])}
        self.assertEqual(found, {"FM26": ["fm26"], "FM24": ["fm_native"], "FIFA 22": ["fifa22"]})
        self.assertEqual(discover([self.tmp], max_depth=1), [])

    def test_inventory_hashes_and_limits(self):
        p = touch(self.fm26, "big.bin", b"a" * 2048)
        entries = build_inventory(self.fm26, max_hash_bytes=1024)
        by_path = {e.path: e for e in entries}
        self.assertIsNone(by_path["big.bin"].sha256)
        self.assertEqual(by_path["fm.exe"].sha256, sha256_file(self.fm26 / "fm.exe"))
        self.assertEqual(summarize(entries)["unhashed"], 1)
        self.assertEqual(p.read_bytes(), b"a" * 2048)  # untouched

    def test_compare(self):
        a = [e.to_dict() for e in build_inventory(self.fm26)]
        touch(self.fm26, "game_plugin.dll", b"patched")
        touch(self.fm26, "new.dll")
        (self.fm26 / "UnityPlayer.dll").unlink()
        b = [e.to_dict() for e in build_inventory(self.fm26)]
        diff = compare_inventories(a, b)
        self.assertEqual(diff.added, ["new.dll"])
        self.assertEqual(diff.removed, ["UnityPlayer.dll"])
        self.assertEqual([c["path"] for c in diff.changed], ["game_plugin.dll"])

    def test_output_inside_install_is_refused(self):
        with self.assertRaises(SafetyError):
            ensure_output_outside([self.fm26], self.fm26 / "reports")
        with self.assertRaises(SafetyError):
            EvidenceBundle(self.fm26, [self.fm26], label="x")

    def test_bundle_manifest_detects_modification(self):
        out = self.tmp / "evidence"
        bundle = EvidenceBundle(out, [self.fm26], label="t")
        bundle.write_json("a.json", {"k": 1})
        bundle.finalize()
        self.assertEqual(verify_bundle(out), [])
        (out / "a.json").write_text("{}")
        self.assertEqual(verify_bundle(out), ["modified: a.json"])

    def test_cli_inventory_and_rea_plan(self):
        out = self.tmp / "bundle"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(research_main(["inventory", str(self.fm26), "--out", str(out), "--quiet"]), 0)
        manifest = json.loads((out / "manifest.json").read_text())
        self.assertTrue(manifest["read_only"])
        self.assertIn("inventory.json", manifest["files"])
        key = json.loads((out / "key_binaries.json").read_text())
        self.assertIn("game_plugin.dll", key)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            research_main(["rea-plan", str(self.fm26)])
        plan = buf.getvalue()
        self.assertIn("rea inspect-desktop-application", plan)
        self.assertIn("inspect-il2cpp-metadata", plan)
        self.assertIn("game_plugin.dll", plan)

    def test_steam_library_parsing(self):
        steam = self.tmp / "Steam"
        touch(steam, "steamapps/libraryfolders.vdf",
              b'"libraryfolders"\n{\n "0" { "path" "C:\\\\Program Files (x86)\\\\Steam" }\n'
              b' "1" { "path" "D:\\\\SteamLibrary" }\n}\n')
        roots = steam_library_roots(steam)
        self.assertEqual(len(roots), 2)
        self.assertTrue(str(roots[1]).startswith("D:\\SteamLibrary"))
        self.assertEqual(steam_library_roots(self.tmp / "nowhere"), [])


if __name__ == "__main__":
    unittest.main()
