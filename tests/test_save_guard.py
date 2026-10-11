"""Checks that save_draft refuses existing destinations without touching them.

Uses only temporary folders; never touches the real CapCut Projects folder and
never writes a draft.
"""
import hashlib
import os
import shutil
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)
os.chdir(REPO)

from draft_cache import DRAFT_CACHE  # noqa: E402
from save_draft_impl import save_draft_impl, save_draft_background  # noqa: E402
from save_task_cache import create_task, get_task_status  # noqa: E402
import mcp_server  # noqa: E402

REAL_FOLDER = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")


def snapshot(root):
    """Path -> (size, mtime_ns, sha256) for every entry, plus the root's own stat."""
    st = os.lstat(root)
    snap = {".": (st.st_mode, st.st_mtime_ns)}
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            p = os.path.join(dirpath, name)
            st = os.lstat(p)
            digest = None
            if os.path.isfile(p) and not os.path.islink(p):
                with open(p, "rb") as f:
                    digest = hashlib.sha256(f.read()).hexdigest()
            snap[os.path.relpath(p, root)] = (st.st_mode, st.st_size, st.st_mtime_ns, digest)
    return snap


def make_existing_draft(parent, draft_id):
    d = os.path.join(parent, draft_id)
    os.makedirs(os.path.join(d, "Resources"))
    with open(os.path.join(d, "draft_content.json"), "w") as f:
        f.write('{"precious": true}')
    with open(os.path.join(d, "Resources", "clip.mp4"), "wb") as f:
        f.write(os.urandom(4096))
    return d


class SaveGuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="capcut_save_guard_")
        self.real_before = snapshot(REAL_FOLDER) if os.path.isdir(REAL_FOLDER) else None

    def tearDown(self):
        shutil.rmtree(self.tmp)
        if self.real_before is not None:
            self.assertEqual(self.real_before, snapshot(REAL_FOLDER), "real CapCut folder changed")

    def test_existing_folder_refused_and_untouched(self):
        draft_id = "dfd_cat_test_existing"
        d = make_existing_draft(self.tmp, draft_id)
        DRAFT_CACHE[draft_id] = object()  # cached, so the old code would have proceeded to rmtree
        before = snapshot(d)
        result = save_draft_impl(draft_id, self.tmp)
        self.assertFalse(result["success"])
        self.assertIn("already exists", result["error"])
        self.assertEqual(before, snapshot(d))

    def test_background_guard_also_refuses(self):
        draft_id = "dfd_cat_test_background"
        d = make_existing_draft(self.tmp, draft_id)
        DRAFT_CACHE[draft_id] = object()
        before = snapshot(d)
        create_task(draft_id)
        save_draft_background(draft_id, self.tmp, draft_id)
        self.assertEqual(get_task_status(draft_id)["status"], "failed")
        self.assertEqual(before, snapshot(d))

    def test_symlink_destination_refused(self):
        target = make_existing_draft(self.tmp, "real_target")
        os.symlink(target, os.path.join(self.tmp, "dfd_cat_test_link"))
        before = snapshot(target)
        result = save_draft_impl("dfd_cat_test_link", self.tmp)
        self.assertFalse(result["success"])
        self.assertTrue(os.path.islink(os.path.join(self.tmp, "dfd_cat_test_link")))
        self.assertEqual(before, snapshot(target))

    def test_invalid_ids_refused(self):
        make_existing_draft(self.tmp, "sibling")
        before = snapshot(self.tmp)
        for bad in ["", ".", "..", "a/b", "../x", "/abs"]:
            result = save_draft_impl(bad, self.tmp)
            self.assertFalse(result["success"], bad)
        self.assertEqual(before, snapshot(self.tmp))

    def test_mcp_tool_reports_failure_for_existing(self):
        draft_id = "dfd_cat_test_mcp"
        d = make_existing_draft(self.tmp, draft_id)
        DRAFT_CACHE[draft_id] = object()
        before = snapshot(d)
        out = mcp_server.execute_tool("save_draft", {"draft_id": draft_id, "draft_folder": self.tmp})
        self.assertFalse(out["success"])
        self.assertIn("already exists", out["error"])
        self.assertEqual(before, snapshot(d))

    def test_mcp_tool_reports_failure_for_unknown_id(self):
        before = snapshot(self.tmp)
        out = mcp_server.execute_tool("save_draft", {"draft_id": "dfd_cat_not_in_cache", "draft_folder": self.tmp})
        self.assertFalse(out["success"])
        self.assertEqual(before, snapshot(self.tmp))


if __name__ == "__main__":
    unittest.main(verbosity=2)
