$server = "192.168.1.45"
$count = 100

$domains = @(
    "google.com",
    "fadexplosion.com",
    "cnn.com",
    "ptosesveg.com",
    "webjudionline.com",
    "softoutfit.com"
)

$ok = 0
$fail = 0

$sw = [Diagnostics.Stopwatch]::StartNew()

for ($i = 0; $i -lt $count; $i++) {
    $domain = $domains[$i % $domains.Count]

    try {
        $result = Resolve-DnsName $domain -Server $server -Type A -ErrorAction Stop
        $ok++
        #Write-Host "Success $($ok)"
    }
    catch {
        $fail++
        #Write-Host "Error: $($_.Exception.Message)"
    }
}

$sw.Stop()

$seconds = $sw.Elapsed.TotalSeconds
$qps = $count / $seconds

"Queries:       $count"
"Successful:    $ok"
"Failed:        $fail"
"Time:          {0:N2} seconds" -f $seconds
"Speed:         {0:N1} queries/sec" -f $qps
