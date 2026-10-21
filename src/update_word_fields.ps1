# Refreshes the TOC, lists of figures/tables, captions and page numbers using Microsoft Word (Windows).
# Usage: powershell -ExecutionPolicy Bypass -File update_word_fields.ps1 -Docx <full path> [-Pdf <full path>]
param([string]$Docx, [string]$Pdf)
$ErrorActionPreference = "Stop"
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {
    $doc = $word.Documents.Open($Docx, $false, $false)
    # Update all fields in every story (body, headers, footers), then the TOC/LOF/LOT twice so page numbers settle
    foreach ($story in $doc.StoryRanges) {
        $r = $story
        while ($r -ne $null) { [void]$r.Fields.Update(); $r = $r.NextStoryRange }
    }
    for ($i = 0; $i -lt 2; $i++) {
        foreach ($t in $doc.TablesOfContents) { [void]$t.Update() }
        foreach ($t in $doc.TablesOfFigures) { [void]$t.Update() }
    }
    "Pages: " + $doc.ComputeStatistics(2)
    "TOCs: " + $doc.TablesOfContents.Count + " | TOFs: " + $doc.TablesOfFigures.Count
    $doc.Save()
    if ($Pdf) { $doc.ExportAsFixedFormat($Pdf, 17) ; "PDF exported" }
    $doc.Close($false)
} finally {
    $word.Quit()
    [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($word)
}
