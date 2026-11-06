"""C2.1 deterministic text checks only: no native execution or product imports.

Run isolated: PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -B -m pytest
  -c NUL --noconftest -p no:cacheprovider -s tests/test_offline_b1_native_source.py
Only the five explicitly named sources below are read. No directory scanning,
fixtures, subprocesses, builds, DLL loading, network or target-file access.
Passing checks do not establish C compilation or native runtime correctness.
"""
from hashlib import sha256
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
HEADER = "paper/offline/native/b1_internal.h"
STATE = "paper/offline/native/b1_state.c"
NATIVE = "tests/native/test_b1_state.c"
SELF = "tests/test_offline_b1_native_source.py"
ABI = "paper/offline/native/journal_storage_windows_inspect.h"
NAMED_SOURCES = (HEADER, STATE, NATIVE, SELF, ABI)
INTERNAL_FUNCTIONS = {
    "b1_enter", "b1_primary", "b1_reserve", "b1_acquired",
    "b1_cleanup_next", "b1_released", "b1_finish",
}


def read(name):
    assert name in NAMED_SOURCES
    return (ROOT / name).read_text(encoding="utf-8")


def code(name):
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", read(name), flags=re.S)


def body(name):
    source = code(STATE)
    # Return-type and function name share a line in the implementation.
    match = re.search(r"\b" + re.escape(name) + r"\([^;{}]*\)\s*\{", source)
    assert match, name
    start = match.end()
    depth = 1
    end = start
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end - 1]


def test_exact_internal_scope():
    h, c = code(HEADER), code(STATE)
    declarations = set(re.findall(r"\b(b1_\w+)\s*\([^;{}]*\)\s*;", h))
    definitions = set(re.findall(r"\b(b1_\w+)\s*\([^;{}]*\)\s*\{", c))
    assert declarations == definitions == INTERNAL_FUNCTIONS
    for text in (h, c):
        assert not re.search(r"PTAI_B1_API|__declspec|__cdecl|extern\s|#pragma\s+pack", text)
        assert not re.search(r"\(\s*\*\s*\w+\s*\)", text)  # No callbacks.
        assert "ptai_b1_inspect_v1(" not in text
        assert "ptai_b1_abi_version(" not in text


def test_fixed_capacities_and_mixed_ledger():
    h = code(HEADER)
    assert "#define B1_HANDLE_CAPACITY 64u" in h
    assert "#define B1_DESCRIPTOR_CAPACITY 128u" in h
    assert "#define B1_LEDGER_CAPACITY (B1_HANDLE_CAPACITY + B1_DESCRIPTOR_CAPACITY)" in h
    for field, capacity in (("handles", "HANDLE"), ("descriptors", "DESCRIPTOR"),
                            ("ledger", "LEDGER")):
        assert f"{field}[B1_{capacity}_CAPACITY]" in h
    assert "b1_kind kind; uint32_t index;" in h
    assert "state.count >= B1_LEDGER_CAPACITY" in body("b1_reserve")


def test_frozen_c1_abi_boundary():
    # Exact baseline bytes, including every public declaration/layout assertion.
    assert sha256((ROOT / ABI).read_bytes()).hexdigest() == (
        "7778052d858742417a47a7c1341b6134a7e6b37b156a716422deb4d7f8a98b28"
    )
    for name in (HEADER, STATE):
        assert not re.search(r"#define\s+PTAI_B1_", code(name))
        assert "typedef struct PTAI_B1_" not in code(name)


def test_no_acquisition_or_activation():
    forbidden = (
        r"CreateFile\w*|CloseHandle|LocalFree|Get\w*Security\w*|LoadLibrary\w*|"
        r"GetProcAddress|DllMain|LockFile\w*|sqlite\w*|fopen|freopen|open|"
        r"malloc|calloc|realloc|free|system|popen|WinExec|CreateProcess\w*"
    )
    for name in (HEADER, STATE, NATIVE):
        assert not re.search(r"\b(?:" + forbidden + r")\s*\(", code(name), re.I)
        includes = re.findall(r"#include\s+[<\"]([^>\"]+)", code(name))
        assert set(includes) <= {
            "journal_storage_windows_inspect.h", "stdint.h", "stddef.h",
            "b1_internal.h", "stdatomic.h", "string.h", "assert.h",
            "../../paper/offline/native/b1_internal.h",
        }
    called = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", code(STATE)))
    assert called <= INTERNAL_FUNCTIONS | {
        "slot_at", "owner", "poison", "invalid", "if", "for", "sizeof", "return",
        "_Static_assert", "ATOMIC_VAR_INIT", "memset",
        "atomic_compare_exchange_strong_explicit", "atomic_fetch_or_explicit",
        "atomic_fetch_and_explicit",
    }


def test_nonblocking_gate_poison_precedence():
    c = code(STATE)
    enter = body("b1_enter")
    assert "ATOMIC_INT_LOCK_FREE == 2" in c
    assert enter.count("atomic_compare_exchange_strong_explicit") == 1
    assert "memory_order_acquire" in enter
    assert "(expected & B1_POISONED) ? PTAI_B1_STATUS_POISONED" in enter
    assert "PTAI_B1_STATUS_BUSY" in enter
    assert not re.search(r"\b(for|while|do)\b", enter)
    assert enter.index("atomic_compare_exchange") < enter.index("memset")
    assert "static atomic_uint gate = ATOMIC_VAR_INIT(0u);" in c
    assert "static b1_state state;" in c


def test_no_poison_reset_and_final_release():
    c = code(STATE)
    assert c.count("atomic_fetch_or_explicit(&gate, B1_POISONED, memory_order_release)") == 1
    assert c.count("atomic_fetch_and_explicit(&gate, ~B1_ACTIVE, memory_order_release)") == 1
    assert not re.search(r"atomic_(?:store|init|exchange)\b|~B1_POISONED", c)
    assert body("b1_finish").rstrip().endswith(
        "atomic_fetch_and_explicit(&gate, ~B1_ACTIVE, memory_order_release);\n    return status;"
    )
    assert "if (!owner(c)) return PTAI_B1_STATUS_INTERNAL_ERROR;" in body("b1_finish")
    assert "finalizer" not in code(HEADER).lower()
    assert not re.search(r"\bb1_\w*(?:reset|init|detach)\w*\s*\(", c)


def test_reservation_precedes_outcome_and_blocks_overlap():
    reserve, acquired = body("b1_reserve"), body("b1_acquired")
    assert reserve.index("s->ownership = B1_RESERVED") < reserve.index("state.ledger[state.count++] = r")
    assert "s->ownership != B1_EMPTY" in reserve
    assert "->ownership == B1_RESERVED" in reserve
    assert "s != last || s->ownership != B1_RESERVED" in acquired
    assert "B1_FAILURE_NO_OWNERSHIP" in acquired
    assert "outcome == B1_SUCCESS ? B1_OWNED : B1_UNKNOWN" in acquired
    assert "prior->identity == identity" in acquired
    assert acquired.index("s->identity = identity") < acquired.index("if (!identity)")


def test_reverse_checked_cleanup_and_retention():
    next_release, released = body("b1_cleanup_next"), body("b1_released")
    assert "state.ledger[state.count - 1]" in next_release
    assert "s->ownership = B1_RELEASE_PENDING" in next_release
    assert "if (!owner(c) || state.uncertain) return NULL;" in next_release
    assert "s->ownership != B1_RELEASE_PENDING" in released
    assert released.index("if (outcome == B1_SUCCESS)") < released.index("memset(s, 0")
    assert "s->ownership = B1_RELEASE_FAILED" in released
    failure = released[released.index("s->ownership = B1_RELEASE_FAILED"):]
    assert "memset" not in failure and "--state.count" not in failure
    assert "poison(s->directory_index, op, code)" in failure


def test_unknown_outcome_stops_cleanup():
    acquired = body("b1_acquired")
    unknown = acquired[acquired.index("if (outcome != B1_SUCCESS)"):acquired.index("if (!identity)")]
    assert "b1_primary" in unknown
    assert "poison(s->directory_index, PTAI_B1_OP_NONE, 0)" in unknown
    assert "return;" in unknown
    assert "if (!owner(c) || state.uncertain) return NULL;" in body("b1_cleanup_next")
    assert "b1_acquired(c, s, B1_OUTCOME_UNKNOWN, 0, 0)" in body("b1_finish")
    assert "b1_released(c, B1_OUTCOME_UNKNOWN, 0)" in body("b1_finish")


def test_primary_and_cleanup_diagnostic_precedence():
    assert "state.primary_status) return;" in body("b1_primary")
    finish = body("b1_finish")
    for construct in (
        "state.uncertain ? PTAI_B1_STATUS_CLEANUP_UNCERTAIN : state.primary_status",
        "error->operation = state.primary_operation",
        "error->win32_error = state.primary_code",
        "state.uncertain ? state.uncertain_index : state.primary_index",
        "error->cleanup_operation = state.cleanup_operation",
        "error->cleanup_win32_error = state.cleanup_code",
        "memset(error, 0, sizeof *error)",
    ):
        assert construct in finish
    assert "if (!state.uncertain)" in body("poison")


def test_native_scenario_coverage():
    native = code(NATIVE)
    scenarios = {
        "gate", "mixed", "capacity", "known_failure", "cleanup_only",
        "primary_cleanup", "uncertain_release", "unknown", "primary_unknown",
        "overflow", "descriptor_overflow", "duplicate_slot", "duplicate_identity",
        "unresolved", "double_next", "release_without_attempt",
        "invalid_primary", "duplicate_cleanup_failure", "zero_identity",
    }
    dispatch = native[native.index("int main("):]
    assert set(re.findall(r'strcmp\(argv\[1\], "([a-z_]+)"\)', dispatch)) == scenarios
    assert "last->ownership == B1_EMPTY && last->identity == 0" in native
    assert "assert_permanent_poison" in native
    assert "retained->count == 2" in native
    assert "e.cleanup_operation == PTAI_B1_OP_FREE_DESCRIPTOR" in native
    assert "e.operation == (with_primary ? PTAI_B1_OP_RECHECK : PTAI_B1_OP_SECURITY)" in native
    assert "s->ownership == B1_UNKNOWN && h->ownership == B1_OWNED" in native


def test_python_checks_are_source_only():
    import ast
    tree = ast.parse(read(SELF))
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert imported == {"hashlib", "pathlib", "re", "ast"}
    assert not any(isinstance(node, (ast.AsyncFunctionDef, ast.With)) for node in ast.walk(tree))
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    assert all(not node.decorator_list for node in functions)
    assert all(not node.args.args for node in functions if node.name.startswith("test_"))


def test_contained_internal_errors_allow_checked_cleanup():
    # Structural regression guards only; native execution remains a separate gate.
    assert "b1_primary" in body("invalid")
    assert "poison(" not in body("invalid")
    assert "poison(" not in body("b1_primary")
    native = code(NATIVE)
    contained = native[native.index("static void contained_failure("):native.index("static void invalid_transition(")]
    assert "assert(!retained->uncertain && retained->count == 2)" in contained
    assert contained.index("b1_cleanup_next(&c, &k) == d") < contained.index("b1_cleanup_next(&c, &k) == h")
    assert "b1_finish(&c, &e) == PTAI_B1_STATUS_INTERNAL_ERROR" in contained
    assert "e.directory_index == PTAI_B1_NO_DIRECTORY && !e.poisoned" in contained
    assert "c = begin();" in contained
    assert "assert_permanent_poison" not in contained
    assert "contained_failure(argv[1], 0)" in native
    assert "contained_failure(argv[1], 1)" in native


def test_unreconciled_ownership_still_poisons():
    acquired = body("b1_acquired")
    for start, end in (("if (!s ||", "if (outcome == B1_FAILURE"),
                       ("if (!identity)", "for (i ="),
                       ("if (!prior ||", None)):
        region = acquired[acquired.index(start):acquired.index(end) if end else len(acquired)]
        assert "poison(" in region and "return;" in region
    assert "poison(" in body("b1_finish")
    native = code(NATIVE)
    uncertain = native[native.index("static void invalid_transition("):native.index("int main(")]
    assert "assert_permanent_poison(&c)" in uncertain
    assert "assert(c.state->count && c.state->uncertain)" in uncertain


def test_native_rejects_ndebug():
    native = code(NATIVE)
    assert re.search(r"#ifdef NDEBUG\s*#error[^\n]*\n#endif", native)
    assert native.index("#ifdef NDEBUG") < native.index("#include <assert.h>")
