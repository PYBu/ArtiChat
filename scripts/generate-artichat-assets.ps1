$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Drawing

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$DarkMark = Join-Path $RepoRoot 'artivis-ass\logo\artimage-mark-dark.png'
$LightMark = Join-Path $RepoRoot 'artivis-ass\logo\artimage-mark-light.png'

function Ensure-Directory {
	param(
		[Parameter(Mandatory = $true)]
		[string]$Path
	)

	$directory = Split-Path -Parent $Path

	if (-not [string]::IsNullOrWhiteSpace($directory) -and -not (Test-Path $directory)) {
		New-Item -ItemType Directory -Path $directory | Out-Null
	}
}

function New-ResizedBitmap {
	param(
		[Parameter(Mandatory = $true)]
		[string]$SourcePath,

		[Parameter(Mandatory = $true)]
		[int]$Width,

		[Parameter(Mandatory = $true)]
		[int]$Height
	)

	$source = [System.Drawing.Image]::FromFile($SourcePath)

	try {
		$bitmap = New-Object System.Drawing.Bitmap $Width, $Height, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
		$bitmap.SetResolution($source.HorizontalResolution, $source.VerticalResolution)

		$graphics = [System.Drawing.Graphics]::FromImage($bitmap)

		try {
			$graphics.Clear([System.Drawing.Color]::Transparent)
			$graphics.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
			$graphics.CompositingQuality = [System.Drawing.Drawing2D.CompositingQuality]::HighQuality
			$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
			$graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
			$graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
			$graphics.DrawImage($source, 0, 0, $Width, $Height)
		}
		finally {
			$graphics.Dispose()
		}

		return $bitmap
	}
	finally {
		$source.Dispose()
	}
}

function Save-PngAsset {
	param(
		[Parameter(Mandatory = $true)]
		[string]$SourcePath,

		[Parameter(Mandatory = $true)]
		[string]$OutputPath,

		[Parameter(Mandatory = $true)]
		[int]$Width,

		[Parameter(Mandatory = $true)]
		[int]$Height
	)

	Ensure-Directory $OutputPath

	$bitmap = New-ResizedBitmap -SourcePath $SourcePath -Width $Width -Height $Height

	try {
		$bitmap.Save($OutputPath, [System.Drawing.Imaging.ImageFormat]::Png)
	}
	finally {
		$bitmap.Dispose()
	}
}

function Save-IcoAsset {
	param(
		[Parameter(Mandatory = $true)]
		[string]$SourcePath,

		[Parameter(Mandatory = $true)]
		[string]$OutputPath,

		[Parameter(Mandatory = $true)]
		[int]$Size
	)

	Ensure-Directory $OutputPath

	$bitmap = New-ResizedBitmap -SourcePath $SourcePath -Width $Size -Height $Size
	$pngStream = New-Object System.IO.MemoryStream

	try {
		$bitmap.Save($pngStream, [System.Drawing.Imaging.ImageFormat]::Png)
		$pngBytes = $pngStream.ToArray()
	}
	finally {
		$pngStream.Dispose()
		$bitmap.Dispose()
	}

	$fileStream = [System.IO.File]::Create($OutputPath)
	$writer = New-Object System.IO.BinaryWriter $fileStream

	try {
		$dimension = if ($Size -ge 256) { 0 } else { [byte]$Size }
		$imageOffset = 22

		$writer.Write([UInt16]0)
		$writer.Write([UInt16]1)
		$writer.Write([UInt16]1)
		$writer.Write([byte]$dimension)
		$writer.Write([byte]$dimension)
		$writer.Write([byte]0)
		$writer.Write([byte]0)
		$writer.Write([UInt16]1)
		$writer.Write([UInt16]32)
		$writer.Write([UInt32]$pngBytes.Length)
		$writer.Write([UInt32]$imageOffset)
		$writer.Write($pngBytes)
	}
	finally {
		$writer.Dispose()
		$fileStream.Dispose()
	}
}

function Save-SvgAsset {
	param(
		[Parameter(Mandatory = $true)]
		[string]$SourcePath,

		[Parameter(Mandatory = $true)]
		[string]$OutputPath,

		[Parameter(Mandatory = $true)]
		[int]$Width,

		[Parameter(Mandatory = $true)]
		[int]$Height
	)

	Ensure-Directory $OutputPath

	$bitmap = New-ResizedBitmap -SourcePath $SourcePath -Width $Width -Height $Height
	$pngStream = New-Object System.IO.MemoryStream

	try {
		$bitmap.Save($pngStream, [System.Drawing.Imaging.ImageFormat]::Png)
		$base64 = [Convert]::ToBase64String($pngStream.ToArray())
	}
	finally {
		$pngStream.Dispose()
		$bitmap.Dispose()
	}

	$svg = @"
<svg xmlns="http://www.w3.org/2000/svg" width="$Width" height="$Height" viewBox="0 0 $Width $Height">
  <image width="$Width" height="$Height" href="data:image/png;base64,$base64" />
</svg>
"@

	$utf8NoBom = New-Object System.Text.UTF8Encoding $false
	[System.IO.File]::WriteAllText($OutputPath, $svg, $utf8NoBom)
}

if (-not (Test-Path $DarkMark)) {
	throw "Missing source asset: $DarkMark"
}

if (-not (Test-Path $LightMark)) {
	throw "Missing source asset: $LightMark"
}

$pngTargets = @(
	@{ Source = $DarkMark; Path = 'static\favicon.png'; Width = 512; Height = 512 },
	@{ Source = $DarkMark; Path = 'static\static\favicon.png'; Width = 512; Height = 512 },
	@{ Source = $LightMark; Path = 'static\static\favicon-dark.png'; Width = 500; Height = 500 },
	@{ Source = $DarkMark; Path = 'static\static\favicon-96x96.png'; Width = 96; Height = 96 },
	@{ Source = $DarkMark; Path = 'static\static\apple-touch-icon.png'; Width = 180; Height = 180 },
	@{ Source = $DarkMark; Path = 'static\static\logo.png'; Width = 500; Height = 500 },
	@{ Source = $DarkMark; Path = 'static\static\splash.png'; Width = 500; Height = 500 },
	@{ Source = $LightMark; Path = 'static\static\splash-dark.png'; Width = 500; Height = 500 },
	@{ Source = $DarkMark; Path = 'static\static\web-app-manifest-192x192.png'; Width = 192; Height = 192 },
	@{ Source = $DarkMark; Path = 'static\static\web-app-manifest-512x512.png'; Width = 512; Height = 512 },
	@{ Source = $DarkMark; Path = 'backend\open_webui\static\favicon.png'; Width = 512; Height = 512 },
	@{ Source = $LightMark; Path = 'backend\open_webui\static\favicon-dark.png'; Width = 500; Height = 500 },
	@{ Source = $DarkMark; Path = 'backend\open_webui\static\splash.png'; Width = 500; Height = 500 },
	@{ Source = $LightMark; Path = 'backend\open_webui\static\splash-dark.png'; Width = 500; Height = 500 },
	@{ Source = $DarkMark; Path = 'backend\open_webui\static\web-app-manifest-192x192.png'; Width = 192; Height = 192 },
	@{ Source = $DarkMark; Path = 'backend\open_webui\static\web-app-manifest-512x512.png'; Width = 512; Height = 512 }
)

foreach ($target in $pngTargets) {
	$outputPath = Join-Path $RepoRoot $target.Path
	Save-PngAsset -SourcePath $target.Source -OutputPath $outputPath -Width $target.Width -Height $target.Height
}

Save-IcoAsset -SourcePath $DarkMark -OutputPath (Join-Path $RepoRoot 'static\static\favicon.ico') -Size 256
Save-SvgAsset -SourcePath $DarkMark -OutputPath (Join-Path $RepoRoot 'static\static\favicon.svg') -Width 512 -Height 512

Write-Output 'ArtiChat assets generated.'
