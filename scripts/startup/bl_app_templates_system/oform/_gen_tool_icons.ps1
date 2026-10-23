# SketchUp Large Tool Set–style glyphs for O-Form (simple flat icons).
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$Out = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "icons"
New-Item -ItemType Directory -Force -Path $Out | Out-Null

$Ink = [System.Drawing.ColorTranslator]::FromHtml("#1A1A1A")
$Red = [System.Drawing.ColorTranslator]::FromHtml("#E03C31")
$Yellow = [System.Drawing.ColorTranslator]::FromHtml("#E8B923")
$Grey = [System.Drawing.ColorTranslator]::FromHtml("#8A8A8A")
$Tan = [System.Drawing.ColorTranslator]::FromHtml("#C4A574")
$Pink = [System.Drawing.ColorTranslator]::FromHtml("#E89AA8")
$Size = 64

function New-Canvas {
    $bmp = New-Object System.Drawing.Bitmap $Size, $Size, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear([System.Drawing.Color]::Transparent)
    return @{ B = $bmp; G = $g }
}

function Save-Icon($name, $draw) {
    $c = New-Canvas
    & $draw $c.G
    $c.G.Dispose()
    $path = Join-Path $Out ($name + ".png")
    $c.B.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $c.B.Dispose()
}

function Pen($color, $w = 3.0) {
    $p = New-Object System.Drawing.Pen $color, $w
    $p.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $p.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $p.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    return $p
}

# Select — black arrow pointer
Save-Icon "select" {
    param($g)
    $brush = New-Object System.Drawing.SolidBrush $Ink
    $pts = @(
        (New-Object System.Drawing.PointF 16,12),
        (New-Object System.Drawing.PointF 16,48),
        (New-Object System.Drawing.PointF 26,38),
        (New-Object System.Drawing.PointF 36,52),
        (New-Object System.Drawing.PointF 42,48),
        (New-Object System.Drawing.PointF 32,34),
        (New-Object System.Drawing.PointF 44,34)
    )
    $g.FillPolygon($brush, $pts)
    $brush.Dispose()
}

# Make Component — red-edged cube-ish box
Save-Icon "component" {
    param($g)
    $pen = Pen $Red 3
    $g.DrawRectangle($pen, 18, 22, 28, 24)
    $g.DrawLine($pen, 18, 22, 28, 14)
    $g.DrawLine($pen, 46, 22, 56, 14)
    $g.DrawLine($pen, 28, 14, 56, 14)
    $g.DrawLine($pen, 56, 14, 56, 38)
    $g.DrawLine($pen, 46, 46, 56, 38)
    $pen.Dispose()
}

# Paint bucket
Save-Icon "paint" {
    param($g)
    $pen = Pen $Ink 2.5
    $fill = New-Object System.Drawing.SolidBrush $Yellow
    $g.FillPolygon($fill, @(
        (New-Object System.Drawing.PointF 22,28),
        (New-Object System.Drawing.PointF 42,28),
        (New-Object System.Drawing.PointF 46,48),
        (New-Object System.Drawing.PointF 18,48)
    ))
    $g.DrawPolygon($pen, @(
        (New-Object System.Drawing.PointF 22,28),
        (New-Object System.Drawing.PointF 42,28),
        (New-Object System.Drawing.PointF 46,48),
        (New-Object System.Drawing.PointF 18,48)
    ))
    $g.DrawArc($pen, 24, 14, 16, 16, 200, 140)
    $spill = New-Object System.Drawing.SolidBrush $Yellow
    $g.FillEllipse($spill, 40, 44, 14, 10)
    $pen.Dispose(); $fill.Dispose(); $spill.Dispose()
}

# Eraser
Save-Icon "eraser" {
    param($g)
    $brush = New-Object System.Drawing.SolidBrush $Pink
    $pen = Pen $Ink 2
    $g.TranslateTransform(32, 32)
    $g.RotateTransform(-35)
    $g.FillRectangle($brush, -14, -8, 28, 16)
    $g.DrawRectangle($pen, -14, -8, 28, 16)
    $g.DrawLine($pen, 0, -8, 0, 8)
    $g.ResetTransform()
    $brush.Dispose(); $pen.Dispose()
}

# Line — red pencil
Save-Icon "line" {
    param($g)
    $pen = Pen $Red 3.5
    $g.DrawLine($pen, 14, 48, 50, 14)
    $tip = New-Object System.Drawing.SolidBrush $Ink
    $g.FillPolygon($tip, @(
        (New-Object System.Drawing.PointF 50,14),
        (New-Object System.Drawing.PointF 44,16),
        (New-Object System.Drawing.PointF 48,22)
    ))
    $pen.Dispose(); $tip.Dispose()
}

# Freehand
Save-Icon "freehand" {
    param($g)
    $pen = Pen $Red 3
    $g.DrawBezier($pen, 12, 40, 22, 12, 36, 52, 52, 20)
    $pen.Dispose()
}

# Rectangle
Save-Icon "rectangle" {
    param($g)
    $pen = Pen $Grey 2.5
    $g.DrawRectangle($pen, 14, 18, 36, 28)
    $diag = Pen $Red 2.5
    $g.DrawLine($diag, 14, 46, 50, 18)
    $pen.Dispose(); $diag.Dispose()
}

# Circle
Save-Icon "circle" {
    param($g)
    $pen = Pen $Grey 2.5
    $g.DrawEllipse($pen, 14, 14, 36, 36)
    $r = Pen $Red 2.5
    $g.DrawLine($r, 32, 32, 50, 32)
    $pen.Dispose(); $r.Dispose()
}

# Polygon (hex)
Save-Icon "polygon" {
    param($g)
    $pen = Pen $Grey 2.5
    $cx=32; $cy=32; $rad=18
    $pts = 0..5 | ForEach-Object {
        $a = [math]::PI/6 + $_ * [math]::PI/3
        New-Object System.Drawing.PointF ($cx + $rad*[math]::Cos($a)), ($cy + $rad*[math]::Sin($a))
    }
    $g.DrawPolygon($pen, [System.Drawing.PointF[]]$pts)
    $r = Pen $Red 2
    $g.DrawLine($r, 32, 32, 48, 32)
    $pen.Dispose(); $r.Dispose()
}

# Arc
Save-Icon "arc" {
    param($g)
    $pen = Pen $Red 3
    $g.DrawArc($pen, 12, 16, 40, 40, 200, 140)
    $pen.Dispose()
}

# Move
Save-Icon "move" {
    param($g)
    $pen = Pen $Red 2.5
    $g.DrawLine($pen, 32, 12, 32, 52)
    $g.DrawLine($pen, 12, 32, 52, 32)
    foreach ($poly in @(
        @((32,12),(28,20),(36,20)),
        @((32,52),(28,44),(36,44)),
        @((12,32),(20,28),(20,36)),
        @((52,32),(44,28),(44,36))
    )) {
        $brush = New-Object System.Drawing.SolidBrush $Red
        $g.FillPolygon($brush, @(
            (New-Object System.Drawing.PointF $poly[0][0], $poly[0][1]),
            (New-Object System.Drawing.PointF $poly[1][0], $poly[1][1]),
            (New-Object System.Drawing.PointF $poly[2][0], $poly[2][1])
        ))
        $brush.Dispose()
    }
    $pen.Dispose()
}

# Push/Pull
Save-Icon "push_pull" {
    param($g)
    $pen = Pen $Grey 2.5
    $g.DrawRectangle($pen, 16, 28, 32, 20)
    $g.DrawLine($pen, 16, 28, 24, 18)
    $g.DrawLine($pen, 48, 28, 56, 18)
    $g.DrawLine($pen, 24, 18, 56, 18)
    $g.DrawLine($pen, 56, 18, 56, 38)
    $g.DrawLine($pen, 48, 48, 56, 38)
    $arrow = Pen $Red 3
    $g.DrawLine($arrow, 32, 44, 32, 12)
    $brush = New-Object System.Drawing.SolidBrush $Red
    $g.FillPolygon($brush, @(
        (New-Object System.Drawing.PointF 32,10),
        (New-Object System.Drawing.PointF 26,20),
        (New-Object System.Drawing.PointF 38,20)
    ))
    $pen.Dispose(); $arrow.Dispose(); $brush.Dispose()
}

# Rotate
Save-Icon "rotate" {
    param($g)
    $pen = Pen $Red 3
    $g.DrawArc($pen, 14, 14, 36, 36, 40, 260)
    $brush = New-Object System.Drawing.SolidBrush $Red
    $g.FillPolygon($brush, @(
        (New-Object System.Drawing.PointF 44,14),
        (New-Object System.Drawing.PointF 52,22),
        (New-Object System.Drawing.PointF 40,24)
    ))
    $pen.Dispose(); $brush.Dispose()
}

# Follow Me
Save-Icon "follow_me" {
    param($g)
    $pen = Pen $Grey 2.5
    $g.DrawLines($pen, @(
        (New-Object System.Drawing.PointF 14,44),
        (New-Object System.Drawing.PointF 14,28),
        (New-Object System.Drawing.PointF 30,28),
        (New-Object System.Drawing.PointF 30,44)
    ))
    $path = Pen $Red 3
    $g.DrawBezier($path, 30, 36, 40, 20, 48, 48, 54, 18)
    $pen.Dispose(); $path.Dispose()
}

# Scale
Save-Icon "scale" {
    param($g)
    $pen = Pen $Grey 2.5
    $g.DrawRectangle($pen, 16, 16, 28, 28)
    $a = Pen $Red 2.5
    $g.DrawLine($a, 44, 44, 54, 54)
    $brush = New-Object System.Drawing.SolidBrush $Red
    $g.FillRectangle($brush, 40, 40, 8, 8)
    $g.FillRectangle($brush, 50, 50, 8, 8)
    $pen.Dispose(); $a.Dispose(); $brush.Dispose()
}

# Offset
Save-Icon "offset" {
    param($g)
    $pen = Pen $Grey 2.5
    $g.DrawRectangle($pen, 14, 14, 36, 36)
    $g.DrawRectangle($pen, 22, 22, 20, 20)
    $a = Pen $Red 2.5
    $g.DrawLine($a, 32, 14, 32, 22)
    $pen.Dispose(); $a.Dispose()
}

# Tape
Save-Icon "tape" {
    param($g)
    $pen = Pen $Yellow 4
    $g.DrawLine($pen, 12, 48, 52, 16)
    $tick = Pen $Ink 2
    $g.DrawLine($tick, 20, 42, 24, 38)
    $g.DrawLine($tick, 30, 34, 34, 30)
    $g.DrawLine($tick, 40, 26, 44, 22)
    $pen.Dispose(); $tick.Dispose()
}

# Protractor
Save-Icon "protractor" {
    param($g)
    $pen = Pen $Yellow 3
    $g.DrawArc($pen, 10, 18, 44, 44, 180, 180)
    $g.DrawLine($pen, 10, 40, 54, 40)
    $ink = Pen $Ink 2
    $g.DrawLine($ink, 32, 40, 32, 22)
    $pen.Dispose(); $ink.Dispose()
}

# Back edges / axes-ish
Save-Icon "back_edges" {
    param($g)
    $x = Pen ([System.Drawing.ColorTranslator]::FromHtml("#E03C31")) 3
    $y = Pen ([System.Drawing.ColorTranslator]::FromHtml("#3FA36A")) 3
    $z = Pen ([System.Drawing.ColorTranslator]::FromHtml("#3B7DD8")) 3
    $g.DrawLine($x, 32, 40, 54, 40)
    $g.DrawLine($y, 32, 40, 18, 52)
    $g.DrawLine($z, 32, 40, 32, 12)
    $x.Dispose(); $y.Dispose(); $z.Dispose()
}

# Orbit
Save-Icon "orbit" {
    param($g)
    $pen = Pen $Ink 2
    $g.DrawEllipse($pen, 16, 16, 32, 32)
    $a = Pen $Red 2.5
    $g.DrawArc($a, 12, 20, 40, 28, 200, 140)
    $b = Pen ([System.Drawing.ColorTranslator]::FromHtml("#3FA36A")) 2.5
    $g.DrawArc($b, 20, 12, 28, 40, 110, 140)
    $pen.Dispose(); $a.Dispose(); $b.Dispose()
}

# Pan — hand
Save-Icon "pan" {
    param($g)
    $brush = New-Object System.Drawing.SolidBrush $Tan
    $pen = Pen $Ink 2
    $g.FillEllipse($brush, 22, 18, 20, 28)
    $g.DrawEllipse($pen, 22, 18, 20, 28)
    $g.FillRectangle($brush, 18, 28, 28, 16)
    $g.DrawRectangle($pen, 18, 28, 28, 16)
    $brush.Dispose(); $pen.Dispose()
}

# Zoom
Save-Icon "zoom" {
    param($g)
    $pen = Pen $Ink 3
    $g.DrawEllipse($pen, 12, 12, 28, 28)
    $g.DrawLine($pen, 36, 36, 52, 52)
    $pen.Dispose()
}

# Zoom extents
Save-Icon "zoom_extents" {
    param($g)
    $pen = Pen $Ink 2.5
    $g.DrawEllipse($pen, 14, 14, 24, 24)
    $g.DrawLine($pen, 34, 34, 46, 46)
    $a = Pen $Red 2
    $g.DrawLine($a, 10, 10, 18, 10); $g.DrawLine($a, 10, 10, 10, 18)
    $g.DrawLine($a, 54, 10, 46, 10); $g.DrawLine($a, 54, 10, 54, 18)
    $g.DrawLine($a, 10, 54, 18, 54); $g.DrawLine($a, 10, 54, 10, 46)
    $g.DrawLine($a, 54, 54, 46, 54); $g.DrawLine($a, 54, 54, 54, 46)
    $pen.Dispose(); $a.Dispose()
}

Write-Host "Wrote SketchUp-style tool icons to $Out"
Get-ChildItem $Out -Filter *.png | Select-Object -ExpandProperty Name
