# Finding the real costs for a FlipFlop build

**Prepared:** 13 October 2026. Examples illustrate the calculation; they are not approved operating costs.

The Playbook needs these inputs to distinguish money received from money left after fulfilling a build. Start with one representative PC and one normal UK delivery. Record each input's value, source/date, and whether it is a quote, measured cost or provisional estimate. Unknown is not zero.

| Input | Meaning | How to find it |
|---|---|---|
| VAT treatment | Whether FlipFlop must charge VAT, and which scheme applies. VAT collected is not profit. | Check the business's VAT registration certificate/HMRC business tax account and confirm the scheme with the accountant. Being a sole trader does not decide VAT registration. Do not select 20% simply because suppliers charge it. |
| Payment fees | The processor's charge for collecting the customer's payment, usually a percentage plus a fixed amount. | Check the merchant agreement/pricing in Stripe and an actual payment's fee breakdown. Record differences for premium/international cards and any other payment methods offered. |
| Labour | A pricing allowance for the human time spent sourcing/admin, assembly, installation, checks and packing. | Time a representative build, distinguish active work from unattended tests, and multiply active hours by a chosen hourly rate. Include somebody else's paid work at its actual cost; owner time also needs an explicit pricing allowance. |
| Packaging | The materials consumed in shipping one complete PC safely. | Add the unit costs of the outer box, inner protection, any second box, cushioning, tape and labels from a supplier quote or invoice. Divide a bulk purchase by the number of usable packs. Do not count materials twice between labour, packaging and courier. |
| Courier | The price paid to transport the packed PC, separate from how long we need to source/build it. | Weigh and measure the fully packed example. Get the suitable service quote using collection/delivery postcodes and required service features. Check whether the quote includes VAT, collection, signature or other surcharges. Use region-specific rules where needed. |
| Insurance | The premium paid for shipment cover on this PC's declared value and service. | Obtain a quote from the selected insurer using the shipment value and confirm the particular item/service/packing is covered. Separate cover already included elsewhere so it is not charged twice. |
| Workshop capacity | How much work can actually be completed with the available people and equipment, after committed work. | Estimate weekly hands-on hours, assembly time per PC, test-bench/QA throughput and packing/dispatch capacity; the slowest stage is the limit. For example, 12 available labour hours at 3 hours per PC suggests at most four before other bottlenecks, existing orders and a safety allowance. |

## Examples and current source checks

- Stripe's published standard UK-card rate is 1.5% + 20p, making the illustrated fee on £1,000 £15.20. Your account/card mix can differ. Use the actual merchant terms, not this example as a universal rate. [Stripe UK pricing](https://stripe.com/gb/pricing).
- HMRC's current UK VAT registration threshold is taxable turnover over £90,000 in the previous 12 months, with a separate next-30-days test. Voluntary registration is possible below the threshold. Confirm actual registration and scheme rather than infer them from anticipated sales. [HMRC registration rules](https://www.gov.uk/register-for-vat).
- The UK standard VAT rate is 20%. Under ordinary standard-rate treatment, £1,200 including VAT contains £200 VAT and £1,000 net revenue. Different schemes need separate modelling; the current solver must not be used to simulate margin-scheme/flat-rate accounting by simply changing its percentage. [HMRC VAT rates](https://www.gov.uk/how-vat-works/how-much-vat-you-must-charge).
- Obtain a packed-PC shipping quote using weight, dimensions and route. The cheapest displayed headline price is not a PC delivery quote. [Parcel2Go quote instructions](https://www.parcel2go.com/help-centre/parcels/question/pricing/how-do-i-send-a-parcel).
- Secursus provides a calculator for the premium at the shipment's value. Record the returned quote and applicable conditions; do not assume the premium from a generic percentage. [Secursus pricing](https://www.secursus.com/en-gb/pricing/).

## A simple first worksheet

1. Confirm VAT registration/scheme and the payment methods being offered.
2. Choose one representative PC, estimate active labour hours and decide the hourly pricing allowance.
3. Obtain one complete packaging quote, weigh/measure the packed parcel, then obtain suitable courier and insurance quotes.
4. List workshop hours available next week, existing committed work and QA/packing limits.
5. Enter these as sourced estimates in the draft. Review a shadow quote, then replace estimates with measured invoices, processing fees and build/delivery outcomes as sales occur.

The approved profit floors and 5% warranty/2% provisional returns reserves are separate from these inputs. Reserve allowances cover expected future costs; they are not the courier's shipment-insurance premium. Overhead, software licences, supplier postage/fees and expected failure costs also need explicit treatment; never make an incomplete worksheet sellable by filling unknowns with zero.
