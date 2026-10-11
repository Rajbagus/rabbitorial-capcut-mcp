"""Checks list_drafts / load_draft folder resolution and draft_id validation.

Works only on fake projects inside temporary folders. The real CapCut Projects
folder is snapshotted before and after every test and must not change.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

import edit_existing_impl  # noqa: E402
import mcp_server  # noqa: E402
import save_draft_impl  # noqa: E402
import settings  # noqa: E402
from draft_cache import DRAFT_CACHE  # noqa: E402
from draft_profiles import get_draft_profile  # noqa: E402
from edit_existing_impl import LOADED_DRAFTS, default_draft_folder  # noqa: E402

REAL_FOLDER = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")
MAC_DEFAULT = REAL_FOLDER


def snapshot(root):
    """Relative path -> (mode, size, mtime_ns) for root and everything under it."""
    st = os.lstat(root)
    snap = {".": (st.st_mode, st.st_mtime_ns)}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            p = os.path.join(dirpath, name)
            st = os.lstat(p)
            snap[os.path.relpath(p, root)] = (st.st_mode, st.st_size, st.st_mtime_ns)
    return snap


def make_project(parent, folder_name, display_name):
    """Fake CapCut project built from the repo's own draft template."""
    d = os.path.join(parent, folder_name)
    shutil.copytree(os.path.join(REPO, get_draft_profile().template_dir), d)
    meta_path = os.path.join(d, "draft_meta_info.json")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    meta["draft_name"] = display_name
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f)
    return d


class Base(unittest.TestCase):
    def setUp(self):
        self.real_before = snapshot(REAL_FOLDER) if os.path.isdir(REAL_FOLDER) else None
        self.tmp = tempfile.mkdtemp(prefix="capcut_folder_test_")
        # Mirrors the real layout, spaces included.
        self.folder = os.path.join(self.tmp, "My Movies", "CapCut", "User Data", "Projects", "com.lveditor.draft")
        os.makedirs(self.folder)
        self.env = mock.patch.dict(os.environ, {"CAPCUT_DRAFT_FOLDER": self.folder})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        for new_id in list(LOADED_DRAFTS):
            if LOADED_DRAFTS[new_id].startswith(self.tmp):
                LOADED_DRAFTS.pop(new_id)
                DRAFT_CACHE.pop(new_id, None)
        shutil.rmtree(self.tmp)
        if self.real_before is not None:
            self.assertEqual(self.real_before, snapshot(REAL_FOLDER), "real CapCut folder changed")


class DefaultFolderTests(Base):
    def test_env_var_with_spaces_used_verbatim(self):
        self.assertEqual(default_draft_folder(), self.folder)

    def test_env_var_tilde_expanded(self):
        with mock.patch.dict(os.environ, {"CAPCUT_DRAFT_FOLDER": "~/Some Folder/drafts"}):
            self.assertEqual(default_draft_folder(), os.path.expanduser("~/Some Folder/drafts"))

    def test_unset_on_mac(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("CAPCUT_DRAFT_FOLDER")
            with mock.patch.object(edit_existing_impl.platform, "system", return_value="Darwin"):
                self.assertEqual(default_draft_folder(), MAC_DEFAULT)

    def test_empty_or_blank_counts_as_unset(self):
        for value in ("", "   "):
            with mock.patch.dict(os.environ, {"CAPCUT_DRAFT_FOLDER": value}):
                with mock.patch.object(edit_existing_impl.platform, "system", return_value="Darwin"):
                    self.assertEqual(default_draft_folder(), MAC_DEFAULT)

    def test_unset_on_windows(self):
        os.environ.pop("CAPCUT_DRAFT_FOLDER")
        with mock.patch.object(edit_existing_impl.platform, "system", return_value="Windows"):
            with mock.patch.dict(os.environ, {"LOCALAPPDATA": r"C:\Users\x\AppData\Local"}):
                self.assertEqual(default_draft_folder(), os.path.join(
                    r"C:\Users\x\AppData\Local", "CapCut", "User Data", "Projects", "com.lveditor.draft"))

    def test_save_draft_default_uses_env_var(self):
        # An existing folder makes save refuse, and the error names the folder it resolved to.
        os.makedirs(os.path.join(self.folder, "dfd_cat_env_check"))
        DRAFT_CACHE["dfd_cat_env_check"] = object()
        try:
            out = mcp_server.execute_tool("save_draft", {"draft_id": "dfd_cat_env_check"})
        finally:
            DRAFT_CACHE.pop("dfd_cat_env_check", None)
        self.assertFalse(out["success"])
        self.assertIn(os.path.join(self.folder, "dfd_cat_env_check"), out["error"])

    def test_cloud_upload_disabled(self):
        self.assertIs(settings.IS_UPLOAD_DRAFT, False)
        self.assertIs(save_draft_impl.IS_UPLOAD_DRAFT, False)


class ListDraftsTests(Base):
    def test_lists_projects_from_env_folder(self):
        make_project(self.folder, "0101", "Holiday Trip")
        make_project(self.folder, "Project With Spaces", "Spaced Name")
        os.makedirs(os.path.join(self.folder, "not a project"))
        with open(os.path.join(self.folder, "root_meta_info.json"), "w") as f:
            f.write("{}")
        before = snapshot(self.folder)

        out = mcp_server.execute_tool("list_drafts", {})
        self.assertTrue(out["success"])
        res = out["result"]
        self.assertEqual(res["draft_folder"], self.folder)
        drafts = {d["folder"]: d for d in res["drafts"]}
        self.assertEqual(set(drafts), {"0101", "Project With Spaces", "not a project"})
        self.assertEqual(drafts["0101"]["name"], "Holiday Trip")
        self.assertEqual(drafts["Project With Spaces"]["name"], "Spaced Name")
        self.assertTrue(drafts["0101"]["editable"])
        self.assertFalse(drafts["not a project"]["editable"])
        self.assertEqual(before, snapshot(self.folder))

    def test_missing_folder_reports_failure(self):
        with mock.patch.dict(os.environ, {"CAPCUT_DRAFT_FOLDER": os.path.join(self.tmp, "does not exist")}):
            out = mcp_server.execute_tool("list_drafts", {})
        self.assertFalse(out["success"])
        self.assertIn("not found", out["error"])


class LoadDraftTests(Base):
    def test_loads_copy_and_leaves_original_untouched(self):
        original = make_project(self.folder, "My Project", "Holiday Trip")
        before = snapshot(original)

        out = mcp_server.execute_tool("load_draft", {"draft_id": "My Project"})
        self.assertTrue(out["success"], out)
        res = out["result"]
        new_id = res["draft_id"]
        self.assertNotEqual(new_id, "My Project")
        self.assertEqual(res["name"], "Holiday Trip (AI edit)")
        self.assertEqual(res["working_copy_path"], os.path.join(self.folder, new_id))
        self.assertTrue(os.path.isdir(res["working_copy_path"]))
        with open(os.path.join(res["working_copy_path"], "draft_meta_info.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f)["draft_name"], "Holiday Trip (AI edit)")
        self.assertTrue(mcp_server.is_loaded_draft(new_id))
        self.assertEqual(before, snapshot(original))

    def test_invalid_and_missing_ids_rejected_without_changes(self):
        make_project(self.folder, "My Project", "Holiday Trip")
        os.makedirs(os.path.join(self.folder, "empty folder"))
        outside = make_project(self.tmp, "outside", "Outside")
        before = snapshot(self.tmp)

        bad_ids = [None, "", ".", "..", "../outside", "a/b", outside, "Nope", "empty folder", 123]
        for bad in bad_ids:
            out = mcp_server.execute_tool("load_draft", {"draft_id": bad})
            self.assertFalse(out["success"], f"{bad!r} was accepted")
        out = mcp_server.execute_tool("load_draft", {})
        self.assertFalse(out["success"], "missing draft_id was accepted")
        self.assertEqual(before, snapshot(self.tmp))


if __name__ == "__main__":
    unittest.main(verbosity=2)
