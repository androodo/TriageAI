$content = [System.IO.File]::ReadAllBytes("c:\Personal Project\backend\app\services\similarity.py")
$text = [System.Text.Encoding]::UTF8.GetString($content)
$text = $text -replace "None else \x00\.0", "None else 0.0"
$bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
[System.IO.File]::WriteAllBytes("c:\Personal Project\backend\app\services\similarity.py", $bytes)
Write-Host "Fixed"