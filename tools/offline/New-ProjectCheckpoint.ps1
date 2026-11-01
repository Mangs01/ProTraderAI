# Read-only display despite the historical New- verb: creates no checkpoint file.
# Compatible syntax for Windows PowerShell 5.1 and PowerShell 7.
[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Trust boundary: a trusted Git executable, PowerShell host, local filesystem and
# complete local repository are required. Git still reads configuration (including
# includes), attributes and object stores; this is not a sandbox for hostile Git
# installations/configuration, promisor repositories, or concurrently changed files.
# Built-in commands below do not use aliases or hooks. Disable paging, fsmonitor,
# external diff/textconv and configured submodule summaries explicitly.
try {
    # Reject environment overrides that redirect discovery/data/configuration or
    # enable trace writes. Do not print their potentially sensitive values.
    foreach ($entry in Get-ChildItem Env:) {
        if ($entry.Name -match '^(GIT_(DIR|WORK_TREE|COMMON_DIR|INDEX_FILE|OBJECT_DIRECTORY|ALTERNATE_OBJECT_DIRECTORIES|NAMESPACE|CEILING_DIRECTORIES|DISCOVERY_ACROSS_FILESYSTEM|SHALLOW_FILE|REPLACE_REF_BASE|GRAFT_FILE|QUARANTINE_PATH)|GIT_CONFIG.*|GIT_TRACE.*)$') {
            throw 'Unsafe Git environment override.'
        }
    }
    $gitCommand = Get-Command git -CommandType Application -ErrorAction Stop
    $repositoryCandidate = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))

    function Invoke-CheckpointGit {
        param([string[]]$GitArguments)
        # --no-optional-locks prevents status from refreshing the index on disk.
        $lines = @(& $gitCommand.Source --no-pager --no-optional-locks -c core.fsmonitor=false -c core.hooksPath=NUL -c log.showSignature=false -c status.submoduleSummary=false -C $repositoryCandidate @GitArguments 2>&1)
        if ($LASTEXITCODE -ne 0) {
            throw 'Read-only Git inspection failed; no further inspection performed.'
        }
        return $lines
    }

    $repositoryRoot = (Invoke-CheckpointGit -GitArguments @('rev-parse', '--show-toplevel')) -join ''
    # Normalize strings only: never resolve or access a Git-supplied filesystem path.
    if (-not [System.IO.Path]::IsPathRooted($repositoryRoot)) {
        throw 'Unexpected repository root.'
    }
    $normalizedRoot = [System.IO.Path]::GetFullPath($repositoryRoot).Replace('/', '\').TrimEnd('\')
    $normalizedExpected = $repositoryCandidate.Replace('/', '\').TrimEnd('\')
    if (-not [string]::Equals($normalizedRoot, $normalizedExpected, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'Unexpected repository root.'
    }
    $branch = (Invoke-CheckpointGit -GitArguments @('branch', '--show-current')) -join ''
    $head = (Invoke-CheckpointGit -GitArguments @('rev-parse', 'HEAD')) -join ''
    $subject = (Invoke-CheckpointGit -GitArguments @('log', '-1', '--no-show-signature', '--format=%s')) -join ''
    $status = @(Invoke-CheckpointGit -GitArguments @('status', '--short', '--untracked-files=all'))
    $staged = @(Invoke-CheckpointGit -GitArguments @('diff', '--cached', '--name-only', '--no-ext-diff', '--no-textconv'))

    Write-Output "Repository: $repositoryRoot"
    if ([string]::IsNullOrEmpty($branch)) { $branch = '(detached HEAD)' }
    Write-Output "Branch: $branch"
    Write-Output "HEAD: $head"
    Write-Output "Commit subject: $subject"
    Write-Output 'Git working-tree status:'
    if ($status.Count -eq 0) { Write-Output '(clean)' } else {
        $status | Write-Output
        Write-Warning 'Working tree is not clean. Preserve unrelated files; review before proceeding.'
    }
    Write-Output 'Staged filenames:'
    if ($staged.Count -eq 0) { Write-Output '(none)' } else { $staged | Write-Output }

    $checkpointPath = Join-Path $repositoryCandidate 'docs/project-continuity/CURRENT_CHECKPOINT.md'
    # Read only this fixed document. Treat Markdown as data, never executable code.
    $checkpointText = Get-Content -LiteralPath $checkpointPath -Raw -Encoding UTF8
    $headMatches = [regex]::Matches($checkpointText, '(?m)^Checkpoint-HEAD: ([0-9a-f]{40})\r?$')
    if ($headMatches.Count -ne 1) {
        throw 'Checkpoint must contain exactly one valid Checkpoint-HEAD field.'
    }
    $expectedHead = $headMatches[0].Groups[1].Value
    Write-Output "Checkpoint HEAD: $expectedHead"
    if ($head -cne $expectedHead) {
        Write-Warning 'HEAD differs from CURRENT_CHECKPOINT.md. Reconcile the recorded checkpoint before work.'
    }
} catch {
    # Fixed diagnostic avoids dumping arbitrary Git errors or environment data.
    Write-Error 'Checkpoint inspection failed: Git, repository or checkpoint is unavailable or invalid.' -ErrorAction Continue
    exit 1
}
