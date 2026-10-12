# Windows 11 Pro offer review

**Reviewed:** 29 September 2026  
**Status:** Research for product decision; not a price approval

## Findings

- Microsoft's UK Store lists a full Windows 11 Pro download licence at **£219.99**. This is a retail licence reference, not evidence of FlipFlop's eligible OEM/system-builder cost. [Microsoft Store: Windows 11 Pro](https://www.microsoft.com/en-gb/d/windows-11-pro/dg7gmgf0d8h4)
- Microsoft says the supported Home-to-Pro path is through Microsoft Store on an activated Home installation. That is a different offer from supplying a new Pro licence with a PC. [Microsoft Support: Upgrade Windows Home to Windows Pro](https://support.microsoft.com/en-us/windows/deployment/install-upgrade/upgrade-windows-home-to-windows-pro)
- Public UK custom-builder pages vary: H&C currently presents Windows 11 Pro installation/activation as included at £0, while GeekAPC lists Windows 11 Pro as included in at least one configurator path. Neither page exposes a separately comparable Pro licence line price, so these are package-positioning examples, not a market price benchmark. [H&C custom builder](https://hc-computech.co.uk/build-your-pc/), [GeekAPC configurator](https://geekapc.com/apps/configurator?system=GPC-AVALANCHE)

## Recommendation

Do not price the FlipFlop Pro add-on at the full £219.99 retail reference by default. First obtain written confirmation from the authorised distributor/system-builder source for the licence channel, per-unit cost, transfer/repair terms and proof-of-purchase requirements. Then price the add-on from the actual landed licence cost plus an explicit activation/setup amount, and disclose the edition, licence type and total before payment. Never use grey-market keys or silently activate a customer-supplied key.

The product decision is still needed on the base edition:

1. Windows 11 Home is included and Pro is an optional upgrade; or
2. Windows 11 Pro is installed on every build and the licence is priced/handled separately.

The current master workshop script validates Windows 11 Pro on every build. Therefore a paid optional Pro upgrade cannot safely go live until the base edition, licence entitlement and no-key path are made consistent across checkout, package generation and workshop setup. Until then, show no Pro purchase control and do not charge for it.

## Implementation guardrails

- Only an admin-approved catalogue entry with a verified GBP price and current licence source may be shown at checkout.
- The server calculates the extra amount and snapshots the selected licence product and price into the verified payment/order record.
- The Getting Ready job receives the add-on only from confirmed order data; the LLM never receives the licence key.
- Licence key storage and application remain separate from the LLM package generator, with key material excluded from logs, ZIPs, email and customer-visible JSON.
- Keep activation behind an explicit workshop confirmation and verify the installed edition/activation result before dispatch.
