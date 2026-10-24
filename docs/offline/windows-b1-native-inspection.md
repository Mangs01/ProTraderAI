# Windows B1 native inspection ABI v1

Status: D2b-B1-C1 declaration and design foundation only. No DLL, loader,
acquisition implementation or build system is supplied. Batch A and existing
Python inspection remain unchanged. This contract does not authorize durable use.

## ABI and call contract

The normative declarations are in
[the header](../../paper/offline/native/journal_storage_windows_inspect.h).
Windows x64, little endian, MSVC-compatible C ABI; C linkage and explicit
__cdecl apply to exactly two proposed DLL exports:

- uint32_t ptai_b1_abi_version(void): returns 0x00010000 without acquisition.
- uint32_t ptai_b1_inspect_v1(const uint16_t *path_utf16,
  uint32_t path_units, uint8_t *output, uint32_t output_capacity,
  uint32_t *output_used, PTAI_B1_ERROR_V1 *error, uint32_t error_capacity):
  returns a fixed status below.

There are no raw Win32 handle exports, allocation/free API exports, callbacks,
variadic APIs or function bodies. The future export table must contain exactly
these undecorated names. All scalar ABI fields and arguments use exact-width
integers; pointers are 64 bits. Structures use pack 8, with explicit padding
represented by reserved fields. C11 or C++11 static assertions cover every field
offset and structure size. The header intentionally rejects other architectures.

Python owns and pins input, output, output_used and error buffers throughout
the synchronous call. All pointers are non-null, correctly aligned for their
declared types, readable/writable as appropriate, and pairwise nonoverlapping.
Input is immutable during the call. Caller provides exactly 16,777,216 output
bytes (16 MiB), a writable uint32_t output_used, and exactly 64 error bytes.
Output is at least 8-byte aligned. Error storage and output_used are zeroed by
the caller before invocation. Invalid pointers, overlapping storage, concurrent
buffer mutation and false capacities violate the caller contract; native code
cannot make arbitrary memory safe. Valid buffers with incorrect numeric
capacities are rejected without acquisition or evidence output.

Input length excludes a terminator, lies in 4..32767 UTF-16 units and describes
the full target file path. No terminator is required or read; embedded NUL,
unpaired surrogates and spellings rejected by Batch A are rejected before
target access. The native implementation must independently enforce the
unchanged Batch A lexical policy; a future loader validates exact Python str
and Batch A records before encoding. No expansion or implicit normalization.
At most 64 ancestor directories including the drive root are inspected;
the final file component is never opened. Excess depth fails before acquisition.

Success is STATUS_OK only after all checks and checked cleanup. output_used
then equals the header output_used, and the error structure has size=64,
status=OK, operation=NONE, directory_index=NO_DIRECTORY, all other fields zero.
For caller-valid writable buffers, every failure sets the separate output_used
to zero; if the output capacity
is correct the output header output_used is also zero. Error is initialized
even on numeric-capacity rejection when error_capacity permits the full
64-byte write; otherwise no error write occurs. Failure output is invalid
and must never be parsed, even if temporary bytes exist. Caller must check
return status, both lengths, layout and reserved zeros before interpretation.

### Entry validation and status precedence

There is no ABI_MISMATCH status or request-version field in v1. A malformed
ABI request (wrong numeric capacities) returns INVALID_ARGUMENT. A future caller
must compare the side-effect-free version query with 0x00010000 before calling;
a version mismatch prevents invocation and is not a native inspect status.
BUSY_OR_REENTRANT is represented by the existing BUSY status.

Entry follows this exact order:

1. Without dereferencing any pointer, check nulls, required pointer alignment,
   path_units in 4..32767, output_capacity=16777216 and error_capacity=64.
   Any failure returns INVALID_ARGUMENT, operation=VALIDATE,
   directory_index=NO_DIRECTORY and zero OS/cleanup codes. No gate is acquired.
   These checks take precedence even over poison or concurrent entry. Failure
   writes apply only to independently caller-valid writable destinations; skip
   null/misaligned destinations and never read path or output contents here.
2. Immediately after those checks, perform one atomic, nonwaiting gate entry
   decision against the module's active and permanent-poison state. If poison
   is set, return POISONED even if active is also set. Otherwise, if active is
   set, return BUSY. Otherwise atomically set active and own the gate. Rejected
   calls neither acquire nor release the gate and perform no input-content or
   environment checks. Neither rejection accesses the target.
3. Only the gate owner reads input contents: enforce UTF-16 and lexical policy
   (INVALID_ARGUMENT), then ancestor-depth and checked-size bounds (LIMIT),
   then runtime/namespace environment policy (UNSUPPORTED). Within each phase
   the first detected failure wins. Thus a valid buffer with malformed UTF-16
   returns POISONED on an already poisoned module, BUSY during an unpoisoned
   active call, and INVALID_ARGUMENT only after successful gate entry.
4. Inspection then proceeds in the specified observation order. The first
   primary failure is retained; errors after acquisition require checked cleanup.
   CLEANUP_UNCERTAIN overrides the return status if ownership or cleanup becomes
   uncertain, with diagnostics as defined below. No later check replaces a
   retained primary failure. OK requires all checks and successful cleanup.

The gate remains owned through validation, acquisition, cleanup, serialization
and final output/error writes. On uncertainty, atomically publish permanent
poison before releasing active; retained ownership bookkeeping persists.
Release active exactly once as the last state transition before returning on
every gate-owning path, including pre-acquisition failures. Never clear poison.
An otherwise valid later call returns POISONED before input-content reads or
target acquisition. A poisoned call may return INVALID_ARGUMENT for a failed
step-1 scalar/pointer-value check, but this does not clear poison or permit
acquisition. For that early rejection poisoned=0 describes the rejection only;
it is not a query of module health.

Non-null but inaccessible pointers, false claimed extents, overlap and concurrent
buffer mutation remain caller contract violations, with no defined status or
precedence guarantee. No pointer probing, speculative reads or exception-based
memory validation is authorized to determine precedence. Valid buffers with
malformed contents are ordinary input failures under the ordering above.

## Fixed identifiers

Identifiers are uint32_t constants, not C enum parameters. Unknown identifiers
are invalid and must fail closed in consumers. NO_DIRECTORY is 0xffffffff.

| Status suffix (PTAI_B1_STATUS_) | Value |
| --- | --- |
| OK | 0 |
| INVALID_ARGUMENT | 1 |
| UNSUPPORTED | 2 |
| LIMIT | 3 |
| OS_ERROR | 4 |
| CHANGED | 5 |
| CLEANUP_UNCERTAIN | 6 |
| POISONED | 7 |
| BUSY | 8 |
| INTERNAL_ERROR | 9 |

INVALID_ARGUMENT covers lexical/argument failures; UNSUPPORTED covers rejected
namespace/runtime policy; LIMIT covers any fixed bound or arithmetic overflow;
OS_ERROR covers inspection API failure; CHANGED covers differing observations.
CLEANUP_UNCERTAIN supersedes any primary failure and permanently poisons the
native module. POISONED rejects subsequent inspections before acquisition.
BUSY rejects concurrent or reentrant inspection without waiting; INTERNAL_ERROR
is a contained internal failure, never permission to publish. Native code must
not let C++ exceptions escape the C boundary. Version queries remain available.

| Operation suffix (PTAI_B1_OP_) | Value |
| --- | --- |
| NONE | 0 |
| VALIDATE | 1 |
| DRIVE_MAPPING | 2 |
| OPEN_DIRECTORY | 3 |
| DIRECTORY_INFO | 4 |
| FINAL_NAME | 5 |
| VOLUME_INFO | 6 |
| SECURITY | 7 |
| RECHECK | 8 |
| CLOSE_HANDLE | 9 |
| FREE_DESCRIPTOR | 10 |
| SERIALIZE | 11 |

Error operation records the primary failing phase (NONE when no primary failure);
cleanup_operation separately identifies CLOSE_HANDLE or FREE_DESCRIPTOR.
win32_error and cleanup_win32_error are captured immediately from the relevant
API result/last-error contract, never stale last-error values; zero means no
applicable OS code. A direct security API error code is preserved directly.
directory_index is selected by the following ordered rules:

- When a release fails or is uncertain for a known resource slot, it identifies
  that cleanup slot's ancestor (NO_DIRECTORY only if the slot is not associated
  with any directory). cleanup_operation is CLOSE_HANDLE or FREE_DESCRIPTOR;
  cleanup_win32_error is the applicable release code, or zero if unavailable.
  The index describes cleanup, even when the primary failure was elsewhere.
- When acquisition outcome is unknown and no release failed, it identifies the
  uncertain acquisition's ancestor, or NO_DIRECTORY if acquisition is not
  associated with any directory. cleanup_operation=NONE and
  cleanup_win32_error=0; no release is attempted after the unknown outcome.
  The index describes acquisition, not a nonexistent cleanup slot.
- Otherwise it identifies the primary failure's ancestor, or NO_DIRECTORY for
  a failure not associated with any directory, a rejection without a phase,
  or success. cleanup_operation=NONE and cleanup_win32_error=0.

operation/win32_error always preserve the first primary failing phase and its
applicable OS code, even when CLEANUP_UNCERTAIN overrides its status and the
index describes cleanup. If unknown acquisition is itself the first failure,
its acquisition operation/code become the primary diagnostics. If an earlier
primary failure exists, retain that pair instead. With no primary failure,
operation=NONE and win32_error=0, including cleanup-only failure. The original
primary status and ancestor cannot both be separately represented when cleanup
overrides them; do not encode them in reserved fields or overwrite the primary
operation/code. No applicable OS code means zero, never stale last-error.

For example, unknown OPEN_DIRECTORY outcome at ancestor 3 reports
CLEANUP_UNCERTAIN, operation=OPEN_DIRECTORY, directory_index=3 and cleanup NONE/0;
a directory-independent unknown acquisition uses NO_DIRECTORY instead. A
DIRECTORY_INFO failure at ancestor 2 followed by failed CLOSE_HANDLE for slot 1
retains DIRECTORY_INFO and its OS code, but reports directory_index=1 and the
CLOSE_HANDLE cleanup code. A primary failure followed by unknown acquisition
at ancestor 3 retains the primary operation/code, uses index 3 and cleanup
NONE/0. Cleanup-only FREE_DESCRIPTOR failure at ancestor 1 uses operation=NONE,
win32_error=0, index 1 and cleanup_operation=FREE_DESCRIPTOR.

poisoned is exactly
0 or 1; it is 1 for CLEANUP_UNCERTAIN and POISONED, otherwise 0. Reserved fields
are always zero. A BUSY rejection reports operation=NONE, NO_DIRECTORY and zero
OS codes. A later POISONED rejection has the same diagnostics with poisoned=1.

## Structure layouts

All offsets and lengths below are bytes except fields explicitly named units.
No pointers occur in these structures. Array reserved fields are entirely zero.

### PTAI_B1_ERROR_V1 (64 bytes)

| Offset | Type | Field |
| --- | --- | --- |
| 0 | uint32_t | size |
| 4 | uint32_t | status |
| 8 | uint32_t | operation |
| 12 | uint32_t | win32_error |
| 16 | uint32_t | directory_index |
| 20 | uint32_t | cleanup_operation |
| 24 | uint32_t | cleanup_win32_error |
| 28 | uint32_t | poisoned |
| 32 | uint32_t | reserved[8] |

### PTAI_B1_OUTPUT_V1 (64 bytes)

| Offset | Type | Field |
| --- | --- | --- |
| 0 | uint32_t | abi_version |
| 4 | uint32_t | header_size |
| 8 | uint32_t | output_used |
| 12 | uint32_t | directory_count |
| 16 | uint32_t | records_offset |
| 20 | uint32_t | record_size |
| 24 | uint32_t | qualified |
| 28 | uint32_t | flags |
| 32 | uint32_t | reserved[8] |

### PTAI_B1_DIRECTORY_V1 (96 bytes)

| Offset | Type | Field |
| --- | --- | --- |
| 0 | uint32_t | record_size |
| 4 | uint32_t | directory_index |
| 8 | uint64_t | volume_id |
| 16 | uint8_t | file_id[16] |
| 32 | uint32_t | path_offset |
| 36 | uint32_t | path_units |
| 40 | uint32_t | final_name_offset |
| 44 | uint32_t | final_name_units |
| 48 | uint32_t | descriptor_offset |
| 52 | uint32_t | descriptor_bytes |
| 56 | uint32_t | volume_serial |
| 60 | uint32_t | maximum_component_units |
| 64 | uint32_t | filesystem_flags |
| 68 | uint32_t | filesystem_name_offset |
| 72 | uint32_t | filesystem_name_units |
| 76 | uint32_t | reserved[5] |

## Serialized output

The 64-byte header starts at output byte zero. abi_version=0x00010000,
header_size=64, directory_count is 1..64, records_offset=64, record_size=96,
qualified=0 and flags=0. The contiguous record table occupies
[64, 64 + 96 * directory_count). Each record has record_size=96 and
directory_index equal to its zero-based table index. Order is root then each
ancestor through the immediate parent. path is the exact ancestor spelling
derived from input (root includes its trailing backslash).

volume_id is the nonzero 64-bit volume identity; file_id is the 16-byte opaque,
nonzero file identity in native byte order, without GUID reinterpretation.
volume_serial, maximum_component_units, filesystem_flags and filesystem_name
are copied volume observations, corresponding to the existing Python volume
tuple. The 32-bit volume_serial is distinct from volume_id. The filesystem
name is NTFS and persistent ACL capability must be observed; these facts alone
do not qualify the filesystem or effective ACL protection.

Each offset is absolute from output base. Each string is UTF-16LE, without BOM
or stored terminator; units counts 16-bit code units, not Unicode scalar values.
Strings have no embedded NUL and must be well-formed UTF-16. path, final_name
and filesystem_name are nonempty, at most 32767 units each. final_name preserves
the observed volume-GUID form; path preserves the input ancestor spelling.

descriptor_bytes is 1..65536 per observation. Descriptor payloads are exact
validated self-relative security descriptor copies including owner, group and
DACL evidence, not absolute structures or pointers. SE_SELF_RELATIVE and internal
component offsets/lengths must be validated against the copied descriptor size.
No SACL or effective-access decision is implied. A malformed or absolute
descriptor is refused, never blindly copied as pointer-bearing data.

Payload allocation is canonical: after the record table, visit records in order,
placing path, final_name, descriptor and filesystem_name in that order.
Start each payload at the next 8-byte boundary. Strings occupy exactly
2 * units bytes, descriptors exactly descriptor_bytes. All payload intervals
are disjoint, lie after the table and end at or before output_used; neither
sharing nor overlapping payloads is allowed. Alignment gaps are zero.
output_used is the end of the last payload, without trailing alignment padding,
and cannot exceed 16777216. Unused output tail is not evidence and is unspecified.
All addition, multiplication, alignment and range checks use checked arithmetic
before writing. Consumers repeat range/disjointness checks before decoding.
No truncation, partial success, size-probe API, overflow resizing or silent
overflow retries are allowed. An oversized observation or changed required size
fails the entire inspection with LIMIT. Fixed scratch capacities must accommodate
terminators required by Win32 without counting them as payload units.

## Observation scope and publication

Future acquisition must preserve the narrow current B1 policy: existing fixed
local drive mapping only, no mapped/substituted/network aliases, no reparse
ancestors, inheritable handles, delete-pending/non-directory objects, unsupported
case sensitivity or unknown identity. Observe directory metadata, final names,
volume data and owner/group/DACL descriptors. Retain ancestor handles and repeat
directory and descriptor observations, then recheck drive mapping. Refuse
differences rather than retry. This describes required future behavior; mocks
and this header provide no Windows qualification evidence.

All serialized evidence must be withheld until checked native cleanup succeeds.
Native staging may use the caller's output payload area, but header publication
and nonzero output_used occur only after cleanup and final serialization checks.
Python may neither read staged output concurrently nor publish a result from it.
The native return is followed by Python cancellation handling and complete output
validation before any Python evidence object is made available. qualified is
always zero. No ownership token or durable coordinator is produced.

## Resource ownership, cleanup and poison

Native code owns every acquired directory handle and security descriptor.
No native resource pointers cross into Python, including diagnostics. Before
any acquisition, reserve fixed native ownership slots for up to 64 handles and
128 descriptor allocations (initial and repeat observations), plus all required
bounded scratch and bookkeeping. Each acquisition has an already-addressable
slot and records its outcome entirely in native code before another operation.
No Python allocation, callback or Python execution is permitted while native
resources are held. Returned OS-owned allocations must be tracked before copying
or validating them. Failed API output parameters are interpreted only according
to the documented API success/failure ownership contract.

Cleanup is checked in strict reverse acquisition order. Each release is attempted
once and its documented return value checked. A successful release clears its
slot. At the first failed or uncertain release, stop cleanup, retain the remaining
slots and permanently poison the module; never guess whether a handle is still
owned. No speculative cleanup retries, reset API, finalizer release or DLL detach
release is permitted. An internal failure with known ownership still attempts
normal checked cleanup. Unknown acquisition outcome also poisons without guessing
a release. Unknown acquisition outcome returns CLEANUP_UNCERTAIN with the
acquisition operation as the primary phase unless an earlier primary failure
must be preserved, cleanup_operation=NONE and cleanup_win32_error=0. Its index
identifies that acquisition's ancestor, or NO_DIRECTORY if none; no release is
attempted after the unknown outcome. Subsequent inspections pass through the
entry precedence above and cannot access the target. Poison
state and retained bookkeeping must persist for process lifetime; the future
loader must keep the DLL loaded and must not reload it to bypass poison.
This containment is fail-closed, not a promise that uncertain resources survived.
Native synchronization follows the atomic gate and precedence specified above;
eligible competing/reentrant calls return BUSY before acquisition unless poison
is already set, in which case they return POISONED. No resource-owning
implementation is part of this change.

## Cancellation and explicit limits of the guarantee

Python cancellation is deferred during synchronous native execution. A future
loader must use a qualified synchronous calling convention that prevents Python
callbacks and asynchronous Python unwinding through the native frame. Pending
KeyboardInterrupt or other Python cancellation is handled after native return
and checked cleanup, and suppresses evidence publication. There is no native
cancel entry point or cancellation callback.

This does not promise immediate cancellation, bounded Win32 I/O, safety under
arbitrary native thread termination, recovery from memory corruption, race-free
namespace binding, effective ACL qualification or SQLite exclusion. Repeated
observations detect observed differences only. No SQLite, LockFileEx, broker or
trading implementation is included. Durable ownership, reservation, recovery,
ACL policy and ordinary external database exclusion remain separate unresolved
D2b gates in the durable journal contract.

## Proposed future build and qualification contract

Qualification target: Windows 11 x64, CPython 3.12 x64, MSVC v143 x64 and Windows
SDK 10.0.26100.0. A future offline reproducible build must use locally installed,
pinned toolchain components, recorded compiler/linker versions and deterministic
flags, with no downloaded dependencies. Generated binaries are local artifacts,
not Git-tracked. Future work must verify the actual DLL export table, C and C++
layout compilation, loader marshaling, cancellation behavior, native fault
injection and Windows resource semantics. These are requirements, not test
results. No compiler or build commands are authorized or executed here.

## C1 review boundary and remaining questions

The wire layout, limits, numeric identifiers, ownership and failure publication
rules are fixed here; changing them requires explicit ABI review. Independent C1
audit should examine descriptor validation, error precedence, poison containment,
checked arithmetic and cancellation assumptions. Concrete Win32 acquisition,
native synchronization, DLL lifetime enforcement, exact CPython cancellation
behavior and reproducible build recipes remain future implementation and
qualification work. They are not evidence of completed D2b safety. This foundation
is reviewable independently; it is not approval to implement or operate storage.

