from __future__ import print_function

import os
import sys

from click.tests import config


def _append_env_path(envname, value):
    if envname in os.environ:
        if value in os.environ[envname].split(":"):
            return False
        os.environ[envname] = "%s:%s" % (os.environ[envname], value)
    else:
        os.environ[envname] = value
    return True


# Don't do any of this in interactive mode.
if not hasattr(sys, "ps1"):
    _lib_click_dir = os.path.join(config.abs_top_builddir, "lib", "click")
    changed = False
    if _append_env_path(
            "LD_LIBRARY_PATH", os.path.join(_lib_click_dir, ".libs")):
        changed = True
    if _append_env_path("GI_TYPELIB_PATH", _lib_click_dir):
        changed = True
    if changed:
        # We have to re-exec ourselves to get the dynamic loader to pick up
        # the new value of LD_LIBRARY_PATH.
        if "-m unittest" in sys.argv[0]:
            # unittest does horrible things to sys.argv in the name of
            # "usefulness", making the re-exec more painful than it needs to
            # be.
            os.execvp(
                sys.executable, [sys.executable, "-m", "unittest"] + sys.argv[1:])
        else:
            os.execvp(sys.executable, [sys.executable] + sys.argv)
        os._exit(1)
