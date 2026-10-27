$ErrorActionPreference = 'Stop'
$shop = 'C:\Users\mclar\CODING\FlipFlop.shop'
$stage = 'C:\Users\mclar\CODING\FlipFlop\tmp\vnext-storefront'
if (-not (Test-Path -LiteralPath (Join-Path $shop 'package.json'))) { throw 'Storefront target not found' }
$target = Join-Path $shop 'app\find-my-pc'
New-Item -ItemType Directory -Force -Path $target | Out-Null
Copy-Item -LiteralPath (Join-Path $stage 'app\find-my-pc\page.tsx') -Destination (Join-Path $target 'page.tsx')
Copy-Item -LiteralPath (Join-Path $stage 'app\find-my-pc\FindMyPcJourney.tsx') -Destination (Join-Path $target 'FindMyPcJourney.tsx')
$upgradeTarget = Join-Path $shop 'app\upgrade-my-pc'
New-Item -ItemType Directory -Force -Path $upgradeTarget | Out-Null
Copy-Item -LiteralPath (Join-Path $stage 'app\upgrade-my-pc\page.tsx') -Destination (Join-Path $upgradeTarget 'page.tsx')

$configPath = Join-Path $shop 'next.config.ts'
$config = Get-Content -LiteralPath $configPath -Raw
$rewrite = '      { source: "/api/recommendations/:path*", destination: `${backendUrl}/api/recommendations/:path*` },'
if (-not $config.Contains($rewrite)) {
    $marker = '      { source: "/studio-assets/:path*", destination: `${backendUrl}/media/:path*` },'
    if (-not $config.Contains($marker)) { throw 'Expected rewrite marker missing' }
    $config = $config.Replace($marker, "$marker`r`n$rewrite")
    Set-Content -LiteralPath $configPath -Value $config -NoNewline
}
$upgradeRewrite = '      { source: "/api/upgrades/:path*", destination: `${backendUrl}/api/upgrades/:path*` },'
if (-not $config.Contains($upgradeRewrite)) {
    $upgradeBaseRewrite = '      { source: "/api/upgrades", destination: `${backendUrl}/api/upgrades` },'
    $config = $config.Replace($rewrite, "$rewrite`r`n$upgradeBaseRewrite`r`n$upgradeRewrite")
    Set-Content -LiteralPath $configPath -Value $config -NoNewline
}

$layoutPath = Join-Path $shop 'app\layout.tsx'
$layout = Get-Content -LiteralPath $layoutPath -Raw
$oldLink = '<Link href="/start" className="nav-start-link" aria-label="Start Here">'
$newLink = '<Link href="/find-my-pc" className="nav-start-link" aria-label="Find My PC">'
if ($layout.Contains($oldLink)) {
    $layout = $layout.Replace($oldLink, $newLink)
} elseif (-not $layout.Contains($newLink)) { throw 'Expected navigation marker missing' }
$layout = $layout.Replace('<span className="nav-start-label">Start Here</span>', '<span className="nav-start-label">Find My PC</span>')
$upgradeNavMarker = '<Link href="/my-builds" className="nav-link nav-icon-link hidden sm:inline-flex"'
if (-not $layout.Contains('href="/upgrade-my-pc"')) {
    $layout = $layout.Replace($upgradeNavMarker, '<Link href="/upgrade-my-pc" className="nav-link hidden lg:inline-flex">Upgrade My PC</Link>' + "`r`n              " + $upgradeNavMarker)
}
Set-Content -LiteralPath $layoutPath -Value $layout -NoNewline

$ctaPath = Join-Path $shop 'components\home\FinalCTA.tsx'
$cta = Get-Content -LiteralPath $ctaPath -Raw
$cta = $cta.Replace('Ready to build?', 'The right PC. Without needing to become a PC expert.')
$cta = $cta.Replace('href="/start" variant="primary" autoAnimate>Build your machine', 'href="/find-my-pc" variant="primary" autoAnimate>Find my PC')
if (-not $cta.Contains('href="/upgrade-my-pc"')) {
    $cta = $cta.Replace('<SpecularButton href="/ready-to-ship" variant="secondary">Explore ready-to-ship PCs</SpecularButton>', '<SpecularButton href="/ready-to-ship" variant="secondary">Explore ready-to-ship PCs</SpecularButton>' + "`r`n        " + '<SpecularButton href="/upgrade-my-pc" variant="secondary">Upgrade my PC</SpecularButton>')
}
Set-Content -LiteralPath $ctaPath -Value $cta -NoNewline

$homePath = Join-Path $shop 'app\page.tsx'
$homePageText = Get-Content -LiteralPath $homePath -Raw
$homePageText = $homePageText.Replace('import StartupExperience from "@/components/home/StartupExperience";', 'import Hero from "@/components/home/Hero";')
$homePageText = $homePageText.Replace('<StartupExperience />', '<Hero />')
Set-Content -LiteralPath $homePath -Value $homePageText -NoNewline

$heroPath = Join-Path $shop 'components\home\Hero.tsx'
$heroText = Get-Content -LiteralPath $heroPath -Raw
$heroText = $heroText.Replace('Beautiful machines,', 'The right PC.')
$heroText = $heroText.Replace('built to be admired.', 'Without needing to become a PC expert.')
$heroText = $heroText.Replace("whiteSpace: 'nowrap'", "whiteSpace: 'normal'")
$heroMarker = '        {/* CTAs moved to FinalCTA at the bottom of the page — here we only'
if ($heroText.Contains($heroMarker) -and -not $heroText.Contains('href="/find-my-pc"')) {
    $heroText = $heroText.Replace($heroMarker, @'
        <p className="text-center text-slate-200" style={{ marginBottom: "1rem" }}>Tell us what you do and what matters. We will handle the component homework.</p>
        <div className="flex flex-wrap justify-center gap-3" style={{ marginBottom: "1rem" }}>
          <a href="/find-my-pc" className="rounded-full bg-orange-500 px-6 py-3 font-semibold text-black">Find my PC</a>
          <a href="/ready-to-ship" className="rounded-full border border-white/50 px-6 py-3 text-white">See what's ready now</a>
        </div>
        {/* CTAs moved to FinalCTA at the bottom of the page — here we only
'@)
}
Set-Content -LiteralPath $heroPath -Value $heroText -NoNewline
Write-Output 'Installed guided journey, API proxy, homepage CTA and immediate hero.'
