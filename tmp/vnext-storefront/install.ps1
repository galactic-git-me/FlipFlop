$ErrorActionPreference = 'Stop'
$shop = 'C:\Users\mclar\CODING\FlipFlop.shop'
$stage = 'C:\Users\mclar\CODING\FlipFlop\tmp\vnext-storefront'
if (-not (Test-Path -LiteralPath (Join-Path $shop 'package.json'))) { throw 'Storefront target not found' }
$target = Join-Path $shop 'app\find-my-pc'
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -LiteralPath (Join-Path $stage 'app\find-my-pc\page.tsx') -Destination (Join-Path $target 'page.tsx')
Copy-Item -LiteralPath (Join-Path $stage 'app\find-my-pc\FindMyPcJourney.tsx') -Destination (Join-Path $target 'FindMyPcJourney.tsx')

$configPath = Join-Path $shop 'next.config.ts'
$config = Get-Content -LiteralPath $configPath -Raw
$rewrite = '      { source: "/api/recommendations/:path*", destination: `${backendUrl}/api/recommendations/:path*` },'
if (-not $config.Contains($rewrite)) {
    $marker = '      { source: "/studio-assets/:path*", destination: `${backendUrl}/media/:path*` },'
    if (-not $config.Contains($marker)) { throw 'Expected rewrite marker missing' }
    $config = $config.Replace($marker, "$marker`r`n$rewrite")
    Set-Content -LiteralPath $configPath -Value $config -NoNewline
}

$layoutPath = Join-Path $shop 'app\layout.tsx'
$layout = Get-Content -LiteralPath $layoutPath -Raw
$oldLink = '<Link href="/start" className="nav-start-link" aria-label="Start Here">'
$newLink = '<Link href="/find-my-pc" className="nav-start-link" aria-label="Find My PC">'
if ($layout.Contains($oldLink)) {
    $layout = $layout.Replace($oldLink, $newLink)
    Set-Content -LiteralPath $layoutPath -Value $layout -NoNewline
} elseif (-not $layout.Contains($newLink)) { throw 'Expected navigation marker missing' }

$ctaPath = Join-Path $shop 'components\home\FinalCTA.tsx'
$cta = Get-Content -LiteralPath $ctaPath -Raw
$cta = $cta.Replace('Ready to build?', 'The right PC. Without needing to become a PC expert.')
$cta = $cta.Replace('href="/start" variant="primary" autoAnimate>Build your machine', 'href="/find-my-pc" variant="primary" autoAnimate>Find my PC')
Set-Content -LiteralPath $ctaPath -Value $cta -NoNewline

$homePath = Join-Path $shop 'app\page.tsx'
$home = Get-Content -LiteralPath $homePath -Raw
$home = $home.Replace('import StartupExperience from "@/components/home/StartupExperience";', 'import Hero from "@/components/home/Hero";')
$home = $home.Replace('<StartupExperience />', '<Hero />')
Set-Content -LiteralPath $homePath -Value $home -NoNewline
Write-Output 'Installed guided journey, API proxy, homepage CTA and immediate hero.'
