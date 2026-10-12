# FlipFlop Software Playbook

**Status:** Current reviewed baseline  
**Version:** 1.1  
**Last reviewed:** 2026-09-29  
**Source of implementation truth:** `flipflop-api/app/services/software_catalogue.py`  
**Audience:** Product/admin operators, customer support, and the FlipFlop support chatbot  
**Customer-safe:** Mixed; ingest only the explicitly marked customer section below. The support knowledge base remains the preferred customer answer source.

## Purpose

Offer a useful, optional set of applications prepared on the customer's PC before dispatch. The recommended set should reduce setup effort for the customer's stated use case. Customers can add or remove any approved application, including choosing none. The customer-approved selection is the only free-app install plan sent to the workshop script.

Application installation is included with the PC. Third-party application terms and any account or licence requirements still apply. FlipFlop does not create customer accounts, accept publisher terms for the customer, buy paid licences, or sign the customer into applications.

## Customer-safe: software recommendations and choice

**Customer-safe: yes**

FlipFlop includes an optional software setup service with a PC. The starting recommendations are based on the customer's Playbook use case, and some product flows can tailor them to the selected budget cell. Customers may add or remove available applications, including choosing none, before their software choices lock for the build. The current recommendations are:

| Use case | Typical starting recommendations |
|---|---|
| Great-value gaming | Steam, Discord, VLC media player, 7-Zip |
| High-performance gaming | Steam, Discord, OBS Studio, VLC media player, 7-Zip |
| Student hybrid | Firefox, Notepad++, VLC media player, 7-Zip |
| Business & office | Firefox, Notepad++, ShareX, 7-Zip |
| Content creation | GIMP, Blender, OBS Studio, VLC media player, 7-Zip |
| AI workstation | Visual Studio Code, Git, Python, Blender, 7-Zip |
| Software development | Visual Studio Code, Git, Python, 7-Zip |
| Family & home | Firefox, VLC media player, ShareX, 7-Zip |

These are optional starting points, not requirements. The software selection saved for the customer's own build is authoritative if it differs from this general list. The setup is included with the PC; third-party account, publisher and licence terms still apply. Some applications finish installing at the customer's first Windows sign-in, as described in that build's Getting Started guide. WinGet may ask the customer to review source or app licence terms at first sign-in. FlipFlop does not accept package terms for the customer; they should accept only agreements they have reviewed and agree to. FlipFlop's setup-time figure is an estimate, not a measured result or guarantee.

## Internal recommendation and installation policy

**Customer-safe: no**

## How recommendations resolve

1. Resolve the customer's Playbook use case and, when available, the exact budget cell.
2. Use an administrator-authored profile for that exact cell when one has been saved and validated against the software allow-list.
3. Otherwise use the reviewed use-case defaults below. These defaults are use-case based and do not currently vary by budget tier.
4. Show the recommended applications checked by default, along with the rationale and indicative time-saving estimate. Let the customer add or remove any available app before the selection locks.
5. Save the submitted package IDs on the order's Getting Ready job. A changed selection invalidates any draft manifest that used the prior selection.
6. Generate deterministic WinGet setup only from the final allow-listed customer selection. Machine-scope packages install in Audit Mode with an explicit machine scope and do not silently accept package EULAs. Packages that support only a user scope are copied to ProgramData and scheduled for that Windows profile's first sign-in; this customer-session installer leaves WinGet source and package agreement prompts visible for the customer to decide. Paid AI setup services are separate purchases and are never inserted into the free software installer.

Curated-for-you cells can have a cell-specific profile. Made-by-you resolves customer type × declared Budget, Mid-range, or High-end tier, then falls back to the use-case default when that exact profile is absent. Ready-to-Ship uses the cell assigned to the build and carries that profile through the sale. Legacy or unknown use cases receive the small general-purpose fallback below.

## Reviewed use-case recommendations

Minutes are the sum of the current catalogue's per-application estimates. They are indicative estimates for avoiding individual search/download and installer steps; they are not measured results or a guarantee of time saved.

| Playbook use case | Recommended applications | Estimated minutes saved | Rationale |
|---|---|---:|---|
| Great-value gaming | Steam, Discord, VLC media player, 7-Zip | 17 | Game library client, optional gaming communication, common media playback, and archive handling. Accounts remain optional and customer-controlled. |
| High-performance gaming | Steam, Discord, OBS Studio, VLC media player, 7-Zip | 23 | Gaming starter set plus optional recording/streaming tools. |
| Student hybrid | Firefox, Notepad++, VLC media player, 7-Zip | 17 | Research, plain-text notes or code snippets, media playback, and archive handling without assuming a paid productivity licence or school account. |
| Business & office | Firefox, Notepad++, ShareX, 7-Zip | 18 | Browser, plain-text notes, screenshots, and archive handling without assuming a paid office suite or work account. |
| Content creation | GIMP, Blender, OBS Studio, VLC media player, 7-Zip | 28 | Free creative tools for image editing, 3D, recording/streaming, media review, and archives. |
| AI workstation | Visual Studio Code, Git, Python 3.12, Blender, 7-Zip | 32 | Code editing, source control, Python workflows, 3D tasks, and archives. These apps do not install a local model or connect to cloud AI. |
| Software development | Visual Studio Code, Git, Python 3.12, 7-Zip | 24 | Code editing, source control, Python projects, and archives. Does not install project dependencies or connect to a code-hosting account. |
| Family & home | Firefox, VLC media player, ShareX, 7-Zip | 17 | General browsing, media, screenshots, and downloaded archives without adding communication or gaming accounts by default. |
| General-purpose fallback | 7-Zip, Firefox, VLC media player | 12 | Small baseline for archive handling, web browsing, and media playback. |

## Approved application catalogue

Only these package identifiers may be selected by customer or admin profiles and emitted into the WinGet installer. Minutes below are the current estimates used by the savings calculation. Package scope is explicit in the executable catalogue: workshop selections request machine scope and Discord requests customer-profile scope. The Microsoft community manifests reviewed on 2026-09-29 show user and machine variants for several entries; the installer must still choose machine explicitly because WinGet otherwise prefers current-user scope when available. Scope mismatches and installer errors fail the setup report rather than silently installing into the temporary workshop profile. Recheck manifests before changing package IDs or revising this allow-list. See Microsoft's [WinGet install scope option](https://learn.microsoft.com/en-us/windows/package-manager/winget/install), [scope preference behavior](https://learn.microsoft.com/en-us/windows/package-manager/winget/settings), and the [community manifest scope field](https://github.com/microsoft/winget-pkgs/blob/master/doc/manifest/schema/1.12.0/installer.md).

| Application | WinGet package ID | Category | Minutes |
|---|---|---|---:|
| 7-Zip | `7zip.7zip` | Utilities | 4 |
| Google Chrome | `Google.Chrome` | Browser | 4 |
| Mozilla Firefox | `Mozilla.Firefox` | Browser | 4 |
| VLC media player | `VideoLAN.VLC` | Media | 4 |
| ShareX | `ShareX.ShareX` | Capture | 5 |
| Notepad++ | `Notepad++.Notepad++` | Utilities | 5 |
| Git | `Git.Git` | Developer | 6 |
| Visual Studio Code | `Microsoft.VisualStudioCode` | Developer | 7 |
| Python 3.12 | `Python.Python.3.12` | Developer | 7 |
| GIMP | `GIMP.GIMP` | Creative | 6 |
| Blender | `BlenderFoundation.Blender` | Creative / 3D | 8 |
| OBS Studio | `OBSProject.OBSStudio` | Streaming / capture | 6 |
| Discord | `Discord.Discord` | Communication | 4 |
| Steam | `Valve.Steam` | Gaming | 5 |

The catalogue and WinGet manifests can change. Review package availability, publisher identity, licensing notes, installation scope, and unattended-install behavior before expanding or changing this allow-list. Do not add paid apps or apps that require accepting a customer-specific agreement without a separately reviewed customer approval flow.

## Customer and workshop safeguards

- The customer selection is separate from paid AI setup offers. A paid offer is shown only when configured and hardware eligibility is met; the service records the confirmed purchase and produces a reviewed operator runbook, not an automatic AI installer.
- A selection is not evidence that an app installed successfully. Workshop setup records machine-scope installation status and blocks dispatch on required failures. User-scope apps are clearly listed in the Getting Started guide, need an internet connection at first Windows sign-in, and retry at the next sign-in if installation fails. The customer can contact support through the build portal if it continues to fail.
- WinGet package execution requires the workshop operator to run the elevated master script and type `RUN`. It uses the allow-listed package IDs saved for that build.
- The master script does not create accounts, enter passwords, run paid AI setup, partition disks, flash firmware, or apply unreviewed RGB profiles.
- Do not tell customers they will save an exact number of minutes. Present the total as FlipFlop's estimate and recalculate it from the apps they actually select.
- Keep Playbook rationale in plain English. Explain why an app is suggested, and avoid implying an app is essential to the PC or the customer's use case.

## Updating this Playbook

Change the executable allow-list and use-case defaults in `flipflop-api/app/services/software_catalogue.py`. Cell-specific recommendation profiles are managed in the applicable admin catalogue/Playbook workflow. Update this document in the same change whenever package identifiers, default lists, rationale, estimated minutes, or customer-visible licensing notes change. Record package provenance and review date in the implementation change before making a new app selectable.
