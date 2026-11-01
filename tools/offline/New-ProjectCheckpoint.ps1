# Read-only display despite the historical New- verb: creates no checkpoint file.
# Windows PowerShell 5.1 compatible. Requires trusted Git/configuration and local
# filesystem; concurrent repository mutation is outside this inspection's boundary.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    foreach ($entry in Get-ChildItem Env:) {
        # Reject every inherited Git override, including the original repository,
        # configuration and trace controls, Windows GIT_REDIRECT_* and GIT_EXEC_PATH.
        # Child-only safety variables are set explicitly below; print no values.
        if ($entry.Name -match '^GIT_') {
            throw 'Unsafe Git environment override.'
        }
    }
    $gitCommand = Get-Command git -CommandType Application -ErrorAction Stop
    $repositoryCandidate = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
    function ConvertTo-NativeArgument {
        param([string]$Value)
        # Windows CommandLineToArgvW quoting, including trailing backslashes.
        return '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
    }
    function Invoke-CheckpointGit {
        param([string[]]$GitArguments, [switch]$AllowAncestryFalse)
        $arguments = @('--no-pager', '--no-optional-locks', '--no-replace-objects',
            '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=NUL',
            '-c', 'log.showSignature=false', '-c', 'commit.gpgSign=false',
            '-c', 'tag.gpgSign=false', '-c', 'status.submoduleSummary=false',
            '-C', $repositoryCandidate) + $GitArguments
        $start = New-Object System.Diagnostics.ProcessStartInfo
        $start.FileName = $gitCommand.Source
        $start.Arguments = ($arguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
        $start.UseShellExecute = $false
        $start.CreateNoWindow = $true
        $start.RedirectStandardOutput = $true
        $start.RedirectStandardError = $true
        $start.StandardOutputEncoding = New-Object System.Text.UTF8Encoding($false, $true)
        $start.EnvironmentVariables['GIT_NO_LAZY_FETCH'] = '1'
        $start.EnvironmentVariables['GIT_NO_REPLACE_OBJECTS'] = '1'
        $start.EnvironmentVariables['GIT_TERMINAL_PROMPT'] = '0'
        # Defense in depth: disallow every transport, including local transports.
        $start.EnvironmentVariables['GIT_ALLOW_PROTOCOL'] = ''
        $process = New-Object System.Diagnostics.Process
        $process.StartInfo = $start
        try {
            if (-not $process.Start()) { throw 'Git start failed.' }
            $outputTask = $process.StandardOutput.ReadToEndAsync()
            $errorTask = $process.StandardError.ReadToEndAsync()
            $process.WaitForExit()
            $outputText = $outputTask.GetAwaiter().GetResult()
            $null = $errorTask.GetAwaiter().GetResult()
            $code = $process.ExitCode
            if ($code -ne 0 -and -not ($AllowAncestryFalse -and $code -eq 1)) {
                throw 'Git inspection failed.'
            }
            return [pscustomobject]@{ Text = $outputText; Code = $code }
        } finally { $process.Dispose() }
    }
    function Get-GitText {
        param([string[]]$Arguments)
        return (Invoke-CheckpointGit -GitArguments $Arguments).Text.TrimEnd("`r", "`n")
    }
    $root = Get-GitText @('rev-parse', '--show-toplevel')
    if (-not [IO.Path]::IsPathRooted($root) -or -not [string]::Equals(
        [IO.Path]::GetFullPath($root).Replace('/', '\').TrimEnd('\'),
        $repositoryCandidate.Replace('/', '\').TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Unexpected repository root.'
    }
    # Enumerate effective names only: do not expose configuration values. Git's
    # own reader applies system/global/local/worktree and included/conditional
    # configuration in this repository context. This command invokes no filters.
    # Reject even empty filter commands rather than infer attribute applicability.
    $configNames = (Invoke-CheckpointGit -GitArguments @('config', '--null', '--name-only', '--list', '--includes')).Text
    if ($configNames.Length -gt 0 -and -not $configNames.EndsWith([string][char]0)) {
        throw 'Invalid configuration enumeration.'
    }
    foreach ($name in $configNames.Split([char]0)) {
        if ($name -match '(?s)^filter\..*\.(clean|process)$') {
            throw 'Executable Git filter configuration is not permitted.'
        }
    }
    # ls-files reads index metadata without refreshing or rewriting the index.
    # -v lowercases assume-unchanged tags; S (or s) denotes skip-worktree.
    # Parse NUL records so whitespace, newlines and tabs in paths remain data.
    $indexText = (Invoke-CheckpointGit -GitArguments @('ls-files', '--cached', '--stage', '-v', '-z', '--')).Text
    if ($indexText.Length -gt 0 -and -not $indexText.EndsWith([string][char]0)) {
        throw 'Invalid index enumeration.'
    }
    foreach ($record in $indexText.Split([char]0)) {
        if ($record.Length -eq 0) { continue }
        $indexMatch = [regex]::Match($record, '\A([A-Za-z?]) ([0-7]{6}) ([0-9a-f]{40}) ([0-3])\t([\s\S]+)\z')
        if (-not $indexMatch.Success) { throw 'Invalid index record.' }
        $tag = $indexMatch.Groups[1].Value
        if ($tag -cmatch '[a-z]' -or $tag -ceq 'S') {
            throw 'Assume-unchanged or skip-worktree index entry is not permitted.'
        }
        # Status can recurse into submodules with independent effective configs.
        # Fail closed on gitlinks rather than hide changes or run unchecked status
        # in another repository. Submodule qualification is outside this tool.
        if ($indexMatch.Groups[2].Value -ceq '160000') {
            throw 'Submodule status safety is not established.'
        }
    }
    $checkpointText = Get-Content -LiteralPath (Join-Path $repositoryCandidate 'docs/project-continuity/CURRENT_CHECKPOINT.md') -Raw -Encoding UTF8
    $patterns = [ordered]@{
        'Checkpoint-Schema' = '1'
        'Expected-Branch' = 'main'
        'Accepted-Checkpoint' = '[0-9a-f]{40}'
        'Accepted-Phase' = 'PC-1'
        'Acceptance-Evidence' = 'operator-reported acceptance following independent source audit and local PowerShell runtime verification'
        'Remote-Backup' = 'unverified'
    }
    $metadata = @{}
    foreach ($key in $patterns.Keys) {
        $occurrences = [regex]::Matches($checkpointText, '(?m)^\s*' + [regex]::Escape($key) + '\s*:.*$')
        $valid = [regex]::Matches($checkpointText, '(?m)^' + [regex]::Escape($key) + ': (' + $patterns[$key] + ')\r?$')
        if ($occurrences.Count -ne 1 -or $valid.Count -ne 1) { throw 'Invalid checkpoint metadata.' }
        $metadata[$key] = $valid[0].Groups[1].Value
    }
    if ($checkpointText -match '(?m)^\s*Checkpoint-HEAD\s*:') { throw 'Obsolete checkpoint metadata.' }
    $branch = Get-GitText @('symbolic-ref', '--quiet', '--short', 'HEAD')
    if ($branch -cne $metadata['Expected-Branch']) { throw 'Wrong branch.' }
    $head = Get-GitText @('rev-parse', '--verify', 'HEAD')
    if ($head -cnotmatch '^[0-9a-f]{40}$') { throw 'Invalid HEAD.' }
    $accepted = $metadata['Accepted-Checkpoint']
    $objectType = Get-GitText @('cat-file', '-t', $accepted)
    if ($objectType -cne 'commit') { throw 'Checkpoint is not a local commit.' }
    # Reject shallow repositories even at equality; ancestry must remain trustworthy.
    if ((Get-GitText @('rev-parse', '--is-shallow-repository')) -cne 'false') { throw 'Incomplete history.' }
    # Traverse both histories to detect absent ancestry objects, including promisor gaps.
    $null = Get-GitText @('rev-list', '--parents', $head, $accepted, '--')
    $review = $false
    if ($head -ceq $accepted) { $classification = 'AT_ACCEPTED_CHECKPOINT' } else {
        $forward = Invoke-CheckpointGit -GitArguments @('merge-base', '--is-ancestor', $accepted, $head) -AllowAncestryFalse
        $backward = Invoke-CheckpointGit -GitArguments @('merge-base', '--is-ancestor', $head, $accepted) -AllowAncestryFalse
        if ($forward.Code -eq 0) { $classification = 'DESCENDANT_REVIEW_REQUIRED'; $review = $true }
        elseif ($backward.Code -eq 0) { throw 'BEHIND_ACCEPTED_CHECKPOINT' }
        else { throw 'DIVERGED' }
    }
    $protected = @(
        'paper/offline/journal_storage_windows.py',
        'tests/test_offline_journal_storage_windows.py',
        'research/metadata/phase28b/pytest_output.txt',
        'research/metadata/phase29a/acquisition_request_plan.json',
        'research/metadata/phase29a/artifact_hashes.json',
        'research/metadata/phase29a/evidence_references.json',
        'research/metadata/phase29a/identity_readiness.json',
        'research/metadata/phase29a/preservation.json',
        'research/metadata/phase29a/report.md',
        'research/metadata/phase29a/stage_sealing_readiness.json',
        'research/metadata/phase29a/verification.json'
    )
    # Filter and index preflights above must succeed before status. These commands
    # request no patches, external diff, textconv or signature verification.
    $status = (Invoke-CheckpointGit -GitArguments @('status', '--porcelain=v1', '-z', '--untracked-files=all', '--ignored=matching', '--ignore-submodules=none')).Text
    $records = $status.Split([char]0)
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::Ordinal)
    for ($i = 0; $i -lt $records.Length; $i++) {
        $record = $records[$i]
        if ($record.Length -eq 0) { continue }
        if ($record.Length -lt 4 -or $record[2] -cne ' ') { throw 'Invalid status record.' }
        $xy = $record.Substring(0, 2)
        $path = $record.Substring(3)
        # Escape control characters in diagnostics; never interpret paths as code.
        $display = $path.Replace('`', '``').Replace("`r", '\r').Replace("`n", '\n').Replace("`t", '\t')
        if ($xy -ceq '??') {
            $null = $seen.Add($path)
            if ($protected -cnotcontains $path) { Write-Output "Unexpected untracked path: $display"; $review = $true }
        } elseif ($xy -cne '!!') {
            Write-Output "Tracked/staged change [$xy]: $display"
            $review = $true
            if ($xy -match '[RC]') {
                $i++
                if ($i -ge $records.Length -or $records[$i].Length -eq 0) { throw 'Invalid rename record.' }
            }
        }
    }
    foreach ($path in $protected) {
        if (-not $seen.Contains($path)) { Write-Output "Missing protected untracked path: $path"; $review = $true }
    }
    Write-Output "Repository: $root"
    Write-Output "Branch: $branch"
    Write-Output "HEAD: $head"
    Write-Output "Accepted checkpoint: $accepted"
    Write-Output "Classification: $classification"
    if ($review) {
        Write-Output 'Review and reconciliation required. Exit 2 grants no implementation or acceptance authority.'
        exit 2
    }
    exit 0
} catch {
    # Only fixed diagnostics: never expose arbitrary Git stderr or metadata.
    if ($_.Exception.Message -ceq 'BEHIND_ACCEPTED_CHECKPOINT') { Write-Output 'Classification: BEHIND_ACCEPTED_CHECKPOINT' }
    elseif ($_.Exception.Message -ceq 'DIVERGED') { Write-Output 'Classification: DIVERGED' }
    Write-Error 'Checkpoint inspection failed: Git, branch, history or metadata is unavailable or invalid.' -ErrorAction Continue
    exit 1
}
