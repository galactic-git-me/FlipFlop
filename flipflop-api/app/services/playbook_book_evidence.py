"""Join recorded channel presence to explicit cell identity, never to a guessed tier."""
from sqlalchemy import select, func
from app.models.product import Product, ProductListing
from app.models.build import Build
from app.models.manual_build import ManualBuild
from app.models.build_sold_observation import BuildSoldObservation


def resolve_cell_identity(product_identity, assignment, parent_id, definitions_by_id, parent_ids):
    assignment = assignment if isinstance(assignment, dict) else {}
    assigned = assignment.get('curated_build_id')
    if product_identity and assigned and product_identity != assigned:
        return None, 'Product and build assignments disagree'
    cell_id = product_identity or assigned
    definition = definitions_by_id.get(cell_id)
    if not definition:
        return None, 'No valid exact Playbook cell assignment'
    expected_parent = parent_ids.get(definition['segment'])
    if expected_parent is None or any(value is not None and value != expected_parent
        for value in (parent_id, assignment.get('playbook_id'))):
        return None, 'Playbook owner conflicts with the recorded cell'
    return cell_id, None


async def distribution_evidence(db, definitions, parents):
    by_id = {row['id']: row for row in definitions}
    parent_ids = {row.name: row.id for row in parents}
    # Select only public product metadata and the assignment leaf, never buyer data.
    rows = (await db.execute(select(Product.id, Product.title, Product.status, Product.product_type,
        Product.playbook_id, Product.item_specifics, Product.updated_at,
        Build.manual_build_id, ManualBuild.evidence_data['playbook_assignment'].label('assignment'))
        .outerjoin(Build, Build.id == Product.build_id)
        .outerjoin(ManualBuild, ManualBuild.id == Build.manual_build_id))).all()
    listings = (await db.execute(select(ProductListing))).scalars().all()
    records, unassigned = [], []
    for row in rows:
        details = row.item_specifics if isinstance(row.item_specifics, dict) else {}
        cell_id, reason = resolve_cell_identity(details.get('curated_build_id'), row.assignment,
            row.playbook_id, by_id, parent_ids)
        entries = [item for item in listings if item.product_id == row.id]
        common = {'cell_id': cell_id, 'product_id': row.id, 'title': row.title or f'Product {row.id}',
                  'manual_build_id': row.manual_build_id, 'offer_kind': 'ready_to_ship' if getattr(row.product_type,'value',row.product_type)=='prebuilt' else 'curated_template',
                  'assignment_reason': reason}
        # Direct storefront publishing uses Product.status without a ProductListing.
        if getattr(row.product_type,'value',row.product_type)=='prebuilt' and not any(getattr(item.channel, 'value', item.channel) == 'storefront' for item in entries):
            record = {**common, 'channel': 'storefront', 'status': getattr(row.status, 'value', row.status),
                'source': 'Stored direct storefront product record', 'external_id': str(row.id),
                'updated_at': row.updated_at}
            (records if cell_id else unassigned).append(record)
        for item in entries:
            record = {**common, 'channel': getattr(item.channel, 'value', item.channel),
                'status': getattr(item.status, 'value', item.status),
                'source': f'Product {row.id} channel record', 'external_id': item.external_listing_id,
                'updated_at': item.updated_at}
            (records if cell_id else unassigned).append(record)
    # eBay build listings can exist without a canonical ProductListing row.
    manual_rows = (await db.execute(select(ManualBuild.id, ManualBuild.name,
        ManualBuild.evidence_data['playbook_assignment'].label('assignment'),
        ManualBuild.ebay_listing_id, ManualBuild.ebay_listing_status,
        ManualBuild.ebay_listing_status_checked_at).where(ManualBuild.ebay_listing_id.is_not(None)))).all()
    for row in manual_rows:
        if any(record['channel'] == 'ebay' and record['external_id'] == row.ebay_listing_id
               for record in [*records, *unassigned]):
            continue
        cell_id, reason = resolve_cell_identity(None, row.assignment, None, by_id, parent_ids)
        record = {'cell_id': cell_id, 'product_id': None, 'manual_build_id': row.id,
            'title': row.name, 'offer_kind': 'ready_to_ship', 'assignment_reason': reason,
            'channel': 'ebay', 'status': row.ebay_listing_status,
            'source': 'Stored build eBay lifecycle record', 'external_id': row.ebay_listing_id,
            'updated_at': row.ebay_listing_status_checked_at}
        (records if cell_id else unassigned).append(record)
    return records, unassigned


async def build_market_evidence(db):
    """Expose reviewable build-level coverage without treating it as cell pricing."""
    rows = (await db.execute(select(ManualBuild.id, ManualBuild.name,
        func.count(BuildSoldObservation.id).label('observations'),
        func.max(BuildSoldObservation.observed_at).label('last_observed_at'))
        .join(BuildSoldObservation, BuildSoldObservation.build_id == ManualBuild.id)
        .group_by(ManualBuild.id, ManualBuild.name)
        .order_by(ManualBuild.id))).all()
    return [{'build_id': row.id, 'name': row.name, 'observations': row.observations,
             'last_observed_at': row.last_observed_at,
             'reason': 'Build-level sold comparisons need exact specification and condition review; they are not a cell market price'}
            for row in rows]
