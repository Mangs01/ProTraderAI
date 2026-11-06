/* C1: Entry validation/status precedence; Resource ownership/cleanup/poison.
 * Process-lifetime singleton, no initialization/reset/finalizer/detach API.
 * C11 lock-free unsigned atomics are required; no library-backed waiting gate.
 * One strong CAS decides entry. Acquire synchronizes with the previous owner's
 * release. Failed CAS uses acquire and its observed value: poison before busy.
 * Poison is release-published while active; the last release RMW clears ONLY
 * active. No operation can clear poison. Rejected calls touch no bookkeeping.
 */
#include "b1_internal.h"
#include <stdatomic.h>
#include <string.h>
_Static_assert(ATOMIC_INT_LOCK_FREE == 2, "nonblocking gate required");
static atomic_uint gate = ATOMIC_VAR_INIT(0u);
static b1_state state;

static b1_slot *slot_at(b1_record r)
{
    if (r.kind == B1_HANDLE && r.index < B1_HANDLE_CAPACITY)
        return &state.handles[r.index];
    if (r.kind == B1_DESCRIPTOR && r.index < B1_DESCRIPTOR_CAPACITY)
        return &state.descriptors[r.index];
    return NULL;
}
static int owner(const b1_call *c)
{
    return c && c->owns_gate == 1u && c->state == &state;
}
static void poison(uint32_t index, uint32_t operation, uint32_t code)
{
    if (!state.uncertain) {
        state.uncertain = 1u;
        state.uncertain_index = index;
        state.cleanup_operation = operation;
        state.cleanup_code = code;
    }
    atomic_fetch_or_explicit(&gate, B1_POISONED, memory_order_release);
}
static void invalid(b1_call *c)
{
    b1_primary(c, PTAI_B1_STATUS_INTERNAL_ERROR, PTAI_B1_OP_NONE, 0,
               PTAI_B1_NO_DIRECTORY);
    /* A contained error does not make known ownership uncertain. */
}
uint32_t b1_enter(b1_call *c)
{
    unsigned expected = 0u;
    if (!c || c->owns_gate || c->state) return PTAI_B1_STATUS_INTERNAL_ERROR;
    if (!atomic_compare_exchange_strong_explicit(&gate, &expected, B1_ACTIVE,
                                                 memory_order_acquire,
                                                 memory_order_acquire))
        return (expected & B1_POISONED) ? PTAI_B1_STATUS_POISONED :
                                         PTAI_B1_STATUS_BUSY;
    /* Only a successfully entered, unpoisoned, empty singleton is reusable. */
    c->state = &state;
    c->owns_gate = 1u;
    if (state.count) {
        /* Leftover ownership at entry cannot be attributed to this call. */
        invalid(c);
        poison(PTAI_B1_NO_DIRECTORY, PTAI_B1_OP_NONE, 0);
        return PTAI_B1_STATUS_OK;
    }
    memset(&state, 0, sizeof state);
    state.primary_index = PTAI_B1_NO_DIRECTORY;
    state.uncertain_index = PTAI_B1_NO_DIRECTORY;
    return PTAI_B1_STATUS_OK; /* Owner must finish, including early exits. */
}
void b1_primary(b1_call *c, uint32_t status, uint32_t op,
                uint32_t code, uint32_t index)
{
    if (!owner(c) || state.primary_status) return;
    if (status == PTAI_B1_STATUS_OK || status > PTAI_B1_STATUS_INTERNAL_ERROR ||
        status == PTAI_B1_STATUS_CLEANUP_UNCERTAIN ||
        status == PTAI_B1_STATUS_POISONED || status == PTAI_B1_STATUS_BUSY ||
        op > PTAI_B1_OP_SERIALIZE ||
        (index >= B1_HANDLE_CAPACITY && index != PTAI_B1_NO_DIRECTORY)) {
        state.primary_status = PTAI_B1_STATUS_INTERNAL_ERROR;
        state.primary_index = PTAI_B1_NO_DIRECTORY;
        return;
    }
    state.primary_status = status;
    state.primary_operation = op;
    state.primary_code = code;
    state.primary_index = index;
}
b1_slot *b1_reserve(b1_call *c, b1_kind kind, uint32_t index,
                    uint32_t directory_index, uint32_t operation)
{
    b1_record r = { kind, index };
    b1_slot *s;
    if (!owner(c) || state.uncertain) return NULL;
    s = slot_at(r);
    if (!s || state.cleaning || state.primary_status ||
        (directory_index >= B1_HANDLE_CAPACITY && directory_index != PTAI_B1_NO_DIRECTORY) ||
        (kind == B1_HANDLE ? operation != PTAI_B1_OP_OPEN_DIRECTORY :
                               operation != PTAI_B1_OP_SECURITY)) {
        invalid(c); return NULL;
    }
    if (state.count >= B1_LEDGER_CAPACITY || s->ownership != B1_EMPTY ||
        (state.count && slot_at(state.ledger[state.count - 1])->ownership == B1_RESERVED)) {
        invalid(c); return NULL;
    }
    s->ownership = B1_RESERVED;
    s->directory_index = directory_index;
    s->operation = operation;
    state.ledger[state.count++] = r;
    return s;
}
void b1_acquired(b1_call *c, b1_slot *s, b1_outcome outcome,
                 uintptr_t identity, uint32_t code)
{
    uint32_t i;
    b1_slot *last;
    if (!owner(c) || state.uncertain) return;
    last = state.count ? slot_at(state.ledger[state.count - 1]) : NULL;
    if (!s || s != last || s->ownership != B1_RESERVED) {
        /* An acquisition report without its reservation cannot be reconciled. */
        invalid(c);
        poison(PTAI_B1_NO_DIRECTORY, PTAI_B1_OP_NONE, 0);
        return;
    }
    if (outcome == B1_FAILURE_NO_OWNERSHIP) {
        b1_primary(c, PTAI_B1_STATUS_OS_ERROR, s->operation, code, s->directory_index);
        memset(s, 0, sizeof *s);
        --state.count;
        return;
    }
    /* Track returned ownership before any validation, including duplicates. */
    s->identity = identity;
    s->ownership = outcome == B1_SUCCESS ? B1_OWNED : B1_UNKNOWN;
    if (outcome != B1_SUCCESS) {
        b1_primary(c, PTAI_B1_STATUS_OS_ERROR, s->operation, code, s->directory_index);
        poison(s->directory_index, PTAI_B1_OP_NONE, 0);
        return;
    }
    if (!identity) {
        /* Success without a usable identity cannot be safely released. */
        invalid(c);
        poison(s->directory_index, PTAI_B1_OP_NONE, 0);
        return;
    }
    for (i = 0; i + 1 < state.count; ++i) {
        b1_record r = state.ledger[i];
        b1_slot *prior = slot_at(r);
        if (!prior || (r.kind == state.ledger[state.count - 1].kind &&
                       prior->identity == identity)) {
            /* Duplicate identities cannot establish two independent releases. */
            invalid(c);
            poison(s->directory_index, PTAI_B1_OP_NONE, 0);
            return;
        }
    }
}
const b1_slot *b1_cleanup_next(b1_call *c, b1_kind *kind)
{
    b1_slot *s;
    if (!owner(c) || state.uncertain) return NULL;
    state.cleaning = 1u;
    if (!state.count) return NULL;
    s = slot_at(state.ledger[state.count - 1]);
    if (s && s->ownership == B1_RESERVED) {
        b1_acquired(c, s, B1_OUTCOME_UNKNOWN, 0, 0); return NULL;
    }
    if (s && s->ownership == B1_RELEASE_PENDING) {
        b1_released(c, B1_OUTCOME_UNKNOWN, 0); return NULL;
    }
    if (!s || s->ownership != B1_OWNED) {
        invalid(c);
        poison(PTAI_B1_NO_DIRECTORY, PTAI_B1_OP_NONE, 0);
        return NULL;
    }
    if (!kind) { invalid(c); return NULL; }
    *kind = state.ledger[state.count - 1].kind;
    s->ownership = B1_RELEASE_PENDING; /* Attempt consumed before release. */
    return s;
}
void b1_released(b1_call *c, b1_outcome outcome, uint32_t code)
{
    b1_slot *s;
    uint32_t op;
    if (!owner(c) || state.uncertain) return;
    s = state.count ? slot_at(state.ledger[state.count - 1]) : NULL;
    if (!s || s->ownership != B1_RELEASE_PENDING) {
        invalid(c);
        /* No attempt was issued: retain known slots for checked cleanup.
         * A missing ledger slot, however, cannot establish ownership. */
        if (!s && state.count) poison(PTAI_B1_NO_DIRECTORY, PTAI_B1_OP_NONE, 0);
        return;
    }
    if (outcome == B1_SUCCESS) {
        memset(s, 0, sizeof *s); /* Only confirmed successful release clears. */
        --state.count;
        return;
    }
    op = state.ledger[state.count - 1].kind == B1_HANDLE ?
         PTAI_B1_OP_CLOSE_HANDLE : PTAI_B1_OP_FREE_DESCRIPTOR;
    s->ownership = B1_RELEASE_FAILED;
    poison(s->directory_index, op, code); /* Retain this and all earlier records. */
}
uint32_t b1_finish(b1_call *c, PTAI_B1_ERROR_V1 *error)
{
    uint32_t status;
    if (!owner(c)) return PTAI_B1_STATUS_INTERNAL_ERROR;
    if (!error) invalid(c);
    if (state.count && !state.uncertain) {
        b1_slot *s = slot_at(state.ledger[state.count - 1]);
        /* An unresolved acquisition or release is never guessed or retried. */
        if (s && s->ownership == B1_RESERVED)
            b1_acquired(c, s, B1_OUTCOME_UNKNOWN, 0, 0);
        else if (s && s->ownership == B1_RELEASE_PENDING)
            b1_released(c, B1_OUTCOME_UNKNOWN, 0);
        else {
            /* Finalization without completed cleanup cannot claim closure.
             * Keep every record; this pull protocol cannot release resources. */
            invalid(c);
            poison(PTAI_B1_NO_DIRECTORY, PTAI_B1_OP_NONE, 0);
        }
    }
    status = state.uncertain ? PTAI_B1_STATUS_CLEANUP_UNCERTAIN : state.primary_status;
    if (error) {
        memset(error, 0, sizeof *error);
        error->size = sizeof *error;
        error->status = status;
        error->operation = state.primary_operation;
        error->win32_error = state.primary_code;
        error->directory_index = state.uncertain ? state.uncertain_index : state.primary_index;
        error->cleanup_operation = state.cleanup_operation;
        error->cleanup_win32_error = state.cleanup_code;
        error->poisoned = state.uncertain ? 1u : 0u;
    }
    c->owns_gate = 0u;
    c->state = NULL;
    atomic_fetch_and_explicit(&gate, ~B1_ACTIVE, memory_order_release);
    return status;
}
