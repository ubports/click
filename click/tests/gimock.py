# Copyright (C) 2014 Canonical Ltd.
# Author: Colin Watson <cjwatson@ubuntu.com>

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Mock function support based on GObject Introspection.

(Note to reviewers: I expect to rewrite this from scratch on my own time as
a more generalised set of Python modules for unit testing of C code,
although using similar core ideas.  This is a first draft for the purpose of
getting Click's test suite to work expediently, rather than an interface I'm
prepared to commit to long-term.)

Python is a versatile and concise language for writing tests, and GObject
Introspection (GI) makes it straightforward (often trivial) to bind native
code into Python.  However, writing tests for native code quickly runs into
the problem of how to build mock functions.  You might reasonably have code
that calls chown(), for instance, and want to test how it's called rather
than worrying about setting up a fakeroot-type environment where chown()
will work.  The obvious solution is to use `LD_PRELOAD` wrappers, but there
are various problems to overcome in practice:

 * You can only set up a new `LD_PRELOAD` by going through the run-time
   linker; you can't just set it for a single in-process test case.
 * Generating the preloaded wrapper involves a fair bit of boilerplate code.
 * Having to write per-test mock code in C is inconvenient, and makes it
   difficult to get information back out of the mock (such as "how often was
   this function called, and with what arguments?").

The first problem can be solved by a decorator that knows how to run
individual tests in a subprocess.  This is made somewhat more inconvenient
by the fact that there is no way for a context manager's `__enter__` method
to avoid executing the context-managed block other than by throwing an
exception, which makes it hard to silently avoid executing the test case in
the parent process, but we can work around this at the cost of an extra line
of code per invocation.

For the rest, a combination of GI itself and ctypes can help.  We can use GI
to keep track of argument and return types of the mocked C functions in a
reasonably sane way, by parsing header files.  We're operating in the other
direction from how GI is normally used, so PyGObject can't deal with
bridging the two calling conventions for us.  ctypes can: but we still need
to be careful!  We have to construct the callback functions in the child
process, ensure that we keep references to them, and inject function
pointers into the preloaded library via specially-named helper functions;
until those function pointers are set up we must make sure to call the libc
functions instead (since some of them might be called during Python
startup).

The combination of all of this allows us to bridge C functions somewhat
transparently into Python.  This lets you supply a Python function or method
as the mock replacement for a C library function, making it much simpler to
record state.

It's still not perfect:

 * We're using GI in an upside-down kind of way, and we specifically need
   GIR files rather than typelibs so that we can extract the original C
   type, so some fiddling is required for each new function you want to
   mock.

 * The subprocess arrangements are unavoidably slow and it's possible that
   they may cause problems with some test runners.

 * Some C functions (such as `stat`) tend to have multiple underlying entry
   points in the C library which must be preloaded independently.

 * You have to be careful about how your libraries are linked, because `ld
   -Wl,-Bsymbolic-functions` prevents `LD_PRELOAD` working for intra-library
   calls.

 * `ctypes should return composite types from callbacks
   <http://bugs.python.org/issue5710>`_.  The least awful approach for now
   seems to be to construct the composite type in question, stash a
   reference to it forever, and then return a pointer to it as a void *; we
   can only get away with this because tests are by nature relatively
   short-lived.

 * The ctypes module's handling of 64-bit pointers is basically just awful.
   The right answer is probably to use a different callback-generation
   framework entirely (maybe extending PyGObject so that we can get at the
   pieces we need), but I've hacked around it for now.

 * It doesn't appear to be possible to install mock replacements for
   functions that are called directly from Python code using their GI
   wrappers.  You can work around this by simply patching the GI wrapper
   instead, using `mock.patch`.

I think the benefits, in terms of local clarity of tests, are worth the
downsides.
"""

from __future__ import print_function

__metaclass__ = type
__all__ = ['GIMockTestCase']


import contextlib
import ctypes
import fcntl
from functools import partial
import os
import pickle
import shutil
import subprocess
import sys
import tempfile
from textwrap import dedent
import traceback
import unittest
try:
    from unittest import mock
except ImportError:
    import mock
try:
    import xml.etree.cElementTree as etree
except ImportError:
    import xml.etree.ElementTree as etree

from click.tests.gimock_types import Stat, Stat64


# Borrowed from giscanner.girparser.
CORE_NS = "http://www.gtk.org/introspection/core/1.0"
C_NS = "http://www.gtk.org/introspection/c/1.0"
GLIB_NS = "http://www.gtk.org/introspection/glib/1.0"


def _corens(tag):
    return '{%s}%s' % (CORE_NS, tag)


def _glibns(tag):
    return '{%s}%s' % (GLIB_NS, tag)


def _cns(tag):
    return '{%s}%s' % (C_NS, tag)


# Override some c:type annotations that g-ir-scanner gets a bit wrong.
_c_type_override = {
    "passwd*": "struct passwd*",
    "stat*": "struct stat*",
    "stat64*": "struct stat64*",
    }


# Mapping of GI type name -> ctypes type.
_typemap = {
    "GError**": ctypes.c_void_p,
    "gboolean": ctypes.c_int,
    "gint": ctypes.c_int,
    "gint*": ctypes.POINTER(ctypes.c_int),
    "gint32": ctypes.c_int32,
    "gpointer": ctypes.c_void_p,
    "guint": ctypes.c_uint,
    "guint8**": ctypes.POINTER(ctypes.POINTER(ctypes.c_uint8)),
    "guint32": ctypes.c_uint32,
    "none": None,
    "utf8": ctypes.c_char_p,
    "utf8*": ctypes.POINTER(ctypes.c_char_p),
    }


class GIMockTestCase(unittest.TestCase):
    def setUp(self):
        super(GIMockTestCase, self).setUp()
        self._gimock_temp_dir = tempfile.mkdtemp(prefix="gimock")
        self.addCleanup(shutil.rmtree, self._gimock_temp_dir)
        self._preload_func_refs = []
        self._composite_refs = []
        self._delegate_funcs = {}

    def tearDown(self):
        self._preload_func_refs = []
        self._composite_refs = []
        self._delegate_funcs = {}

    def _gir_get_type(self, obj):
        ret = {}
        arrayinfo = obj.find(_corens("array"))
        if arrayinfo is not None:
            typeinfo = arrayinfo.find(_corens("type"))
            raw_ctype = arrayinfo.get(_cns("type"))
        else:
            typeinfo = obj.find(_corens("type"))
            raw_ctype = typeinfo.get(_cns("type"))
        gi_type = typeinfo.get("name")
        if obj.get("direction", "in") == "out":
            gi_type += "*"
        if arrayinfo is not None:
            gi_type += "*"
        ret["gi"] = gi_type
        ret["c"] = _c_type_override.get(raw_ctype, raw_ctype)
        return ret

    def _parse_gir(self, path):
        # A very, very crude GIR parser.  We might have used
        # giscanner.girparser, but it's not importable in Python 3 at the
        # moment.
        tree = etree.parse(path)
        root = tree.getroot()
        assert root.tag == _corens("repository")
        assert root.get("version") == "1.2"
        ns = root.find(_corens("namespace"))
        assert ns is not None
        funcs = {}
        for func in ns.findall(_corens("function")):
            name = func.get(_cns("identifier"))
            # g-ir-scanner skips identifiers starting with "__", which we
            # need in order to mock stat effectively.  Work around this.
            name = name.replace("under_under_", "__")
            headers = None
            for attr in func.findall(_corens("attribute")):
                if attr.get("name") == "headers":
                    headers = attr.get("value")
                    break
            rv = func.find(_corens("return-value"))
            assert rv is not None
            params = []
            paramnode = func.find(_corens("parameters"))
            if paramnode is not None:
                for param in paramnode.findall(_corens("parameter")):
                    params.append({
                        "name": param.get("name"),
                        "type": self._gir_get_type(param),
                        })
            if func.get("throws", "0") == "1":
                params.append({
                    "name": "error",
                    "type": { "gi": "GError**", "c": "GError**" },
                    })
            funcs[name] = {
                "name": name,
                "headers": headers,
                "rv": self._gir_get_type(rv),
                "params": params,
                }
        return funcs

    def _ctypes_type(self, gi_type):
        return _typemap[gi_type["gi"]]

    def make_preloads(self, preloads):
        rpreloads = []
        std_headers = set([
            "dlfcn.h",
            # Not strictly needed, but convenient for ad-hoc debugging.
            "stdio.h",
            "stdint.h",
            "stdlib.h",
            "sys/types.h",
            "unistd.h",
            ])
        preload_headers = set()
        funcs = self._parse_gir("click/tests/preload.gir")
        for name, func in preloads.items():
            info = funcs[name]
            rpreloads.append([info, func])
            headers = info["headers"]
            if headers is not None:
                preload_headers.update(headers.split(","))
        if "GIMOCK_SUBPROCESS" in os.environ:
            return None, rpreloads
        preloads_dir = os.path.join(self._gimock_temp_dir, "_preloads")
        os.makedirs(preloads_dir)
        c_path = os.path.join(preloads_dir, "gimockpreload.c")
        with open(c_path, "w") as c:
            print("#define _GNU_SOURCE", file=c)
            for header in sorted(std_headers | preload_headers):
                print("#include <%s>" % header, file=c)
            print(file=c)
            for info, _ in rpreloads:
                conv = {}
                conv["name"] = info["name"]
                argtypes = [p["type"]["c"] for p in info["params"]]
                argnames = [p["name"] for p in info["params"]]
                conv["ret"] = info["rv"]["c"]
                conv["bareproto"] = ", ".join(argtypes)
                conv["proto"] = ", ".join(
                    "%s %s" % pair for pair in zip(argtypes, argnames))
                conv["args"] = ", ".join(argnames)
                # The delegation scheme used here is needed because trying
                # to pass pointers back and forward through ctypes is a
                # recipe for having them truncated to 32 bits at the drop of
                # a hat.  This approach is less obvious but much safer.
                print(dedent("""\
                    typedef %(ret)s preloadtype_%(name)s (%(bareproto)s);
                    preloadtype_%(name)s *ctypes_%(name)s = (void *) 0;
                    preloadtype_%(name)s *real_%(name)s = (void *) 0;
                    static volatile int delegate_%(name)s = 0;

                    extern void _gimock_init_%(name)s (preloadtype_%(name)s *f)
                    {
                        ctypes_%(name)s = f;
                        if (! real_%(name)s) {
                            /* Retry lookup in case the symbol wasn't
                             * resolvable until the program under test was
                             * loaded.
                             */
                            dlerror ();
                            real_%(name)s = dlsym (RTLD_NEXT, \"%(name)s\");
                            if (dlerror ()) _exit (1);
                        }
                    }
                    """) % conv, file=c)
                if conv["ret"] == "void":
                    print(dedent("""\
                        void %(name)s (%(proto)s)
                        {
                            if (ctypes_%(name)s) {
                                delegate_%(name)s = 0;
                                (*ctypes_%(name)s) (%(args)s);
                                if (! delegate_%(name)s)
                                    return;
                            }
                            (*real_%(name)s) (%(args)s);
                        }
                        """) % conv, file=c)
                else:
                    print(dedent("""\
                        %(ret)s %(name)s (%(proto)s)
                        {
                            if (ctypes_%(name)s) {
                                %(ret)s ret;
                                delegate_%(name)s = 0;
                                ret = (*ctypes_%(name)s) (%(args)s);
                                if (! delegate_%(name)s)
                                    return ret;
                            }
                            return (*real_%(name)s) (%(args)s);
                        }
                        """) % conv, file=c)
                print(dedent("""\
                    extern void _gimock_delegate_%(name)s (void)
                    {
                        delegate_%(name)s = 1;
                    }
                    """) % conv, file=c)
            print(dedent("""\
                static void __attribute__ ((constructor))
                gimockpreload_init (void)
                {
                    dlerror ();
                """), file=c)
            for info, _ in rpreloads:
                name = info["name"]
                print("    real_%s = dlsym (RTLD_NEXT, \"%s\");" %
                      (name, name), file=c)
                print("    if (dlerror ()) _exit (1);", file=c)
            print("}", file=c)
        if "GIMOCK_PRELOAD_DEBUG" in os.environ:
            with open(c_path) as c:
                print(c.read())
        # TODO: Use libtool or similar rather than hardcoding gcc invocation.
        lib_path = os.path.join(preloads_dir, "libgimockpreload.so")
        cflags = subprocess.check_output([
            "pkg-config", "--cflags", "glib-2.0", "gee-0.8"],
            universal_newlines=True).rstrip("\n").split()
        subprocess.check_call([
            "gcc", "-O0", "-g", "-shared", "-fPIC", "-DPIC", "-I", "lib/click",
            ] + cflags + [
            "-Wl,-soname", "-Wl,libgimockpreload.so",
            c_path, "-ldl", "-o", lib_path,
            ])
        return lib_path, rpreloads

    # Use as:
    #   with self.run_in_subprocess("func", ...) as (enter, preloads):
    #       enter()
    #       # test case body; preloads["func"] will be a mock.MagicMock
    #       # instance
    @contextlib.contextmanager
    def run_in_subprocess(self, *patches):
        preloads = {}
        for patch in patches:
            preloads[patch] = mock.MagicMock()
        if preloads:
            lib_path, rpreloads = self.make_preloads(preloads)
        else:
            lib_path, rpreloads = None, None

        class ParentProcess(Exception):
            pass

        def helper(lib_path, rpreloads):
            if "GIMOCK_SUBPROCESS" in os.environ:
                del os.environ["LD_PRELOAD"]
                preload_lib = ctypes.cdll.LoadLibrary(lib_path)
                delegate_cfunctype = ctypes.CFUNCTYPE(None)
                for info, func in rpreloads:
                    signature = [info["rv"]] + [
                        p["type"] for p in info["params"]]
                    signature = [self._ctypes_type(t) for t in signature]
                    cfunctype = ctypes.CFUNCTYPE(*signature)
                    init = getattr(
                        preload_lib, "_gimock_init_%s" % info["name"])
                    cfunc = cfunctype(func)
                    self._preload_func_refs.append(cfunc)
                    init(cfunc)
                    delegate = getattr(
                        preload_lib, "_gimock_delegate_%s" % info["name"])
                    self._delegate_funcs[info["name"]] = delegate_cfunctype(
                        delegate)
                return
            rfd, wfd = os.pipe()
            # It would be cleaner to use subprocess.Popen(pass_fds=[wfd]), but
            # that isn't available in Python 2.7.
            if hasattr(os, "set_inheritable"):
                os.set_inheritable(wfd, True)
            else:
                fcntl.fcntl(rfd, fcntl.F_SETFD, fcntl.FD_CLOEXEC)
            args = [
                sys.executable, "-m", "unittest",
                "%s.%s.%s" % (
                    self.__class__.__module__, self.__class__.__name__,
                    self._testMethodName)]
            env = os.environ.copy()
            env["GIMOCK_SUBPROCESS"] = str(wfd)
            if lib_path is not None:
                env["LD_PRELOAD"] = lib_path
            subp = subprocess.Popen(args, close_fds=False, env=env)
            os.close(wfd)
            reader = os.fdopen(rfd, "rb")
            subp.communicate()
            exctype = pickle.load(reader)
            if exctype is not None and issubclass(exctype, AssertionError):
                raise AssertionError("Subprocess failed a test!")
            elif exctype is not None or subp.returncode != 0:
                raise Exception("Subprocess returned an error!")
            reader.close()
            raise ParentProcess()

        try:
            yield partial(helper, lib_path, rpreloads), preloads
            if "GIMOCK_SUBPROCESS" in os.environ:
                wfd = int(os.environ["GIMOCK_SUBPROCESS"])
                writer = os.fdopen(wfd, "wb")
                pickle.dump(None, writer)
                writer.flush()
                os._exit(0)
        except ParentProcess:
            pass
        except Exception as e:
            if "GIMOCK_SUBPROCESS" in os.environ:
                wfd = int(os.environ["GIMOCK_SUBPROCESS"])
                writer = os.fdopen(wfd, "wb")
                # It would be better to use tblib to pickle the traceback so
                # that we can re-raise it properly from the parent process.
                # Until that's packaged and available to us, just print the
                # traceback and send the exception type.
                print()
                traceback.print_exc()
                pickle.dump(type(e), writer)
                writer.flush()
                os._exit(1)
            else:
                raise

    def make_pointer(self, composite):
        # Store a reference to a composite type and return a pointer to it,
        # working around http://bugs.python.org/issue5710.
        self._composite_refs.append(composite)
        return ctypes.addressof(composite)

    def make_string(self, s):
        # As make_pointer, but for a string.
        copied = ctypes.create_string_buffer(s.encode())
        self._composite_refs.append(copied)
        return ctypes.addressof(copied)

    def convert_pointer(self, composite_type, address):
        # Return a ctypes composite type instance at a given address.
        return composite_type.from_address(address)

    def convert_stat_pointer(self, name, address):
        # As convert_pointer, but for a "struct stat *" or "struct stat64 *"
        # depending on the wrapped function name.
        stat_type = {"__xstat": Stat, "__xstat64": Stat64}
        return self.convert_pointer(stat_type[name], address)

    def delegate_to_original(self, name):
        # Cause the wrapper function to delegate to the original version
        # after the callback returns.  (Note that the callback still needs
        # to return something type-compatible with the declared result type,
        # although the return value will otherwise be ignored.)
        self._delegate_funcs[name]()
