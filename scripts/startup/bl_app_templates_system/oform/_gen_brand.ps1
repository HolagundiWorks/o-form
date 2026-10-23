# Regenerates O-Form suite mark assets (pastel green plate, ink glyph).
# Same geometry as hcw-ui tools/Brand: C + lower arc + centre ring in a 194 box.
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$OutDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Accent = [System.Drawing.ColorTranslator]::FromHtml("#C6E6D3")
$Ink = [System.Drawing.ColorTranslator]::FromHtml("#1A1A1A")
$InkSoft = [System.Drawing.ColorTranslator]::FromHtml("#5C5C5C")
$White = [System.Drawing.Color]::White

function New-Bitmap([int]$w, [int]$h) {
    New-Object System.Drawing.Bitmap $w, $h, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
}

function Get-Canvas([System.Drawing.Bitmap]$bitmap) {
    $g = [System.Drawing.Graphics]::FromImage($bitmap)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $g.Clear([System.Drawing.Color]::Transparent)
    return $g
}

function Get-Rounded([float]$x, [float]$y, [float]$w, [float]$h, [float]$r) {
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddArc($x, $y, 2 * $r, 2 * $r, 180, 90)
    $path.AddArc($x + $w - 2 * $r, $y, 2 * $r, 2 * $r, 270, 90)
    $path.AddArc($x + $w - 2 * $r, $y + $h - 2 * $r, 2 * $r, 2 * $r, 0, 90)
    $path.AddArc($x, $y + $h - 2 * $r, 2 * $r, 2 * $r, 90, 90)
    $path.CloseFigure()
    return $path
}

function Draw-Mark(
    [System.Drawing.Graphics]$g,
    [float]$x,
    [float]$y,
    [float]$size,
    [bool]$full = $true
) {
    $state = $g.Save()
    $s = $size / 194.0
    $g.TranslateTransform($x, $y)
    $g.ScaleTransform($s, $s)
    $g.TranslateTransform(-31, -31)
    $brush = New-Object System.Drawing.SolidBrush $Accent
    if ($full) {
        $path = Get-Rounded 31 31 194 194 34
        $g.FillPath($brush, $path)
        $path.Dispose()
    } else {
        $g.FillRectangle($brush, 31, 31, 194, 194)
    }
    $brush.Dispose()
    $pen = New-Object System.Drawing.Pen $Ink
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Flat
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Flat
    $pen.Width = 18
    $g.DrawArc($pen, 138 - 69, 127 - 69, 138, 138, 90, 180)
    $pen.Width = 12
    $g.DrawArc($pen, 138 - 50, 127 - 50, 100, 100, 0, 180)
    $pen.Width = 5
    $g.DrawEllipse($pen, 138 - 18.5, 127 - 18.5, 37, 37)
    $pen.Dispose()
    $g.Restore($state)
}

function Save-Mark([int]$size, [string]$path) {
    $bmp = New-Bitmap $size $size
    $g = Get-Canvas $bmp
    Draw-Mark $g 0 0 $size $true
    $g.Dispose()
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

function Save-Splash([string]$path) {
    $w = 960; $h = 420
    $bmp = New-Bitmap $w $h
    $g = Get-Canvas $bmp
    $g.Clear($White)
    $markSize = 280
    Draw-Mark $g 48 (($h - $markSize) / 2) $markSize $true
    $title = New-Object System.Drawing.Font "Segoe UI Semibold", 64, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
    $sub = New-Object System.Drawing.Font "Segoe UI", 28, ([System.Drawing.FontStyle]::Regular), ([System.Drawing.GraphicsUnit]::Pixel)
    $inkBrush = New-Object System.Drawing.SolidBrush $Ink
    $softBrush = New-Object System.Drawing.SolidBrush $InkSoft
    $g.DrawString("O-Form", $title, $inkBrush, 360, 140)
    $g.DrawString("Modeling", $sub, $softBrush, 364, 220)
    $title.Dispose(); $sub.Dispose(); $inkBrush.Dispose(); $softBrush.Dispose()
    $g.Dispose()
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
}

function Save-Ico([string]$path) {
    $sizes = @(16, 24, 32, 48, 64, 128, 256)
    $images = New-Object System.Collections.Generic.List[byte[]]
    foreach ($size in $sizes) {
        $bmp = New-Bitmap $size $size
        $g = Get-Canvas $bmp
        Draw-Mark $g 0 0 $size $true
        $g.Dispose()
        $ms = New-Object System.IO.MemoryStream
        $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
        $images.Add($ms.ToArray())
        $ms.Dispose()
        $bmp.Dispose()
    }
    $fs = [System.IO.File]::Create($path)
    $w = New-Object System.IO.BinaryWriter $fs
    $w.Write([uint16]0)
    $w.Write([uint16]1)
    $w.Write([uint16]$sizes.Length)
    $offset = 6 + 16 * $sizes.Length
    for ($i = 0; $i -lt $sizes.Length; $i++) {
        $s = $sizes[$i]
        $w.Write([byte]$(if ($s -eq 256) { 0 } else { $s }))
        $w.Write([byte]$(if ($s -eq 256) { 0 } else { $s }))
        $w.Write([byte]0)
        $w.Write([byte]0)
        $w.Write([uint16]1)
        $w.Write([uint16]32)
        $w.Write([int]$images[$i].Length)
        $w.Write([int]$offset)
        $offset += $images[$i].Length
    }
    foreach ($img in $images) { $w.Write($img) }
    $w.Flush(); $fs.Close()
}

Save-Mark 256 (Join-Path $OutDir "mark.png")
Save-Mark 256 (Join-Path $OutDir "mark-256.png")
Save-Splash (Join-Path $OutDir "splash.png")
Save-Ico (Join-Path $OutDir "app.ico")
Copy-Item (Join-Path $OutDir "app.ico") (Join-Path $OutDir "favicon.ico") -Force
Copy-Item (Join-Path $OutDir "app.ico") (Join-Path $OutDir "file.ico") -Force

$svg = @"
<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 194 194" width="194" height="194">
  <title>O-Form</title>
  <rect width="194" height="194" rx="34" ry="34" fill="#C6E6D3"/>
  <g fill="none" stroke="#1A1A1A">
    <path d="M107 27A69 69 0 0 0 107 165" stroke-width="18"/>
    <path d="M57 96A50 50 0 0 0 157 96" stroke-width="12"/>
    <circle cx="107" cy="96" r="18.5" stroke-width="5"/>
  </g>
</svg>
"@
Set-Content -Path (Join-Path $OutDir "mark.svg") -Value $svg -Encoding UTF8
Write-Host "Wrote brand assets to $OutDir"
