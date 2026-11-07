# Print the client ID from MijnTed's public JavaScript.
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

try {
    $site = [Uri]'https://mijnted.nl/'
    $page = Invoke-WebRequest -Uri $site -UseBasicParsing -TimeoutSec 30
    $scriptPattern = '<script\b[^>]*\bsrc=["'']([^"'']+\.js)["'']'
    $clientPattern = '["''`]([a-f0-9]{8}-(?:[a-f0-9]{4}-){3}[a-f0-9]{12})["''`]\s*,\s*["''`]MyTedprod["''`]'
    $clientIds = @(
        foreach ($script in [regex]::Matches($page.Content, $scriptPattern, 'IgnoreCase')) {
            $scriptUri = [Uri]::new($site, $script.Groups[1].Value)
            if ($scriptUri.Scheme -ne 'https' -or $scriptUri.Host -ne $site.Host -or
                -not $scriptUri.AbsolutePath.StartsWith('/assets/')) {
                continue
            }
            $javascript = Invoke-WebRequest -Uri $scriptUri -UseBasicParsing -TimeoutSec 30
            foreach ($match in [regex]::Matches($javascript.Content, $clientPattern, 'IgnoreCase')) {
                $match.Groups[1].Value.ToLowerInvariant()
            }
        }
    ) | Sort-Object -Unique

    if (@($clientIds).Count -ne 1) {
        throw 'Could not identify a single MijnTed client ID. Use the browser method in the README.'
    }
    $clientIds
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
