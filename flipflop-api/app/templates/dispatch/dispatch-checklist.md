# Dispatch checklist — {{build_name}}

Complete and record each item in Dispatch Centre. Add a meaningful operator note to every completed or not-required action. This file is a workshop aid and does not mark database actions complete.

## Build and package

- [ ] Source data reconciled: exact specification and serial checked against the physical build, and sale/order details match the linked order
- [ ] Manufacturer manuals checked for every distinct exact component model; exact cached/reviewed PDFs included, and unavailable or unverified manuals have an operator note
- [ ] Customer software selection is submitted and its selected package IDs match the latest order record; made-to-order choices lock after components are ordered, while Ready-to-Ship choices can change until dispatch, so regenerate and re-review the package if that selection changes
- [ ] Content manifest generated from the approved specification, measured benchmarks, customer choices and reviewed evidence
- [ ] Customer-document and workshop USB artifacts generated for this build
- [ ] Content manifest, plaque, specification, benchmark report, guide, manuals, upgrade path and installer reports reviewed; unsupported claims or mismatched build details corrected
- [ ] Customer-document package explicitly approved after review
- [ ] Workshop USB package downloaded from Dispatch Centre; file list and SHA-256 checksums verified before copying to the branded USB
- [ ] For a direct guest or indirect-channel buyer, issue the final order/build-scoped portal claim before booking; if it is reissued, replace the leaflet and record the current grant
- [ ] Windows 11 Pro en-GB deployed with `Deploy-Windows11-Pro.ps1` from official English International media only after the Dispatch Centre target model/serial is matched, re-entered, and both typed erase confirmations are completed; run `collect-windows-deployment-evidence.ps1`, import its build-bound report, and confirm the system-drive model/serial matches the pre-install target (never record the product key)
- [ ] After verifying the workshop USB ZIP, if a Windows Pro activation helper is required, download it privately from Dispatch Centre and place it beside the master script before setup; allow the script's separate `APPLY-LICENSE` confirmation, then verify activation and that the helper was removed (never record or copy the key)
- [ ] Selected machine-scope applications installed and first-run warnings reviewed; selected user-scope applications are scheduled in the customer Windows profile and disclosed in the Getting Started guide
- [ ] Drivers, firmware and BIOS recommendations reviewed against official manufacturer evidence
- [ ] Record a structured review outcome for every distinct exact component model in Dispatch Centre; cite its approved manufacturer source for any installed update, or explain why no update applies, before marking driver setup complete
- [ ] Paid AI services completed only within the purchased and approved scope
- [ ] FlipFlop Rainmeter build theme applied and portal link opened successfully
- [ ] RGB profile applied only if a reviewed profile exists for the exact motherboard/controller; otherwise record as not configured
- [ ] Final QA and benchmark recheck passed
- [ ] Approved customer documents published to the correct private build portal
- [ ] Print the leaflet for the current claim, scan-test it on a second device, and pack it; do not reissue the claim after printing unless the replacement leaflet is also printed and tested before courier booking

## Delivery evidence and booking

- [ ] Delivery name/address and declared sale value verified
- [ ] Dimensions and weight measured
- [ ] Eligible courier quoted with Parcel2Go's Signature extra included; immediately before payment, explicitly confirm the exact service and current total; confirm the unpaid created-order total matches before paying, then save the tracking number before shipment evidence is uploaded
- [ ] Working-build photo or video captured
- [ ] Package-contents still photo captured before sealing
- [ ] Sealed-parcel still photo captured
- [ ] Each evidence item downloaded/inspected and explicitly approved or rejected in Dispatch Centre with a meaningful review note; rejected items replaced and reviewed again
- [ ] New, resistant double packaging used inside a rigid outer container; contents cannot be deduced by touch
- [ ] Package does not disclose item nature/value or display business/website branding; courier label does not disclose item nature/value
- [ ] Adult/direct-signature courier service selected
- [ ] Carrier collection or official carrier depot/branch handover arranged; no parcel shop or locker without written insurer approval
- [ ] Insurance eligibility, current terms, packaging and admin-approved evidence reviewed; computer screens have written insurer approval if applicable
- [ ] Obtain a fresh insurance quote; explicitly confirm the current premium and approve the live policy purchase only if the production account/use gate is enabled
- [ ] Confirm the registered policy ID and premium are saved before handover
- [ ] Recheck that policy, signed-for service, approved evidence and checklist gates are all complete
- [ ] Hand parcel to the carrier and explicitly confirm physical handover in Dispatch Centre
- [ ] Dispatch notification checked

## Safety boundary

This checklist does not authorise disk erasure, Windows deployment, BIOS flashing, licence activation, account creation, external publishing, courier purchase or insurance purchase. Each external purchase and physical handover requires its separate reviewed operator confirmation; insurance remains unavailable while production eligibility is gated.
