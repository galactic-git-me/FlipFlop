"""Standalone business disclosure validation, using temporary files only."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from pydantic import ValidationError
from app.services.business_details import BusinessDetails, read_business_details, save_business_details


class BusinessDetailsContract(unittest.TestCase):
    def test_nonlocal_settings_requests_require_admin_authentication(self):
        import asyncio
        from types import SimpleNamespace
        from unittest.mock import AsyncMock
        from fastapi import HTTPException
        from app.routes.admin_auth import get_current_admin
        db=AsyncMock()
        with self.assertRaises(HTTPException) as error:
            asyncio.run(get_current_admin(SimpleNamespace(client=SimpleNamespace(host='198.51.100.1')),authorization=None,db=db))
        self.assertEqual(error.exception.status_code,401)
        db.execute.assert_not_called()

    def test_defaults_do_not_invent_a_proprietor_or_weee_membership(self):
        with TemporaryDirectory() as folder, patch('app.services.business_details.BUSINESS_DETAILS_PATH', Path(folder)/'business.json'):
            result=read_business_details()
            self.assertEqual(result.legalName,'')
            self.assertEqual(result.weeeTakebackRoute,'unconfirmed')

    def test_settings_round_trip_without_database_changes(self):
        with TemporaryDirectory() as folder, patch('app.services.business_details.BUSINESS_DETAILS_PATH', Path(folder)/'business.json'):
            details=BusinessDetails(legalName='Test Proprietor',tradingName='Test Shop',address='Public business address',phone='01234567890')
            self.assertEqual(save_business_details(details),details)
            self.assertEqual(read_business_details(),details)
            self.assertEqual(len(list(Path(folder).iterdir())),1)

    def test_invalid_email_route_and_unexpected_private_fields_are_rejected(self):
        for invalid in ({'email':'not-an-email'},{'weeeTakebackRoute':'invented'},{'openrouter_api_key':'must-not-be-published'}):
            with self.assertRaises(ValidationError): BusinessDetails(**invalid)


if __name__=='__main__': unittest.main()
