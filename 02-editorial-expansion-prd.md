# FlipFlop Growth Engine — Editorial Expansion PRD

**Depends on:** Marketing MVP, Product Catalogue, Media Service  
**Release:** Editorial Expansion  
**Primary outcome:** Produce evidence-backed blog drafts and publish approved articles to the storefront

## 1. Purpose and scope

Add AI-assisted editorial production without allowing AI to publish unapproved public content.

### Included

- Topic and opportunity suggestions from market data, customer questions, analytics and inventory.
- Editorial briefs, source collection and article outlines.
- Draft article generation in UK English and FlipFlop tone.
- Internal links to products, builds, listings and configurator routes.
- Media briefs and approved/generative media workflow.
- Fact, brand, SEO, accessibility, claims and link validation.
- Storefront preview, approval, publication, rollback and update.
- Automatic creation of social draft tasks after publication.

### Excluded

- Newsletter sending.
- Paid campaigns.
- Automatic vouchers.
- Unreviewed AI publication.
- Unlicensed third-party imagery.

## 2. Content lifecycle

`idea → briefed → researching → drafting → fact_check → brand_review → approval → approved → scheduled → published → superseded/archived`.

Every article revision is immutable. A change to a public claim, price, product fact, image or CTA requires a new approval.

## 3. Topic discovery

Ideas may be generated from:

- Component and market-price movements.
- Search and website queries.
- Customer questions and support themes.
- Social engagement and recurring comments.
- New builds and available inventory.
- Seasonal buying moments.

Each idea stores relevance, evidence, freshness, audience, commercial relationship, risk, proposed CTA and confidence.

## 4. Article contract

Required fields:

- Title, subtitle, slug and summary.
- Body and section headings.
- Category, tags, author and publication dates.
- Meta description, canonical URL and social preview.
- Featured media, alt text, captions and licence/provenance.
- Source list and claim-level evidence.
- Internal links and related products.
- CTA and tracked links.
- Disclosure status for sponsored, affiliate or AI-assisted material.

## 5. CMS contract

The storefront owns the public presentation. The Editorial Service owns drafts and publication intent. The CMS integration must support preview URL, draft sync, confirmed revision ID, slug collision detection, canonical URL, sitemap/RSS updates, rollback, update, archive and deletion.

Publication confirmation is required before the article is marked live.

## 6. AI and media rules

AI may research, outline and draft using approved sources. It may not invent technical specifications, prices, benchmarks, stock or claims. Generated media records model, prompt, licence status and review state. Automatic resizing of an already-approved asset is low risk; newly generated or materially edited media requires review.

## 7. Acceptance criteria

- Topic suggestions show evidence and confidence.
- A user can approve a topic and create a sourced draft.
- Claims link to approved catalogue data or source evidence.
- Media has provenance, licence status and alt text.
- Preview, approval, publication and rollback work.
- Slug collisions are blocked.
- Article publication creates social draft tasks but does not auto-publish them.
- Broken links, stale prices and unavailable products are detected before approval.

## 8. Launch gate

Ten representative articles pass fact, provenance, accessibility, SEO, CMS publication and rollback tests with zero invented specifications or prices.

