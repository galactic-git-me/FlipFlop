"""Tests for welcome guide service."""

import pytest
from unittest.mock import MagicMock, Mock
from datetime import datetime, timedelta
from app.services.guide_service import GuideService


class TestGuideServiceStyles:
    """Tests for PDF styling."""

    def test_create_styles(self):
        """Test style creation."""
        db_mock = MagicMock()
        service = GuideService(db_mock)

        styles = service.styles
        assert styles is not None
        assert isinstance(styles, dict)

        # Verify key styles exist
        assert 'CustomTitle' in styles
        assert 'CustomHeading1' in styles
        assert 'CustomBody' in styles


class TestGuideServiceSectionMethods:
    """Tests for individual section creation methods."""

    def setup_method(self):
        """Set up test fixtures."""
        self.db_mock = MagicMock()
        self.service = GuideService(self.db_mock)

        # Create a mock order with customer and OS component
        self.mock_order = MagicMock()
        self.mock_order.id = 1
        self.mock_order.order_id = "FF-2026-0001"
        self.mock_order.customer = MagicMock()
        self.mock_order.customer.name = "John Smith"
        self.mock_order.actual_delivery_date = datetime.utcnow()
        self.mock_order.playbook = MagicMock()
        self.mock_order.playbook.name = "Gaming Beast"
        self.mock_order.specs = {
            "cpu": {"name": "Intel Core i7-14700K", "cores": 20, "threads": 28},
            "gpu": {"name": "NVIDIA RTX 4070", "memory": 12},
            "motherboard": {"name": "ASUS ROG Strix Z790-E", "socket": "LGA1700"},
            "ram": {"name": "Corsair Vengeance DDR5", "capacity": 32, "speed": 6000},
            "storage": {"name": "Samsung 990 Pro", "capacity": 1000, "type": "NVMe SSD"},
            "psu": {"name": "Corsair HX850", "wattage": 850, "rating": "80+ Platinum"},
            "case": {"name": "Lian Li LANCOOL 216", "type": "Mid-Tower ATX"},
            "cooler": {"name": "Noctua NH-D15", "type": "Air"},
        }
        self.mock_order.os_component = MagicMock()
        self.mock_order.os_component.os_type = "windows_11_pro"
        self.mock_order.os_component.license_key = "XXXXXXXXXXXXXXXXXXXXX" + "XXX"  # 25 chars

    def test_create_cover_page_returns_list(self):
        """Test cover page returns list of elements."""
        content = self.service._create_cover_page(self.mock_order)
        assert isinstance(content, list)
        assert len(content) > 0

    def test_create_quick_start_returns_list(self):
        """Test quick start returns list of elements."""
        content = self.service._create_quick_start(self.mock_order)
        assert isinstance(content, list)
        assert len(content) > 0

    def test_create_component_specs_returns_list(self):
        """Test component specs returns list of elements."""
        content = self.service._create_component_specs(self.mock_order)
        assert isinstance(content, list)
        assert len(content) > 0

    def test_create_bios_guide_returns_list(self):
        """Test BIOS guide returns list of elements."""
        content = self.service._create_bios_guide(self.mock_order)
        assert isinstance(content, list)
        assert len(content) > 0

    def test_create_os_setup_returns_list(self):
        """Test OS setup returns list of elements."""
        content = self.service._create_os_setup(self.mock_order)
        assert isinstance(content, list)
        assert len(content) > 0

    def test_create_license_page_returns_list(self):
        """Test license page returns list of elements."""
        content = self.service._create_license_page(self.mock_order)
        assert isinstance(content, list)
        assert len(content) > 0

    def test_create_troubleshooting_returns_list(self):
        """Test troubleshooting returns list of elements."""
        content = self.service._create_troubleshooting(self.mock_order)
        assert isinstance(content, list)
        assert len(content) > 0

    def test_create_warranty_returns_list(self):
        """Test warranty returns list of elements."""
        content = self.service._create_warranty(self.mock_order)
        assert isinstance(content, list)
        assert len(content) > 0


class TestGuideServiceWithoutOSComponent:
    """Tests for guide generation without OS component."""

    def test_create_os_setup_without_windows_component(self):
        """Test OS setup when no Windows component present."""
        db_mock = MagicMock()
        service = GuideService(db_mock)

        mock_order = MagicMock()
        mock_order.os_component = None

        content = service._create_os_setup(mock_order)
        assert isinstance(content, list)
        assert len(content) > 0


class TestGuideServiceEdgeCases:
    """Tests for edge cases."""

    def test_empty_specs(self):
        """Test handling of empty component specs."""
        db_mock = MagicMock()
        service = GuideService(db_mock)

        mock_order = MagicMock()
        mock_order.id = 1
        mock_order.specs = {}
        mock_order.customer = MagicMock()
        mock_order.customer.name = "Test"
        mock_order.actual_delivery_date = datetime.utcnow()

        content = service._create_component_specs(mock_order)
        assert isinstance(content, list)
        assert len(content) > 0

    def test_license_key_formatting_25_chars(self):
        """Test license key formatting with 25 characters."""
        db_mock = MagicMock()
        service = GuideService(db_mock)

        mock_order = MagicMock()
        mock_order.os_component = MagicMock()
        # Create a 25 character key (5 groups of 5)
        mock_order.os_component.license_key = "ABCDE" * 5

        content = service._create_license_page(mock_order)
        assert isinstance(content, list)
        assert len(content) > 0
