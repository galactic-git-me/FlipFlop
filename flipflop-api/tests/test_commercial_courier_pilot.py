"""Home collection and signature constraints; no external provider calls."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
import unittest
from app.services import parcel2go_courier as courier


def row(collection='Collection', signature=True):
    return {'Service':{'Slug':'test-service','Name':'Test','CourierName':'Test','CollectionType':collection},
        'TotalPrice':13.49,'TotalPriceExVat':11.24,
        'Extras':[{'Type':'Signature'}] if signature else [],
        'Collection':'2026-10-15T00:00:00','EstimatedDeliveryDate':'2026-10-16T00:00:00'}


class CourierPilotTests(unittest.IsolatedAsyncioTestCase):
    def test_collection_filter_rejects_dropoff_and_unknown_collection_type(self):
        result=courier._parse_tracked_quotes({'Quotes':[row(),row('Shop'),row(None)]},require_collection=True)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0].price_gbp,13.49)  # Gross cost for nonregistered business.

    def test_requesting_signature_does_not_prove_it_is_included(self):
        self.assertEqual(courier._parse_tracked_quotes({'Quotes':[row(signature=False)]},require_collection=True),[])

    async def test_route_and_signature_sent_without_adding_provider_insurance(self):
        client=MagicMock();client.post=AsyncMock(return_value=SimpleNamespace(status_code=200,json=lambda:{'Quotes':[row()]}))
        context=MagicMock();context.__aenter__=AsyncMock(return_value=client);context.__aexit__=AsyncMock(return_value=False)
        with patch.object(courier,'get_settings',return_value=SimpleNamespace(parcel2go_environment='sandbox')), patch.object(
            courier,'_get_access_token',AsyncMock(return_value='test-only')), patch.object(courier.httpx,'AsyncClient',return_value=context):
            result=await courier.get_tracked_quotes(25,57,30,55,1000,collection_postcode='AB1 2CD',
                delivery_postcode='XY1 2ZZ',require_collection=True)
        payload=client.post.call_args.kwargs['json']
        self.assertEqual(payload['CollectionAddress']['Postcode'],'AB1 2CD')
        self.assertEqual(payload['DeliveryAddress']['Postcode'],'XY1 2ZZ')
        self.assertEqual(payload['Parcels'][0]['Weight'],25)
        self.assertEqual(payload['Extras'],[{'Type':'Signature'}])
        self.assertTrue(result[0].signature_tracking)

    async def test_missing_route_rejected_before_authentication(self):
        with patch.object(courier,'get_settings',return_value=SimpleNamespace(parcel2go_environment='sandbox')), patch.object(
            courier,'_get_access_token',AsyncMock()) as token:
            with self.assertRaises(courier.Parcel2GoError):
                await courier.get_tracked_quotes(25,57,30,55,1000,require_collection=True)
            token.assert_not_awaited()
