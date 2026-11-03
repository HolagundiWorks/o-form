# O-Form tool glyphs: 20px art, 1.5px stroke, exported at 4x so the stroke stays sharp.
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$Out = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "icons"
New-Item -ItemType Directory -Force -Path $Out | Out-Null

$Logical = 20.0
$Scale = 4.0
$Size = [int]($Logical * $Scale)
$Stroke = [single](1.5 * $Scale)

$Ink = [System.Drawing.ColorTranslator]::FromHtml("#102C80")   # Midnight, the suite ink
$Red = [System.Drawing.ColorTranslator]::FromHtml("#E03C31")
$Yellow = [System.Drawing.ColorTranslator]::FromHtml("#E8B923")
$Grey = [System.Drawing.ColorTranslator]::FromHtml("#546B88")
$Tan = [System.Drawing.ColorTranslator]::FromHtml("#C4A574")
$Pink = [System.Drawing.ColorTranslator]::FromHtml("#E89AA8")
$Green = [System.Drawing.ColorTranslator]::FromHtml("#166040")   # Grove
$Blue = [System.Drawing.ColorTranslator]::FromHtml("#3B7DD8")

function New-Canvas {
    $bmp = New-Object System.Drawing.Bitmap $Size, $Size, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
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

function Pen($color) {
    $p = New-Object System.Drawing.Pen $color, $Stroke
    $p.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $p.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $p.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    return $p
}

function Pt($x, $y) {
    return New-Object System.Drawing.PointF ([single]($x * $Scale)), ([single]($y * $Scale))
}

function Poly($pairs) {
    return @($pairs | ForEach-Object { Pt $_[0] $_[1] })
}

# Select — stroked pointer
Save-Icon "select" {
    param($g)
    $pen = Pen $Ink
    $g.DrawPolygon($pen, [System.Drawing.PointF[]](Poly @(
        @(4.5,3.2), @(4.5,16.2), @(8.2,12.6), @(11.6,17.2), @(13.6,15.8), @(10.2,11.2), @(14.6,11.2)
    )))
    $pen.Dispose()
}

# Make Component
Save-Icon "component" {
    param($g)
    $pen = Pen $Red
    $g.DrawPolygon($pen, [System.Drawing.PointF[]](Poly @(
        @(5,8), @(9,5.5), @(15,5.5), @(15,12.5), @(11,15), @(5,15)
    )))
    $g.DrawLine($pen, (Pt 5 8), (Pt 11 8))
    $g.DrawLine($pen, (Pt 11 8), (Pt 15 5.5))
    $g.DrawLine($pen, (Pt 11 8), (Pt 11 15))
    $pen.Dispose()
}

# Paint bucket
Save-Icon "paint" {
    param($g)
    $pen = Pen $Ink
    $fill = New-Object System.Drawing.SolidBrush $Yellow
    $pts = [System.Drawing.PointF[]](Poly @(@(6.5,8.5), @(12.5,8.5), @(14,15.5), @(5,15.5)))
    $g.FillPolygon($fill, $pts)
    $g.DrawPolygon($pen, $pts)
    $g.DrawArc($pen, (4.5*$Scale), (3.2*$Scale), (8*$Scale), (6*$Scale), 200, 140)
    $spill = New-Object System.Drawing.SolidBrush $Yellow
    $g.FillEllipse($spill, (12.2*$Scale), (13.6*$Scale), (4.2*$Scale), (3*$Scale))
    $pen.Dispose(); $fill.Dispose(); $spill.Dispose()
}

# Eraser
Save-Icon "eraser" {
    param($g)
    $brush = New-Object System.Drawing.SolidBrush $Pink
    $pen = Pen $Ink
    $g.TranslateTransform((10*$Scale), (10*$Scale))
    $g.RotateTransform(-35)
    $g.FillRectangle($brush, (-5*$Scale), (-2.4*$Scale), (10*$Scale), (4.8*$Scale))
    $g.DrawRectangle($pen, (-5*$Scale), (-2.4*$Scale), (10*$Scale), (4.8*$Scale))
    $g.DrawLine($pen, 0, (-2.4*$Scale), 0, (2.4*$Scale))
    $g.ResetTransform()
    $brush.Dispose(); $pen.Dispose()
}

# Line
Save-Icon "line" {
    param($g)
    $pen = Pen $Red
    $g.DrawLine($pen, (Pt 4.2 15.6), (Pt 15.2 4.4))
    $pen.Dispose()
}

# Freehand
Save-Icon "freehand" {
    param($g)
    $pen = Pen $Red
    $g.DrawBezier($pen, (Pt 3.5 13), (Pt 7 3.5), (Pt 12 16.5), (Pt 16.5 6))
    $pen.Dispose()
}

# Rectangle
Save-Icon "rectangle" {
    param($g)
    $pen = Pen $Grey
    $g.DrawRectangle($pen, (4*$Scale), (5*$Scale), (12*$Scale), (10*$Scale))
    $diag = Pen $Red
    $g.DrawLine($diag, (Pt 4 15), (Pt 16 5))
    $pen.Dispose(); $diag.Dispose()
}

# Circle
Save-Icon "circle" {
    param($g)
    $pen = Pen $Grey
    $g.DrawEllipse($pen, (4*$Scale), (4*$Scale), (12*$Scale), (12*$Scale))
    $r = Pen $Red
    $g.DrawLine($r, (Pt 10 10), (Pt 16 10))
    $pen.Dispose(); $r.Dispose()
}

# Polygon
Save-Icon "polygon" {
    param($g)
    $pen = Pen $Grey
    $pts = 0..5 | ForEach-Object {
        $a = [math]::PI/6 + $_ * [math]::PI/3
        Pt (10 + 6.2*[math]::Cos($a)) (10 + 6.2*[math]::Sin($a))
    }
    $g.DrawPolygon($pen, [System.Drawing.PointF[]]$pts)
    $r = Pen $Red
    $g.DrawLine($r, (Pt 10 10), (Pt 15.5 10))
    $pen.Dispose(); $r.Dispose()
}

# Arc
Save-Icon "arc" {
    param($g)
    $pen = Pen $Red
    $g.DrawArc($pen, (3.5*$Scale), (4.5*$Scale), (13*$Scale), (13*$Scale), 200, 140)
    $pen.Dispose()
}

# Move
Save-Icon "move" {
    param($g)
    $pen = Pen $Red
    $g.DrawLine($pen, (Pt 10 3.2), (Pt 10 16.8))
    $g.DrawLine($pen, (Pt 3.2 10), (Pt 16.8 10))
    foreach ($poly in @(
        @(@(10,3.2), @(8.2,5.6), @(11.8,5.6)),
        @(@(10,16.8), @(8.2,14.4), @(11.8,14.4)),
        @(@(3.2,10), @(5.6,8.2), @(5.6,11.8)),
        @(@(16.8,10), @(14.4,8.2), @(14.4,11.8))
    )) {
        $g.DrawPolygon($pen, [System.Drawing.PointF[]](Poly $poly))
    }
    $pen.Dispose()
}

# Copy — two offset squares
Save-Icon "copy" {
    param($g)
    $pen = Pen $Ink
    $g.DrawRectangle($pen, (7*$Scale), (4*$Scale), (8.5*$Scale), (8.5*$Scale))
    $g.DrawRectangle($pen, (4*$Scale), (7.5*$Scale), (8.5*$Scale), (8.5*$Scale))
    $pen.Dispose()
}

# Push/Pull
Save-Icon "push_pull" {
    param($g)
    $pen = Pen $Grey
    $g.DrawPolygon($pen, [System.Drawing.PointF[]](Poly @(
        @(4.5,9), @(7.5,6.5), @(15.5,6.5), @(15.5,13), @(12.5,15.5), @(4.5,15.5)
    )))
    $g.DrawLine($pen, (Pt 4.5 9), (Pt 12.5 9))
    $g.DrawLine($pen, (Pt 12.5 9), (Pt 15.5 6.5))
    $g.DrawLine($pen, (Pt 12.5 9), (Pt 12.5 15.5))
    $arrow = Pen $Red
    $g.DrawLine($arrow, (Pt 9 14.5), (Pt 9 3.4))
    $g.DrawPolygon($arrow, [System.Drawing.PointF[]](Poly @(@(9,3.2), @(7.2,5.6), @(10.8,5.6))))
    $pen.Dispose(); $arrow.Dispose()
}

# Trim — edge and a cutter
Save-Icon "trim" {
    param($g)
    $pen = Pen $Grey
    $g.DrawLine($pen, (Pt 4 15.5), (Pt 4 4.5))
    $g.DrawLine($pen, (Pt 4 4.5), (Pt 15.5 4.5))
    $cut = Pen $Red
    $g.DrawLine($cut, (Pt 7.5 12.5), (Pt 15.5 4.5))
    $pen.Dispose(); $cut.Dispose()
}

# Rotate
Save-Icon "rotate" {
    param($g)
    $pen = Pen $Red
    $g.DrawArc($pen, (4*$Scale), (4*$Scale), (12*$Scale), (12*$Scale), 40, 270)
    $g.DrawPolygon($pen, [System.Drawing.PointF[]](Poly @(@(14.2,4.2), @(16.6,6.6), @(13.2,7.2))))
    $pen.Dispose()
}

# Follow Me
Save-Icon "follow_me" {
    param($g)
    $pen = Pen $Grey
    $g.DrawLines($pen, [System.Drawing.PointF[]](Poly @(
        @(4,14.5), @(4,8.5), @(9.5,8.5), @(9.5,14.5)
    )))
    $path = Pen $Red
    $g.DrawBezier($path, (Pt 9.5 11.5), (Pt 12.5 5), (Pt 15 15), (Pt 17 6))
    $pen.Dispose(); $path.Dispose()
}

# Scale
Save-Icon "scale" {
    param($g)
    $pen = Pen $Grey
    $g.DrawRectangle($pen, (4*$Scale), (4*$Scale), (8.5*$Scale), (8.5*$Scale))
    $a = Pen $Red
    $g.DrawLine($a, (Pt 12.5 12.5), (Pt 16.5 16.5))
    $g.DrawRectangle($a, (11.2*$Scale), (11.2*$Scale), (2.4*$Scale), (2.4*$Scale))
    $g.DrawRectangle($a, (15*$Scale), (15*$Scale), (2.2*$Scale), (2.2*$Scale))
    $pen.Dispose(); $a.Dispose()
}

# Offset
Save-Icon "offset" {
    param($g)
    $pen = Pen $Grey
    $g.DrawRectangle($pen, (3.8*$Scale), (3.8*$Scale), (12.4*$Scale), (12.4*$Scale))
    $g.DrawRectangle($pen, (7*$Scale), (7*$Scale), (6*$Scale), (6*$Scale))
    $a = Pen $Red
    $g.DrawLine($a, (Pt 10 3.8), (Pt 10 7))
    $pen.Dispose(); $a.Dispose()
}

# Tape
Save-Icon "tape" {
    param($g)
    $pen = Pen $Yellow
    $g.DrawLine($pen, (Pt 3.5 15.5), (Pt 16.2 4.2))
    $tick = Pen $Ink
    $g.DrawLine($tick, (Pt 6.2 13.2), (Pt 7.6 11.8))
    $g.DrawLine($tick, (Pt 9.4 10.2), (Pt 10.8 8.8))
    $g.DrawLine($tick, (Pt 12.6 7.2), (Pt 14 5.8))
    $pen.Dispose(); $tick.Dispose()
}

# Protractor
Save-Icon "protractor" {
    param($g)
    $pen = Pen $Yellow
    $g.DrawArc($pen, (3*$Scale), (5*$Scale), (14*$Scale), (14*$Scale), 180, 180)
    $g.DrawLine($pen, (Pt 3 12), (Pt 17 12))
    $ink = Pen $Ink
    $g.DrawLine($ink, (Pt 10 12), (Pt 10 6.2))
    $pen.Dispose(); $ink.Dispose()
}

# Back edges
Save-Icon "back_edges" {
    param($g)
    $x = Pen $Red
    $y = Pen $Green
    $z = Pen $Blue
    $g.DrawLine($x, (Pt 10 12), (Pt 17 12))
    $g.DrawLine($y, (Pt 10 12), (Pt 5.5 16.2))
    $g.DrawLine($z, (Pt 10 12), (Pt 10 4))
    $x.Dispose(); $y.Dispose(); $z.Dispose()
}

# Orbit
Save-Icon "orbit" {
    param($g)
    $pen = Pen $Ink
    $g.DrawEllipse($pen, (5*$Scale), (5*$Scale), (10*$Scale), (10*$Scale))
    $a = Pen $Red
    $g.DrawArc($a, (3.5*$Scale), (6.5*$Scale), (13*$Scale), (8*$Scale), 200, 140)
    $b = Pen $Green
    $g.DrawArc($b, (6.5*$Scale), (3.5*$Scale), (8*$Scale), (13*$Scale), 110, 140)
    $pen.Dispose(); $a.Dispose(); $b.Dispose()
}

# Pan
Save-Icon "pan" {
    param($g)
    $pen = Pen $Ink
    $g.DrawEllipse($pen, (7*$Scale), (3.5*$Scale), (6*$Scale), (6*$Scale))
    $g.DrawLine($pen, (Pt 8.2 8.8), (Pt 8.2 15.5))
    $g.DrawLine($pen, (Pt 11.8 8.8), (Pt 11.8 15.5))
    $g.DrawArc($pen, (6.5*$Scale), (12*$Scale), (7*$Scale), (5*$Scale), 10, 160)
    $pen.Dispose()
}

# Zoom
Save-Icon "zoom" {
    param($g)
    $pen = Pen $Ink
    $g.DrawEllipse($pen, (3.5*$Scale), (3.5*$Scale), (9*$Scale), (9*$Scale))
    $g.DrawLine($pen, (Pt 11.2 11.2), (Pt 16.4 16.4))
    $pen.Dispose()
}

# Zoom extents
Save-Icon "zoom_extents" {
    param($g)
    $pen = Pen $Ink
    $g.DrawEllipse($pen, (5.5*$Scale), (5.5*$Scale), (7*$Scale), (7*$Scale))
    $g.DrawLine($pen, (Pt 11.2 11.2), (Pt 14.2 14.2))
    $a = Pen $Red
    $g.DrawLine($a, (Pt 3.2 3.2), (Pt 6.2 3.2)); $g.DrawLine($a, (Pt 3.2 3.2), (Pt 3.2 6.2))
    $g.DrawLine($a, (Pt 16.8 3.2), (Pt 13.8 3.2)); $g.DrawLine($a, (Pt 16.8 3.2), (Pt 16.8 6.2))
    $g.DrawLine($a, (Pt 3.2 16.8), (Pt 6.2 16.8)); $g.DrawLine($a, (Pt 3.2 16.8), (Pt 3.2 13.8))
    $g.DrawLine($a, (Pt 16.8 16.8), (Pt 13.8 16.8)); $g.DrawLine($a, (Pt 16.8 16.8), (Pt 16.8 13.8))
    $pen.Dispose(); $a.Dispose()
}

# Customize
Save-Icon "gear" {
    param($g)
    $pen = Pen $Ink
    $g.DrawEllipse($pen, (7.2*$Scale), (7.2*$Scale), (5.6*$Scale), (5.6*$Scale))
    for ($i = 0; $i -lt 8; $i++) {
        $a = $i * [math]::PI / 4
        $g.DrawLine(
            $pen,
            (Pt (10 + 4.2*[math]::Cos($a)) (10 + 4.2*[math]::Sin($a))),
            (Pt (10 + 6.6*[math]::Cos($a)) (10 + 6.6*[math]::Sin($a)))
        )
    }
    $pen.Dispose()
}

Write-Host "Wrote 20px / 1.5px tool icons to $Out"
