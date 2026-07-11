[CmdletBinding()]
param(
	[Parameter(Mandatory = $true)]
	[string]$Destination,

	[switch]$ScanOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$DestinationPath = [System.IO.Path]::GetFullPath($Destination)
$ForbiddenValuesPath = Join-Path $RepoRoot '.public-forbidden-values'
$Utf8Strict = New-Object System.Text.UTF8Encoding -ArgumentList @($false, $true)

function Invoke-Git {
	param(
		[Parameter(Mandatory = $true)]
		[string]$WorkingDirectory,

		[Parameter(Mandatory = $true)]
		[string[]]$Arguments
	)

	& git -C $WorkingDirectory @Arguments
	if ($LASTEXITCODE -ne 0) {
		throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
	}
}

function Get-CustomForbiddenValues {
	if (-not (Test-Path -LiteralPath $ForbiddenValuesPath -PathType Leaf)) {
		return @()
	}

	return @(
		Get-Content -LiteralPath $ForbiddenValuesPath -Encoding UTF8 |
			ForEach-Object { $_.Trim() } |
			Where-Object { $_ -and -not $_.StartsWith('#') }
	)
}

function Get-RelativeExportPath {
	param(
		[Parameter(Mandatory = $true)]
		[string]$FullName
	)

	return $FullName.Substring($DestinationPath.Length).TrimStart([char[]]@('\', '/'))
}

function Test-DummySecretValue {
	param(
		[Parameter(Mandatory = $true)]
		[string]$Value
	)

	$normalized = $Value.Trim().TrimEnd('\').Trim().Trim('"', "'")
	if ([string]::IsNullOrWhiteSpace($normalized)) {
		return $true
	}

	if ($normalized -match '^(change_me|replace_me|dummy|example|test-only(?:-secret)?(?:\\n.*)?)$') {
		return $true
	}

	if ($normalized -match '^(<|!|<[^>]+>|\$\{[^}]+\}|\$\(.+\)|%[^%]+%|[A-Za-z_][A-Za-z0-9_.]*\()') {
		return $true
	}

	return $normalized -match '\u539F\u503C'
}

function Invoke-SecretScan {
	param(
		[Parameter(Mandatory = $true)]
		[AllowEmptyCollection()]
		[string[]]$CustomForbiddenValues
	)

	$violations = New-Object 'System.Collections.Generic.List[string]'
	$gitDirectoryPrefix = [System.IO.Path]::Combine($DestinationPath, '.git') + [System.IO.Path]::DirectorySeparatorChar

	foreach ($file in Get-ChildItem -LiteralPath $DestinationPath -Recurse -Force -File) {
		if ($file.FullName.StartsWith($gitDirectoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
			continue
		}

		$relativePath = Get-RelativeExportPath -FullName $file.FullName
		$normalizedPath = $relativePath.Replace('\', '/')
		$lowerName = $file.Name.ToLowerInvariant()

		if (
			$lowerName -eq '.env' -or
			($lowerName.StartsWith('.env.') -and $lowerName -ne '.env.example') -or
			$lowerName -match '\.env$' -or
			$lowerName -match '\.(db|sqlite|sqlite3|pem|key|bak|backup|tar|tgz|zip)$' -or
			$lowerName -match '\.tar\.gz$' -or
			$normalizedPath -match '(^|/)(deploy-backups|backups?)(/|$)'
		) {
			$violations.Add("${relativePath}:1 forbidden file type or backup path")
			continue
		}

		$bytes = [System.IO.File]::ReadAllBytes($file.FullName)
		if ([System.Array]::IndexOf($bytes, [byte]0) -ge 0) {
			continue
		}

		try {
			$text = $Utf8Strict.GetString($bytes)
		}
		catch [System.Text.DecoderFallbackException] {
			continue
		}

		$lines = [System.Text.RegularExpressions.Regex]::Split($text, "`r?`n")
		for ($index = 0; $index -lt $lines.Length; $index++) {
			$line = $lines[$index]
			$lineNumber = $index + 1

			if ($line -match '-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----') {
				$violations.Add("${relativePath}:${lineNumber} private key header")
			}

			if ($line -match '(?i)\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})\b') {
				$violations.Add("${relativePath}:${lineNumber} GitHub token")
			}

			if ($line -match '\b(?:AKIA|ASIA)[0-9A-Z]{16}\b') {
				$violations.Add("${relativePath}:${lineNumber} AWS access key")
			}

			$secretMatch = [System.Text.RegularExpressions.Regex]::Match(
				$line,
				'(?i)(?:^|[^A-Z0-9_])WEBUI_SECRET_KEY\s*=(?!=)\s*(?<value>[^#\r\n]*)'
			)
			if ($secretMatch.Success -and -not (Test-DummySecretValue -Value $secretMatch.Groups['value'].Value)) {
				$violations.Add("${relativePath}:${lineNumber} non-dummy WEBUI_SECRET_KEY assignment")
			}

			foreach ($forbiddenValue in $CustomForbiddenValues) {
				if ($line.Contains($forbiddenValue)) {
					$violations.Add("${relativePath}:${lineNumber} custom forbidden value")
				}
			}
		}
	}

	if ($violations.Count -gt 0) {
		$details = $violations | Sort-Object -Unique
		throw "Public export secret scan failed:`n$($details -join "`n")"
	}

	Write-Output "Public export secret scan passed: $DestinationPath"
}

if ($ScanOnly) {
	if (-not (Test-Path -LiteralPath $DestinationPath -PathType Container)) {
		throw "Scan destination does not exist: $DestinationPath"
	}

	Invoke-SecretScan -CustomForbiddenValues @(Get-CustomForbiddenValues)
	return
}

$repoPrefix = $RepoRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
if (
	$DestinationPath.Equals($RepoRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
	$DestinationPath.StartsWith($repoPrefix, [System.StringComparison]::OrdinalIgnoreCase)
) {
	throw 'Export destination must be outside the source repository.'
}

$status = @(& git -C $RepoRoot status --porcelain)
if ($LASTEXITCODE -ne 0) {
	throw 'Unable to read Git working tree status.'
}
if ($status.Count -gt 0) {
	throw 'The source working tree must be clean before creating a public export.'
}

if (Test-Path -LiteralPath $DestinationPath) {
	if (-not (Test-Path -LiteralPath $DestinationPath -PathType Container)) {
		throw "Export destination is not a directory: $DestinationPath"
	}
	if (Get-ChildItem -LiteralPath $DestinationPath -Force | Select-Object -First 1) {
		throw "Export destination must be empty: $DestinationPath"
	}
}
else {
	New-Item -ItemType Directory -Path $DestinationPath | Out-Null
}

$archivePath = Join-Path ([System.IO.Path]::GetTempPath()) "artichat-public-$([guid]::NewGuid().ToString('N')).zip"
try {
	Invoke-Git -WorkingDirectory $RepoRoot -Arguments @('archive', '--format=zip', "--output=$archivePath", 'HEAD')
	Expand-Archive -LiteralPath $archivePath -DestinationPath $DestinationPath

	Invoke-SecretScan -CustomForbiddenValues @(Get-CustomForbiddenValues)

	Invoke-Git -WorkingDirectory $DestinationPath -Arguments @('init', '--initial-branch=main')
	Invoke-Git -WorkingDirectory $DestinationPath -Arguments @('add', '--all')
	Invoke-Git -WorkingDirectory $DestinationPath -Arguments @(
		'-c',
		'user.name=ArtiChat Public Export',
		'-c',
		'user.email=artichat-public-export@invalid.local',
		'commit',
		'-m',
		'Initial public snapshot'
	)

	Write-Output "Public repository export created: $DestinationPath"
}
finally {
	Remove-Item -LiteralPath $archivePath -Force -ErrorAction SilentlyContinue
}
