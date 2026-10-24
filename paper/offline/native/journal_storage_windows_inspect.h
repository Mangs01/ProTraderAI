/* Declaration-only Windows x64 B1 inspection ABI. See the design document. */
#ifndef PTAI_JOURNAL_STORAGE_WINDOWS_INSPECT_H
#define PTAI_JOURNAL_STORAGE_WINDOWS_INSPECT_H
#include <stdint.h>
#include <stddef.h>
#if !defined(_WIN32) || !defined(_M_X64)
#error This ABI requires Windows x64 (MSVC-compatible ABI).
#endif
#define PTAI_B1_API __declspec(dllexport)
#define PTAI_B1_CALL __cdecl
#define PTAI_B1_ABI_VERSION UINT32_C(0x00010000)
#define PTAI_B1_MAX_DIRECTORIES UINT32_C(64)
#define PTAI_B1_MAX_DESCRIPTOR_BYTES UINT32_C(65536)
#define PTAI_B1_MAX_NAME_UNITS UINT32_C(32767)
#define PTAI_B1_OUTPUT_BYTES UINT32_C(16777216)
#define PTAI_B1_NO_DIRECTORY UINT32_C(0xffffffff)

/* Fixed uint32_t identifiers, never C enum ABI types. */
#define PTAI_B1_STATUS_OK UINT32_C(0)
#define PTAI_B1_STATUS_INVALID_ARGUMENT UINT32_C(1)
#define PTAI_B1_STATUS_UNSUPPORTED UINT32_C(2)
#define PTAI_B1_STATUS_LIMIT UINT32_C(3)
#define PTAI_B1_STATUS_OS_ERROR UINT32_C(4)
#define PTAI_B1_STATUS_CHANGED UINT32_C(5)
#define PTAI_B1_STATUS_CLEANUP_UNCERTAIN UINT32_C(6)
#define PTAI_B1_STATUS_POISONED UINT32_C(7)
#define PTAI_B1_STATUS_BUSY UINT32_C(8)
#define PTAI_B1_STATUS_INTERNAL_ERROR UINT32_C(9)
#define PTAI_B1_OP_NONE UINT32_C(0)
#define PTAI_B1_OP_VALIDATE UINT32_C(1)
#define PTAI_B1_OP_DRIVE_MAPPING UINT32_C(2)
#define PTAI_B1_OP_OPEN_DIRECTORY UINT32_C(3)
#define PTAI_B1_OP_DIRECTORY_INFO UINT32_C(4)
#define PTAI_B1_OP_FINAL_NAME UINT32_C(5)
#define PTAI_B1_OP_VOLUME_INFO UINT32_C(6)
#define PTAI_B1_OP_SECURITY UINT32_C(7)
#define PTAI_B1_OP_RECHECK UINT32_C(8)
#define PTAI_B1_OP_CLOSE_HANDLE UINT32_C(9)
#define PTAI_B1_OP_FREE_DESCRIPTOR UINT32_C(10)
#define PTAI_B1_OP_SERIALIZE UINT32_C(11)

#pragma pack(push, 8)
typedef struct PTAI_B1_ERROR_V1 {
    uint32_t size;
    uint32_t status;
    uint32_t operation;
    uint32_t win32_error;
    uint32_t directory_index;
    uint32_t cleanup_operation;
    uint32_t cleanup_win32_error;
    uint32_t poisoned;
    uint32_t reserved[8];
} PTAI_B1_ERROR_V1;

typedef struct PTAI_B1_OUTPUT_V1 {
    uint32_t abi_version;
    uint32_t header_size;
    uint32_t output_used;
    uint32_t directory_count;
    uint32_t records_offset;
    uint32_t record_size;
    uint32_t qualified;
    uint32_t flags;
    uint32_t reserved[8];
} PTAI_B1_OUTPUT_V1;

typedef struct PTAI_B1_DIRECTORY_V1 {
    uint32_t record_size;
    uint32_t directory_index;
    uint64_t volume_id;
    uint8_t file_id[16];
    uint32_t path_offset;
    uint32_t path_units;
    uint32_t final_name_offset;
    uint32_t final_name_units;
    uint32_t descriptor_offset;
    uint32_t descriptor_bytes;
    uint32_t volume_serial;
    uint32_t maximum_component_units;
    uint32_t filesystem_flags;
    uint32_t filesystem_name_offset;
    uint32_t filesystem_name_units;
    uint32_t reserved[5];
} PTAI_B1_DIRECTORY_V1;

#pragma pack(pop)
#if defined(__cplusplus)
#define PTAI_B1_ASSERT(c) static_assert((c), #c)
#else
#define PTAI_B1_ASSERT(c) _Static_assert((c), #c)
#endif
PTAI_B1_ASSERT(sizeof(void *) == 8);
PTAI_B1_ASSERT(sizeof(PTAI_B1_ERROR_V1) == 64);
PTAI_B1_ASSERT(offsetof(PTAI_B1_ERROR_V1, size) == 0);
PTAI_B1_ASSERT(offsetof(PTAI_B1_ERROR_V1, status) == 4);
PTAI_B1_ASSERT(offsetof(PTAI_B1_ERROR_V1, operation) == 8);
PTAI_B1_ASSERT(offsetof(PTAI_B1_ERROR_V1, win32_error) == 12);
PTAI_B1_ASSERT(offsetof(PTAI_B1_ERROR_V1, directory_index) == 16);
PTAI_B1_ASSERT(offsetof(PTAI_B1_ERROR_V1, cleanup_operation) == 20);
PTAI_B1_ASSERT(offsetof(PTAI_B1_ERROR_V1, cleanup_win32_error) == 24);
PTAI_B1_ASSERT(offsetof(PTAI_B1_ERROR_V1, poisoned) == 28);
PTAI_B1_ASSERT(offsetof(PTAI_B1_ERROR_V1, reserved) == 32);
PTAI_B1_ASSERT(sizeof(PTAI_B1_OUTPUT_V1) == 64);
PTAI_B1_ASSERT(offsetof(PTAI_B1_OUTPUT_V1, abi_version) == 0);
PTAI_B1_ASSERT(offsetof(PTAI_B1_OUTPUT_V1, header_size) == 4);
PTAI_B1_ASSERT(offsetof(PTAI_B1_OUTPUT_V1, output_used) == 8);
PTAI_B1_ASSERT(offsetof(PTAI_B1_OUTPUT_V1, directory_count) == 12);
PTAI_B1_ASSERT(offsetof(PTAI_B1_OUTPUT_V1, records_offset) == 16);
PTAI_B1_ASSERT(offsetof(PTAI_B1_OUTPUT_V1, record_size) == 20);
PTAI_B1_ASSERT(offsetof(PTAI_B1_OUTPUT_V1, qualified) == 24);
PTAI_B1_ASSERT(offsetof(PTAI_B1_OUTPUT_V1, flags) == 28);
PTAI_B1_ASSERT(offsetof(PTAI_B1_OUTPUT_V1, reserved) == 32);
PTAI_B1_ASSERT(sizeof(PTAI_B1_DIRECTORY_V1) == 96);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, record_size) == 0);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, directory_index) == 4);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, volume_id) == 8);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, file_id) == 16);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, path_offset) == 32);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, path_units) == 36);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, final_name_offset) == 40);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, final_name_units) == 44);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, descriptor_offset) == 48);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, descriptor_bytes) == 52);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, volume_serial) == 56);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, maximum_component_units) == 60);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, filesystem_flags) == 64);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, filesystem_name_offset) == 68);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, filesystem_name_units) == 72);
PTAI_B1_ASSERT(offsetof(PTAI_B1_DIRECTORY_V1, reserved) == 76);
#undef PTAI_B1_ASSERT

#ifdef __cplusplus
extern "C" {
#endif
/* Side-effect-free version query; no resources acquired. */
PTAI_B1_API uint32_t PTAI_B1_CALL ptai_b1_abi_version(void);
/* Caller owns all buffers. See document for validity, failure and publication rules.
 * No native pointers or handles appear in serialized output or error.
 * Entry precedence (no new status identifiers or request-version field):
 * ABI_MISMATCH means caller-side version-query mismatch: do not invoke inspect.
 * Wrong request capacities map to INVALID_ARGUMENT; BUSY_OR_REENTRANT maps to BUSY.
 * First, without dereferencing pointers, check nulls, required alignment,
 * path_units in 4..32767, output_capacity=16777216 and error_capacity=64.
 * Failure is INVALID_ARGUMENT/VALIDATE, NO_DIRECTORY, zero OS/cleanup codes,
 * poisoned=0, even if module poison or active is set; no gate is acquired.
 * Failure writes require independently caller-valid writable destinations;
 * skip null/misaligned destinations. Invalid addresses, false extents, overlap
 * or concurrent mutation violate the caller contract: no status guarantee.
 * Do not probe memory or read buffer contents to decide entry precedence.
 * Immediately after these checks, one atomic nonwaiting decision checks
 * permanent poison first (POISONED), then active (BUSY), else sets active.
 * Rejected calls neither acquire nor release the gate and do not read input
 * contents or check the environment. They cannot access the target.
 * Only the gate owner validates UTF-16/lexical input (INVALID_ARGUMENT), then
 * depth/checked-size bounds (LIMIT), then runtime/namespace policy (UNSUPPORTED),
 * then inspects in documented observation order; first failure per phase wins.
 * A poisoned scalar-valid call with malformed buffer contents returns POISONED.
 * First primary failure is retained; after acquisition perform checked cleanup.
 * CLEANUP_UNCERTAIN overrides status on ownership/cleanup uncertainty. OK needs
 * all checks and successful cleanup. Hold the gate through final serialization
 * and output/error writes; publish permanent poison atomically before clearing
 * active on uncertainty. Clear active exactly once as the last state transition
 * before every gate-owning return, even pre-acquisition failures. Never clear
 * poison or discard retained bookkeeping. Scalar rejection cannot bypass poison
 * for acquisition; its poisoned=0 is not a module-health query.
 *
 * Diagnostic index rules, in priority order:
 * - Failed/uncertain release of a known slot: directory_index is that cleanup
 *   slot's ancestor, or NO_DIRECTORY if the slot has no directory association;
 *   cleanup_operation=CLOSE_HANDLE/FREE_DESCRIPTOR, cleanup_win32_error is the
 *   applicable release code or zero when unavailable. Index describes cleanup.
 * - Unknown acquisition outcome without a failed release: index is the uncertain
 *   acquisition's ancestor, or NO_DIRECTORY if unassociated; cleanup_operation
 *   is NONE and cleanup_win32_error=0. No release follows the unknown outcome.
 *   Index describes acquisition, not cleanup.
 * - Otherwise index is the primary failure's ancestor, or NO_DIRECTORY for
 *   unassociated failure, phase-less rejection or success; cleanup is NONE/0.
 * operation/win32_error retain the first primary failure's phase/code, including
 * when cleanup overrides status/index. Unknown acquisition supplies this pair
 * only if no earlier primary failure exists. With no primary failure (including
 * cleanup-only failure), operation=NONE and win32_error=0. Unavailable OS codes
 * are zero, never stale last-error. Overridden primary status/index have no
 * separate ABI fields; never use reserved fields to preserve them.
 * CLEANUP_UNCERTAIN and POISONED have poisoned=1; all other statuses have 0.
 * BUSY/POISONED diagnostics are operation=NONE, NO_DIRECTORY, zero OS/cleanup
 * codes. Reserved fields are zero. No speculative cleanup retry or partial
 * evidence publication; every result remains qualified=0 (False).
 */
PTAI_B1_API uint32_t PTAI_B1_CALL ptai_b1_inspect_v1(
    const uint16_t *path_utf16,
    uint32_t path_units,
    uint8_t *output,
    uint32_t output_capacity,
    uint32_t *output_used,
    PTAI_B1_ERROR_V1 *error,
    uint32_t error_capacity);
#ifdef __cplusplus
}
#endif
#endif

