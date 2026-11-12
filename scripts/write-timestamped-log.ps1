# Prefix each redirected server output line with an ISO 8601 local timestamp.
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
while ($null -ne ($line = [Console]::In.ReadLine())) {
    $timestamp = [DateTimeOffset]::Now.ToString('yyyy-MM-ddTHH:mm:ss.fffzzz')
    [Console]::Out.WriteLine("[$timestamp] $line")
}
