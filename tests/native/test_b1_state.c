/* Synthetic source ONLY; not executed or compiled by source checks.
 * Future harness: invoke a fresh process once for EACH named scenario below.
 * There is deliberately no singleton reset, even in tests.
 * Integer identities never represent real OS handles or allocations. */
#include "../../paper/offline/native/b1_internal.h"
/* Assertions contain protocol operations: disabling them is unsupported. */
#ifdef NDEBUG
#error Native scenarios require assertions enabled; NDEBUG is forbidden.
#endif
#include <assert.h>
#include <string.h>

static b1_call begin(void)
{
    b1_call c = {0};
    assert(b1_enter(&c) == PTAI_B1_STATUS_OK);
    return c; /* Transfer this sole token; do not use the original again. */
}
static b1_slot *add(b1_call *c, b1_kind kind, uint32_t slot,
                    uint32_t directory, uintptr_t identity)
{
    b1_slot *s = b1_reserve(c, kind, slot, directory,
        kind == B1_HANDLE ? PTAI_B1_OP_OPEN_DIRECTORY : PTAI_B1_OP_SECURITY);
    assert(s);
    b1_acquired(c, s, B1_SUCCESS, identity, 0);
    assert(s->ownership == B1_OWNED);
    return s;
}
static void gate_and_preacquisition(void)
{
    b1_call c = begin(), rejected = {0};
    PTAI_B1_ERROR_V1 e;
    assert(b1_enter(&rejected) == PTAI_B1_STATUS_BUSY);
    assert(!rejected.owns_gate && !rejected.state);
    assert(b1_finish(&rejected, &e) == PTAI_B1_STATUS_INTERNAL_ERROR);
    assert(b1_enter(&rejected) == PTAI_B1_STATUS_BUSY);
    b1_primary(&c, PTAI_B1_STATUS_INVALID_ARGUMENT, PTAI_B1_OP_VALIDATE, 0,
               PTAI_B1_NO_DIRECTORY);
    assert(b1_finish(&c, &e) == PTAI_B1_STATUS_INVALID_ARGUMENT);
    assert(e.directory_index == PTAI_B1_NO_DIRECTORY && !e.poisoned);
    assert(b1_finish(&c, &e) == PTAI_B1_STATUS_INTERNAL_ERROR);
    c = begin();
    assert(b1_finish(&c, &e) == PTAI_B1_STATUS_OK);
}
static void mixed_reverse_cleanup(void)
{
    b1_call c = begin();
    b1_kind k;
    PTAI_B1_ERROR_V1 e;
    b1_slot *h = add(&c, B1_HANDLE, 0, 0, 101);
    b1_slot *d = add(&c, B1_DESCRIPTOR, 0, 0, 201);
    b1_slot *h2 = add(&c, B1_HANDLE, 1, 1, 102);
    assert(b1_cleanup_next(&c, &k) == h2 && k == B1_HANDLE);
    assert(h2->ownership == B1_RELEASE_PENDING && h2->identity == 102);
    b1_released(&c, B1_SUCCESS, 0);
    assert(h2->ownership == B1_EMPTY);
    assert(b1_cleanup_next(&c, &k) == d && k == B1_DESCRIPTOR);
    b1_released(&c, B1_SUCCESS, 0);
    assert(b1_cleanup_next(&c, &k) == h && k == B1_HANDLE);
    b1_released(&c, B1_SUCCESS, 0);
    assert(!b1_cleanup_next(&c, &k));
    assert(b1_finish(&c, &e) == PTAI_B1_STATUS_OK);
    assert(e.operation == PTAI_B1_OP_NONE && !e.cleanup_operation);
}
static void capacity_boundaries(void)
{
    b1_call c = begin();
    b1_kind k;
    PTAI_B1_ERROR_V1 e;
    uint32_t i;
    for (i = 0; i < B1_HANDLE_CAPACITY; ++i) add(&c, B1_HANDLE, i, i, 1000 + i);
    for (i = 0; i < B1_DESCRIPTOR_CAPACITY; ++i)
        add(&c, B1_DESCRIPTOR, i, i / 2, 2000 + i);
    assert(c.state->count == B1_LEDGER_CAPACITY);
    for (i = B1_DESCRIPTOR_CAPACITY; i > 0; --i) {
        assert(b1_cleanup_next(&c, &k)->identity == 2000 + i - 1);
        assert(k == B1_DESCRIPTOR);
        b1_released(&c, B1_SUCCESS, 0);
    }
    for (i = B1_HANDLE_CAPACITY; i > 0; --i) {
        assert(b1_cleanup_next(&c, &k)->identity == 1000 + i - 1);
        assert(k == B1_HANDLE);
        b1_released(&c, B1_SUCCESS, 0);
    }
    assert(b1_finish(&c, &e) == PTAI_B1_STATUS_OK);
}
static void assert_permanent_poison(b1_call *c)
{
    b1_call rejected = {0};
    PTAI_B1_ERROR_V1 e;
    assert(b1_enter(&rejected) == PTAI_B1_STATUS_POISONED); /* Even active. */
    assert(!rejected.owns_gate && !rejected.state);
    assert(b1_finish(&rejected, &e) == PTAI_B1_STATUS_INTERNAL_ERROR);
    assert(b1_finish(c, &e) == PTAI_B1_STATUS_CLEANUP_UNCERTAIN);
    assert(e.poisoned == 1);
    assert(b1_enter(&rejected) == PTAI_B1_STATUS_POISONED);
    assert(b1_enter(c) == PTAI_B1_STATUS_POISONED); /* Reinitialized token only. */
    assert(b1_enter(c) == PTAI_B1_STATUS_POISONED);
}
static void cleanup_failure(int with_primary, b1_outcome outcome)
{
    b1_call c = begin();
    b1_kind k;
    PTAI_B1_ERROR_V1 e;
    b1_state *retained = c.state;
    b1_slot *h = add(&c, B1_HANDLE, 0, 0, 101);
    b1_slot *d = add(&c, B1_DESCRIPTOR, 0, 1, 201);
    b1_slot *last = add(&c, B1_HANDLE, 1, 1, 102);
    if (with_primary) {
        b1_primary(&c, PTAI_B1_STATUS_CHANGED, PTAI_B1_OP_RECHECK, 91, 2);
        b1_primary(&c, PTAI_B1_STATUS_OS_ERROR, PTAI_B1_OP_DIRECTORY_INFO, 92, 3);
    }
    assert(b1_cleanup_next(&c, &k) == last && k == B1_HANDLE);
    b1_released(&c, B1_SUCCESS, 0);
    assert(last->ownership == B1_EMPTY && last->identity == 0);
    assert(b1_cleanup_next(&c, &k) == d && k == B1_DESCRIPTOR);
    b1_released(&c, outcome, 73);
    assert(d->ownership == B1_RELEASE_FAILED && h->ownership == B1_OWNED);
    assert(!b1_cleanup_next(&c, &k));
    b1_released(&c, B1_SUCCESS, 0); /* Cannot retry or erase ownership. */
    assert(retained->count == 2 && d->identity == 201 && h->identity == 101);
    assert(b1_finish(&c, &e) == PTAI_B1_STATUS_CLEANUP_UNCERTAIN);
    assert(e.directory_index == 1 && e.cleanup_operation == PTAI_B1_OP_FREE_DESCRIPTOR);
    assert(e.cleanup_win32_error == 73 && e.poisoned == 1);
    assert(e.operation == (with_primary ? PTAI_B1_OP_RECHECK : PTAI_B1_OP_NONE));
    assert(e.win32_error == (with_primary ? 91u : 0u));
    assert(retained->count == 2 && d->ownership == B1_RELEASE_FAILED);
    assert(b1_enter(&c) == PTAI_B1_STATUS_POISONED);
}
static void unknown_acquisition(int with_primary)
{
    b1_call c = begin();
    b1_kind k;
    PTAI_B1_ERROR_V1 e;
    b1_slot *h = add(&c, B1_HANDLE, 0, 0, 101);
    b1_slot *s = b1_reserve(&c, B1_DESCRIPTOR, 0, 3, PTAI_B1_OP_SECURITY);
    assert(s);
    if (with_primary)
        b1_primary(&c, PTAI_B1_STATUS_CHANGED, PTAI_B1_OP_RECHECK, 91, 2);
    b1_acquired(&c, s, B1_OUTCOME_UNKNOWN, 0, 61);
    assert(s->ownership == B1_UNKNOWN && h->ownership == B1_OWNED);
    assert(!b1_cleanup_next(&c, &k));
    assert(b1_finish(&c, &e) == PTAI_B1_STATUS_CLEANUP_UNCERTAIN);
    assert(e.operation == (with_primary ? PTAI_B1_OP_RECHECK : PTAI_B1_OP_SECURITY));
    assert(e.win32_error == (with_primary ? 91u : 61u));
    assert(e.directory_index == 3 && e.cleanup_operation == PTAI_B1_OP_NONE);
    assert(e.cleanup_win32_error == 0 && e.poisoned == 1);
    assert(b1_enter(&c) == PTAI_B1_STATUS_POISONED);
}
static void known_failure(void)
{
    b1_call c = begin();
    b1_kind k;
    PTAI_B1_ERROR_V1 e;
    b1_slot *h = add(&c, B1_HANDLE, 0, 0, 101);
    b1_slot *d = b1_reserve(&c, B1_DESCRIPTOR, 0, 0, PTAI_B1_OP_SECURITY);
    b1_acquired(&c, d, B1_FAILURE_NO_OWNERSHIP, 0, 55);
    b1_primary(&c, PTAI_B1_STATUS_CHANGED, PTAI_B1_OP_RECHECK, 99, 1);
    assert(d->ownership == B1_EMPTY && c.state->count == 1);
    assert(b1_cleanup_next(&c, &k) == h);
    b1_released(&c, B1_SUCCESS, 0);
    assert(b1_finish(&c, &e) == PTAI_B1_STATUS_OS_ERROR);
    assert(e.operation == PTAI_B1_OP_SECURITY && e.win32_error == 55 && !e.poisoned);
}
static void contained_failure(const char *which, int fail_cleanup)
{
    b1_call c = begin();
    b1_kind k;
    PTAI_B1_ERROR_V1 e;
    b1_state *retained = c.state;
    b1_slot *h = add(&c, B1_HANDLE, 0, 0, 101);
    b1_slot *d = add(&c, B1_DESCRIPTOR, 0, 1, 201);
    if (!strcmp(which, "overflow")) {
        assert(!b1_reserve(&c, B1_HANDLE, B1_HANDLE_CAPACITY, 0, PTAI_B1_OP_OPEN_DIRECTORY));
    } else if (!strcmp(which, "descriptor_overflow")) {
        assert(!b1_reserve(&c, B1_DESCRIPTOR, B1_DESCRIPTOR_CAPACITY, 0, PTAI_B1_OP_SECURITY));
    } else if (!strcmp(which, "invalid_primary")) {
        b1_primary(&c, PTAI_B1_STATUS_OK, PTAI_B1_OP_VALIDATE, 99, 0);
    } else if (!strcmp(which, "release_without_attempt")) {
        b1_released(&c, B1_SUCCESS, 0);
    } else {
        assert(!b1_reserve(&c, B1_HANDLE, 0, 0, PTAI_B1_OP_OPEN_DIRECTORY));
    }
    assert(retained->primary_status == PTAI_B1_STATUS_INTERNAL_ERROR);
    assert(!retained->uncertain && retained->count == 2);
    assert(h->ownership == B1_OWNED && d->ownership == B1_OWNED);
    b1_primary(&c, PTAI_B1_STATUS_CHANGED, PTAI_B1_OP_RECHECK, 91, 3);
    assert(b1_cleanup_next(&c, &k) == d && k == B1_DESCRIPTOR);
    b1_released(&c, fail_cleanup ? B1_OUTCOME_UNKNOWN : B1_SUCCESS, 73);
    if (fail_cleanup) {
        assert(!b1_cleanup_next(&c, &k));
        assert(retained->count == 2 && h->ownership == B1_OWNED);
        assert(d->ownership == B1_RELEASE_FAILED && d->identity == 201);
        assert(b1_finish(&c, &e) == PTAI_B1_STATUS_CLEANUP_UNCERTAIN);
        assert(e.poisoned && e.directory_index == 1);
        assert(e.cleanup_operation == PTAI_B1_OP_FREE_DESCRIPTOR && e.cleanup_win32_error == 73);
        assert(e.operation == PTAI_B1_OP_NONE && e.win32_error == 0);
        assert(b1_enter(&c) == PTAI_B1_STATUS_POISONED);
        return;
    }
    assert(d->ownership == B1_EMPTY && d->identity == 0);
    assert(b1_cleanup_next(&c, &k) == h && k == B1_HANDLE);
    b1_released(&c, B1_SUCCESS, 0);
    assert(h->ownership == B1_EMPTY && retained->count == 0);
    assert(!b1_cleanup_next(&c, &k));
    assert(b1_finish(&c, &e) == PTAI_B1_STATUS_INTERNAL_ERROR);
    assert(e.operation == PTAI_B1_OP_NONE && e.win32_error == 0);
    assert(e.directory_index == PTAI_B1_NO_DIRECTORY && !e.poisoned);
    assert(e.cleanup_operation == PTAI_B1_OP_NONE && e.cleanup_win32_error == 0);
    c = begin(); /* Successful checked cleanup permits the next call. */
    assert(b1_finish(&c, &e) == PTAI_B1_STATUS_OK);
}
static void invalid_transition(const char *which)
{
    b1_call c = begin();
    b1_kind k;
    b1_slot *s;
    if (!strcmp(which, "duplicate_identity")) {
        add(&c, B1_HANDLE, 0, 0, 101);
        add(&c, B1_HANDLE, 1, 1, 101);
        assert(c.state->count == 2 && c.state->handles[0].identity == 101);
    } else if (!strcmp(which, "zero_identity")) {
        s = b1_reserve(&c, B1_HANDLE, 0, 0, PTAI_B1_OP_OPEN_DIRECTORY);
        assert(s);
        b1_acquired(&c, s, B1_SUCCESS, 0, 0);
        assert(s->ownership == B1_OWNED && c.state->count == 1);
    } else if (!strcmp(which, "unresolved")) {
        s = b1_reserve(&c, B1_HANDLE, 0, 0, PTAI_B1_OP_OPEN_DIRECTORY);
        assert(s && s->ownership == B1_RESERVED);
        assert(!b1_cleanup_next(&c, &k));
    } else {
        add(&c, B1_HANDLE, 0, 0, 101);
        assert(b1_cleanup_next(&c, &k));
        assert(!b1_cleanup_next(&c, &k));
    }
    assert(c.state->count && c.state->uncertain);
    assert(!b1_cleanup_next(&c, &k));
    assert_permanent_poison(&c);
}
int main(int argc, char **argv)
{
    if (argc != 2) return 2;
    if (!strcmp(argv[1], "gate")) gate_and_preacquisition();
    else if (!strcmp(argv[1], "mixed")) mixed_reverse_cleanup();
    else if (!strcmp(argv[1], "capacity")) capacity_boundaries();
    else if (!strcmp(argv[1], "known_failure")) known_failure();
    else if (!strcmp(argv[1], "cleanup_only")) cleanup_failure(0, B1_FAILURE_NO_OWNERSHIP);
    else if (!strcmp(argv[1], "primary_cleanup")) cleanup_failure(1, B1_FAILURE_NO_OWNERSHIP);
    else if (!strcmp(argv[1], "uncertain_release")) cleanup_failure(1, B1_OUTCOME_UNKNOWN);
    else if (!strcmp(argv[1], "unknown")) unknown_acquisition(0);
    else if (!strcmp(argv[1], "primary_unknown")) unknown_acquisition(1);
    else if (!strcmp(argv[1], "overflow") || !strcmp(argv[1], "descriptor_overflow") ||
             !strcmp(argv[1], "duplicate_slot") || !strcmp(argv[1], "invalid_primary") ||
             !strcmp(argv[1], "release_without_attempt")) contained_failure(argv[1], 0);
    else if (!strcmp(argv[1], "duplicate_cleanup_failure")) contained_failure(argv[1], 1);
    else if (!strcmp(argv[1], "duplicate_identity") || !strcmp(argv[1], "zero_identity") ||
             !strcmp(argv[1], "unresolved") || !strcmp(argv[1], "double_next")) invalid_transition(argv[1]);
    else return 2;
    return 0;
}
