/* Private C2.1 foundation. Not a public ABI or an acquisition interface. */
#ifndef B1_INTERNAL_H_PRIVATE
#define B1_INTERNAL_H_PRIVATE
#include "journal_storage_windows_inspect.h"

#define B1_HANDLE_CAPACITY 64u
#define B1_DESCRIPTOR_CAPACITY 128u
#define B1_LEDGER_CAPACITY (B1_HANDLE_CAPACITY + B1_DESCRIPTOR_CAPACITY)
#define B1_ACTIVE 1u
#define B1_POISONED 2u

typedef enum { B1_HANDLE, B1_DESCRIPTOR } b1_kind;
typedef enum { B1_EMPTY, B1_RESERVED, B1_OWNED, B1_UNKNOWN,
               B1_RELEASE_PENDING, B1_RELEASE_FAILED } b1_ownership;
typedef enum { B1_SUCCESS, B1_FAILURE_NO_OWNERSHIP, B1_OUTCOME_UNKNOWN } b1_outcome;
typedef struct {
    b1_ownership ownership;
    uintptr_t identity; /* Opaque synthetic/native identity, never dereferenced. */
    uint32_t directory_index;
    uint32_t operation;
} b1_slot;
typedef struct { b1_kind kind; uint32_t index; } b1_record;
typedef struct {
    b1_slot handles[B1_HANDLE_CAPACITY];
    b1_slot descriptors[B1_DESCRIPTOR_CAPACITY];
    b1_record ledger[B1_LEDGER_CAPACITY];
    uint32_t count;
    uint32_t primary_status, primary_operation, primary_code, primary_index;
    uint32_t cleanup_operation, cleanup_code, uncertain_index;
    unsigned uncertain;
    unsigned cleaning;
} b1_state;
typedef struct { b1_state *state; unsigned owns_gate; } b1_call;

/* Zero-initialize a fresh call token. Never reuse/copy an active token.
 * All functions except enter require the sole owner on the entering thread.
 * No resource operation occurs here. Reserve, perform a future acquisition,
 * record its outcome immediately; never leave a reservation unresolved.
 * Cleanup is a pull protocol: next marks one attempt BEFORE a future release;
 * record that release immediately. No callbacks or implicit release retries.
 * Finish writes diagnostics, then releases active as its final state change.
 * A future caller must finish serialization/output writes BEFORE finish. */
uint32_t b1_enter(b1_call *call);
void b1_primary(b1_call *call, uint32_t status, uint32_t operation,
                uint32_t code, uint32_t index);
b1_slot *b1_reserve(b1_call *call, b1_kind kind, uint32_t index,
                    uint32_t directory_index, uint32_t operation);
void b1_acquired(b1_call *call, b1_slot *slot, b1_outcome outcome,
                 uintptr_t identity, uint32_t code);
const b1_slot *b1_cleanup_next(b1_call *call, b1_kind *kind);
void b1_released(b1_call *call, b1_outcome outcome, uint32_t code);
uint32_t b1_finish(b1_call *call, PTAI_B1_ERROR_V1 *error);
#endif
