"""
Load an existing CapCut project so it can be edited with the add_* tools.

Design goals (safety first):
- We NEVER modify the user's original project. load_draft makes a full copy of
  the draft folder (assets, metadata, everything) and edits the copy.
- The copy is re-tagged in draft_meta_info.json with a fresh draft_id / name /
  path so CapCut treats it as a separate project.
- Saving writes the updated timeline (draft_info.json) back into the copy folder
  in place, preserving every other file.

Exposed helpers:
- list_existing_drafts(draft_folder=None)
- load_existing_draft(draft_id, draft_folder=None, new_name=None)
- save_loaded_draft(draft_id)
- is_loaded_draft(draft_id)
"""

import os
import time
import json
import uuid
import shutil

from pyJianYingDraft.script_file import Script_file
from draft_cache import DRAFT_CACHE, update_cache
from draft_profiles import get_draft_profile

# new_draft_id -> absolute path of the working-copy folder
LOADED_DRAFTS = {}


def _default_folder():
    return os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "CapCut", "User Data", "Projects", "com.lveditor.draft",
    )


def is_loaded_draft(draft_id):
    """True if this draft_id is an in-place (template-mode) draft we loaded."""
    if draft_id in LOADED_DRAFTS:
        return True
    script = DRAFT_CACHE.get(draft_id)
    return bool(script is not None and getattr(script, "save_path", None))


def list_existing_drafts(draft_folder=None):
    """List the projects currently in the CapCut Projects folder."""
    draft_folder = draft_folder or _default_folder()
    if not os.path.isdir(draft_folder):
        return {"success": False, "error": f"Draft folder not found: {draft_folder}"}
    profile = get_draft_profile()
    drafts = []
    for name in os.listdir(draft_folder):
        d = os.path.join(draft_folder, name)
        if not os.path.isdir(d):
            continue
        has_content = os.path.exists(os.path.join(d, profile.content_file))
        meta_name = name
        meta_path = os.path.join(d, "draft_meta_info.json")
        try:
            if os.path.exists(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                meta_name = meta.get("draft_name", name)
        except Exception:
            pass
        drafts.append({
            "folder": name,
            "name": meta_name,
            "editable": has_content,
        })
    return {"success": True, "draft_folder": draft_folder, "drafts": drafts}


def _read_meta(folder):
    meta_path = os.path.join(folder, "draft_meta_info.json")
    if not os.path.exists(meta_path):
        return None, None
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f), meta_path


def _retag_copy_meta(folder, new_meta_draft_id, new_name):
    """Make the copied folder look like its own CapCut project."""
    meta, meta_path = _read_meta(folder)
    if meta is None:
        return
    now_us = int(time.time() * 1_000_000)
    fold_path = folder.replace("\\", "/")
    root_path = os.path.dirname(folder).replace("\\", "/")
    meta["draft_id"] = new_meta_draft_id
    meta["draft_name"] = new_name
    meta["draft_fold_path"] = fold_path
    meta["draft_root_path"] = root_path
    meta["tm_draft_create"] = now_us
    meta["tm_draft_modified"] = now_us
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


def _touch_meta(folder, script):
    meta, meta_path = _read_meta(folder)
    if meta is None:
        return
    meta["tm_draft_modified"] = int(time.time() * 1_000_000)
    if getattr(script, "duration", None):
        meta["tm_duration"] = int(script.duration)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)


def load_existing_draft(draft_id, draft_folder=None, new_name=None):
    """Open an existing CapCut project as an editable copy.

    :param draft_id: folder name of the project inside the CapCut Projects dir.
    :param draft_folder: override the Projects dir (defaults to CapCut's).
    :param new_name: name for the working copy (defaults to '<original> (AI edit)').
    :return: dict with the NEW draft_id to use for subsequent add_* / save_draft calls.
    """
    draft_folder = draft_folder or _default_folder()
    src = os.path.join(draft_folder, draft_id)
    if not os.path.isdir(src):
        return {"success": False, "error": f"Project '{draft_id}' not found in {draft_folder}"}

    profile = get_draft_profile()
    content_path = os.path.join(src, profile.content_file)
    if not os.path.exists(content_path):
        return {"success": False,
                "error": f"'{draft_id}' has no {profile.content_file}; it may be an incompatible draft format."}

    # Determine original name
    orig_name = draft_id
    meta, _ = _read_meta(src)
    if meta and meta.get("draft_name"):
        orig_name = meta["draft_name"]

    # Create a fresh working copy (folder + ids) so the original is never touched
    new_id = f"dfd_cat_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    dst = os.path.join(draft_folder, new_id)
    if os.path.exists(dst):
        return {"success": False, "error": f"Working-copy folder already exists: {dst}"}
    shutil.copytree(src, dst)

    try:
        script = Script_file.load_template(os.path.join(dst, profile.content_file))
    except Exception as e:
        # roll back the copy on load failure
        shutil.rmtree(dst, ignore_errors=True)
        return {"success": False, "error": f"Failed to parse draft: {e}"}

    update_cache(new_id, script)
    LOADED_DRAFTS[new_id] = dst

    final_name = new_name or f"{orig_name} (AI edit)"
    _retag_copy_meta(dst, str(uuid.uuid4()).upper(), final_name)

    return {
        "success": True,
        "draft_id": new_id,
        "name": final_name,
        "source_draft_id": draft_id,
        "source_name": orig_name,
        "working_copy_path": dst,
        "imported_tracks": len(script.imported_tracks),
        "duration_seconds": round((getattr(script, "duration", 0) or 0) / 1_000_000, 2),
        "note": "Editing a COPY. The original project is untouched. "
                "Use this draft_id for add_* tools and save_draft.",
    }


def save_loaded_draft(draft_id):
    """Save edits to a loaded draft in place (preserves all other project files)."""
    script = DRAFT_CACHE.get(draft_id)
    if script is None:
        return {"success": False, "error": f"Draft {draft_id} is not in the cache."}
    if not getattr(script, "save_path", None):
        return {"success": False, "error": f"{draft_id} is not a loaded draft; use the normal save."}
    script.save()
    folder = LOADED_DRAFTS.get(draft_id) or os.path.dirname(script.save_path)
    _touch_meta(folder, script)
    return {"success": True, "saved_to": folder}
