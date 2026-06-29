"""
Tests for admin dashboard API endpoints.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import get_db
from app.models.order import Order, OrderStatus
from app.models.order_checklist import OrderChecklist
from app.models.customer import Customer


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sample_customer(db: Session):
    """Create a sample customer for testing."""
    customer = Customer(
        email="test@example.com",
        password_hash="hashed_password",
        name="Test Customer",
        address="123 Test St",
        phone="555-0123"
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@pytest.fixture
def sample_order(db: Session, sample_customer: Customer):
    """Create a sample order for testing."""
    order = Order(
        order_id="ORD-001",
        customer_id=sample_customer.id,
        specs={
            "cpu": "Intel i7-10700K",
            "gpu": "RTX 3080",
            "ram": "32GB DDR4"
        },
        customer_price=1500.0,
        component_costs=800.0,
        overhead_amount=100.0,
        profit=600.0,
        promised_delivery_date=datetime.utcnow() + timedelta(days=14),
        status=OrderStatus.AWAITING_SOURCING,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


class TestAdminOrderList:
    """Tests for listing orders."""

    def test_list_orders_empty(self, client: TestClient):
        """Test listing orders when none exist."""
        response = client.get("/api/admin/orders")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["orders"] == []

    def test_list_orders_with_pagination(self, client: TestClient, db: Session, sample_customer: Customer):
        """Test listing orders with pagination."""
        # Create multiple orders
        for i in range(60):
            order = Order(
                order_id=f"ORD-{i:03d}",
                customer_id=sample_customer.id,
                specs={"cpu": "i7"},
                customer_price=1000.0 + i * 10,
                component_costs=500.0,
                overhead_amount=100.0,
                promised_delivery_date=datetime.utcnow() + timedelta(days=14)
            )
            db.add(order)
        db.commit()

        # Test first page
        response = client.get("/api/admin/orders?skip=0&limit=50")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 60
        assert len(data["orders"]) == 50

        # Test second page
        response = client.get("/api/admin/orders?skip=50&limit=50")
        assert response.status_code == 200
        data = response.json()
        assert len(data["orders"]) == 10

    def test_list_orders_filter_by_status(self, client: TestClient, db: Session, sample_order: Order):
        """Test filtering orders by status."""
        # Create another order with different status
        customer = sample_order.customer
        building_order = Order(
            order_id="ORD-002",
            customer_id=customer.id,
            specs={"cpu": "i7"},
            customer_price=1200.0,
            component_costs=600.0,
            overhead_amount=100.0,
            status=OrderStatus.BUILDING,
            promised_delivery_date=datetime.utcnow() + timedelta(days=14)
        )
        db.add(building_order)
        db.commit()

        # Filter by sourcing status
        response = client.get("/api/admin/orders?status=awaiting_sourcing")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["orders"][0]["order_id"] == "ORD-001"

        # Filter by building status
        response = client.get("/api/admin/orders?status=building")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["orders"][0]["order_id"] == "ORD-002"


class TestAdminOrderDetail:
    """Tests for getting order details."""

    def test_get_order_detail(self, client: TestClient, sample_order: Order):
        """Test retrieving order details."""
        response = client.get(f"/api/admin/orders/{sample_order.id}")
        assert response.status_code == 200
        data = response.json()

        assert data["order"]["id"] == sample_order.id
        assert data["order"]["order_id"] == "ORD-001"
        assert data["order"]["customer_name"] == "Test Customer"
        assert "checklist" in data
        assert "build" in data["checklist"]
        assert "qa" in data["checklist"]
        assert "photos" in data

    def test_get_order_detail_not_found(self, client: TestClient):
        """Test retrieving non-existent order."""
        response = client.get("/api/admin/orders/999")
        assert response.status_code == 404


class TestAdminOrderStatus:
    """Tests for updating order status."""

    def test_update_order_status(self, client: TestClient, sample_order: Order):
        """Test updating order status."""
        response = client.patch(
            f"/api/admin/orders/{sample_order.id}",
            json={"status": "parts_ordered"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["new_status"] == "parts_ordered"

    def test_update_order_status_invalid(self, client: TestClient, sample_order: Order):
        """Test updating order with invalid status."""
        response = client.patch(
            f"/api/admin/orders/{sample_order.id}",
            json={"status": "invalid_status"}
        )
        assert response.status_code == 400

    def test_update_order_status_sets_timestamps(self, client: TestClient, db: Session, sample_order: Order):
        """Test that status update sets proper timestamps."""
        # Move to parts_ordered
        response = client.patch(
            f"/api/admin/orders/{sample_order.id}",
            json={"status": "parts_ordered"}
        )
        assert response.status_code == 200

        # Refresh order from DB
        db.refresh(sample_order)
        assert sample_order.status == OrderStatus.PARTS_ORDERED
        assert sample_order.sourcing_started_at is not None
        assert sample_order.sourcing_approved_at is not None
        assert sample_order.building_started_at is not None


class TestAdminChecklist:
    """Tests for checklist operations."""

    def test_create_checklist_item(self, client: TestClient, db: Session, sample_order: Order):
        """Test creating a checklist item."""
        response = client.post(
            f"/api/admin/orders/{sample_order.id}/checklist/build",
            json={
                "item": "CPU installed",
                "completed": True,
                "notes": "Installation complete"
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["item"] == "CPU installed"
        assert data["completed"] is True

        # Verify in DB
        checklist = db.query(OrderChecklist).filter(
            OrderChecklist.order_id == sample_order.id,
            OrderChecklist.section == "build",
            OrderChecklist.item == "CPU installed"
        ).first()
        assert checklist is not None
        assert checklist.completed is True
        assert checklist.notes == "Installation complete"

    def test_update_checklist_item(self, client: TestClient, db: Session, sample_order: Order):
        """Test updating an existing checklist item."""
        # Create initial item
        client.post(
            f"/api/admin/orders/{sample_order.id}/checklist/build",
            json={"item": "CPU installed", "completed": False}
        )

        # Update it
        response = client.post(
            f"/api/admin/orders/{sample_order.id}/checklist/build",
            json={"item": "CPU installed", "completed": True, "notes": "Updated"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["completed"] is True

    def test_invalid_checklist_section(self, client: TestClient, sample_order: Order):
        """Test with invalid checklist section."""
        response = client.post(
            f"/api/admin/orders/{sample_order.id}/checklist/invalid",
            json={"item": "Test", "completed": False}
        )
        assert response.status_code == 400


class TestAdminShipping:
    """Tests for shipping operations."""

    def test_update_shipping(self, client: TestClient, db: Session, sample_order: Order):
        """Test updating shipping information."""
        estimated = (datetime.utcnow() + timedelta(days=3)).isoformat()

        response = client.patch(
            f"/api/admin/orders/{sample_order.id}/shipping",
            json={
                "tracking_number": "TRK123456",
                "carrier": "royal_mail",
                "estimated_delivery": estimated
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tracking_number"] == "TRK123456"
        assert data["carrier"] == "royal_mail"

        # Verify in DB
        db.refresh(sample_order)
        assert sample_order.tracking_number == "TRK123456"
        assert sample_order.carrier == "royal_mail"


class TestAdminMetrics:
    """Tests for metrics endpoint."""

    def test_metrics_empty_database(self, client: TestClient):
        """Test metrics with no orders."""
        response = client.get("/api/admin/metrics")
        assert response.status_code == 200
        data = response.json()

        assert data["total_active"] == 0
        assert data["average_build_time_days"] == 0.0
        assert data["late_orders"] == 0
        assert data["customer_satisfaction_avg"] is None

    def test_metrics_with_orders(self, client: TestClient, db: Session, sample_customer: Customer):
        """Test metrics with various orders."""
        # Create orders in different statuses
        statuses = [
            OrderStatus.AWAITING_SOURCING,
            OrderStatus.BUILDING,
            OrderStatus.QA,
            OrderStatus.COMPLETED
        ]

        for i, status in enumerate(statuses):
            order = Order(
                order_id=f"ORD-{i:03d}",
                customer_id=sample_customer.id,
                specs={"cpu": "i7"},
                customer_price=1000.0,
                component_costs=500.0,
                overhead_amount=100.0,
                status=status,
                promised_delivery_date=datetime.utcnow() + timedelta(days=14),
                rating=5 if status == OrderStatus.COMPLETED else None
            )
            if status == OrderStatus.COMPLETED:
                order.delivered_at = datetime.utcnow()
            db.add(order)
        db.commit()

        response = client.get("/api/admin/metrics")
        assert response.status_code == 200
        data = response.json()

        assert data["total_active"] == 3  # AWAITING, BUILDING, QA
        assert data["orders_by_status"]["awaiting_sourcing"] == 1
        assert data["orders_by_status"]["building"] == 1
        assert data["orders_by_status"]["qa"] == 1
        assert data["orders_by_status"]["completed"] == 1

    def test_metrics_late_orders(self, client: TestClient, db: Session, sample_customer: Customer):
        """Test metrics for late orders."""
        # Create order older than 14 days
        old_date = datetime.utcnow() - timedelta(days=20)
        order = Order(
            order_id="ORD-LATE",
            customer_id=sample_customer.id,
            specs={"cpu": "i7"},
            customer_price=1000.0,
            component_costs=500.0,
            overhead_amount=100.0,
            status=OrderStatus.BUILDING,
            promised_delivery_date=datetime.utcnow() + timedelta(days=14),
            created_at=old_date
        )
        db.add(order)
        db.commit()

        response = client.get("/api/admin/metrics")
        assert response.status_code == 200
        data = response.json()

        assert data["late_orders"] == 1
