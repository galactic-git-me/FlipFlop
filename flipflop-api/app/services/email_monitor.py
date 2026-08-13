"""Email monitor — reconciles purchases via receipt email parsing and detects external sales."""
import imaplib
import email
from email.header import decode_header
from datetime import datetime
from typing import Optional
import re
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models.inventory import InventoryItem
from app.models.build import Build
from app.models.product import Product
import logging

log = logging.getLogger(__name__)


class EmailMonitor:
    """Monitor incoming emails for purchase receipts and sales notifications."""

    def __init__(self):
        self.settings = get_settings()
        self.imap_host = self.settings.imap_host
        self.imap_user = self.settings.imap_user
        self.imap_pass = self.settings.imap_pass
        self.imap_folder = self.settings.imap_folder

    def connect(self) -> Optional[imaplib.IMAP4_SSL]:
        """Connect to IMAP server."""
        if not self.imap_host or not self.imap_user or not self.imap_pass:
            log.warning("Email monitor not configured (missing IMAP credentials)")
            return None

        try:
            imap = imaplib.IMAP4_SSL(self.imap_host)
            imap.login(self.imap_user, self.imap_pass)
            return imap
        except Exception as e:
            log.error(f"Failed to connect to IMAP: {e}")
            return None

    def decode_header_value(self, header_value: str) -> str:
        """Decode email header value (handles RFC 2047 encoding)."""
        if not header_value:
            return ""
        try:
            decoded_parts = decode_header(header_value)
            result = ""
            for part, charset in decoded_parts:
                if isinstance(part, bytes):
                    result += part.decode(charset or "utf-8", errors="ignore")
                else:
                    result += str(part)
            return result
        except Exception:
            return header_value

    def get_email_body(self, message: email.message.Message) -> str:
        """Extract plain text body from email message."""
        body = ""
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_type() == "text/plain":
                    try:
                        body += part.get_payload(decode=True).decode(part.get_charset() or "utf-8", errors="ignore")
                    except Exception:
                        pass
                elif part.get_content_type() == "text/html":
                    try:
                        body += part.get_payload(decode=True).decode(part.get_charset() or "utf-8", errors="ignore")
                    except Exception:
                        pass
        else:
            try:
                body = message.get_payload(decode=True).decode(message.get_charset() or "utf-8", errors="ignore")
            except Exception:
                body = message.get_payload()
        return body

    def parse_ebay_receipt(self, body: str) -> Optional[dict]:
        """Parse eBay purchase receipt email."""
        # Look for eBay purchase patterns
        if "ebay" not in body.lower():
            return None

        # Match order total: look for "Total: £X.XX" or similar
        total_match = re.search(r"Total[:\s]+[£$€]?([\d,]+\.?\d{0,2})", body, re.IGNORECASE)
        if not total_match:
            return None

        total_price = float(total_match.group(1).replace(",", ""))

        # Extract item details (simplified)
        item_matches = re.findall(
            r"(?:Item|Product):\s*([^\n]+?)(?:\n|$)",
            body,
            re.IGNORECASE,
        )

        if not item_matches:
            return None

        return {
            "marketplace": "ebay",
            "total_price": total_price,
            "items": item_matches,
        }

    def parse_vinted_receipt(self, body: str) -> Optional[dict]:
        """Parse Vinted sale receipt email."""
        if "vinted" not in body.lower():
            return None

        # Look for Vinted sale patterns
        if "you've sold" not in body.lower() and "sold item" not in body.lower():
            return None

        # Extract price (Vinted uses € or £)
        price_match = re.search(r"[£€$]?([\d,]+\.?\d{0,2})", body)
        if not price_match:
            return None

        price = float(price_match.group(1).replace(",", ""))

        # Extract item name
        item_match = re.search(r"(?:Item|Product):\s*([^\n]+?)(?:\n|$)", body, re.IGNORECASE)
        item_name = item_match.group(1) if item_match else "Unknown"

        return {
            "marketplace": "vinted",
            "total_price": price,
            "items": [item_name],
        }

    def parse_amazon_receipt(self, body: str) -> Optional[dict]:
        """Parse Amazon purchase receipt email."""
        if "amazon" not in body.lower():
            return None

        # Look for order confirmation patterns
        if "order confirmation" not in body.lower() and "order placed" not in body.lower():
            return None

        # Extract order total
        total_match = re.search(r"Order Total[:\s]+[£$€]?([\d,]+\.?\d{0,2})", body, re.IGNORECASE)
        if not total_match:
            return None

        total_price = float(total_match.group(1).replace(",", ""))

        # Extract items
        item_matches = re.findall(r"(?:Item|Product):\s*([^\n]+?)(?:\n|$)", body, re.IGNORECASE)

        if not item_matches:
            return None

        return {
            "marketplace": "amazon",
            "total_price": total_price,
            "items": item_matches,
        }

    def parse_temu_receipt(self, body: str) -> Optional[dict]:
        """Parse Temu purchase receipt."""
        if "temu" not in body.lower():
            return None

        # Extract total
        total_match = re.search(r"Total[:\s]+[£$€]?([\d,]+\.?\d{0,2})", body, re.IGNORECASE)
        if not total_match:
            return None

        total_price = float(total_match.group(1).replace(",", ""))

        # Extract items
        item_matches = re.findall(r"(?:Item|Product):\s*([^\n]+?)(?:\n|$)", body, re.IGNORECASE)

        return {
            "marketplace": "temu",
            "total_price": total_price,
            "items": item_matches or ["Unknown"],
        }

    def parse_overclockers_receipt(self, body: str) -> Optional[dict]:
        """Parse Overclockers.co.uk purchase receipt."""
        if "overclockers" not in body.lower():
            return None

        # Extract order total
        total_match = re.search(r"Order Total[:\s]+£([\d,]+\.?\d{0,2})", body, re.IGNORECASE)
        if not total_match:
            return None

        total_price = float(total_match.group(1).replace(",", ""))

        # Extract items
        item_matches = re.findall(r"(?:Item|Product):\s*([^\n]+?)(?:\n|$)", body, re.IGNORECASE)

        if not item_matches:
            return None

        return {
            "marketplace": "overclockers",
            "total_price": total_price,
            "items": item_matches,
        }

    def parse_storefront_receipt(self, body: str) -> Optional[dict]:
        """Parse FlipFlop storefront order confirmation."""
        if "flipflop" not in body.lower() or "order" not in body.lower():
            return None

        # Extract order ID and total
        total_match = re.search(r"Order Total[:\s]+£([\d,]+\.?\d{0,2})", body, re.IGNORECASE)
        if not total_match:
            return None

        total_price = float(total_match.group(1).replace(",", ""))

        # Extract items
        item_matches = re.findall(r"(?:Item|Product):\s*([^\n]+?)(?:\n|$)", body, re.IGNORECASE)

        return {
            "marketplace": "flipflop",
            "total_price": total_price,
            "items": item_matches or ["Custom Build"],
        }

    def detect_ebay_sale(self, body: str) -> Optional[dict]:
        """Detect eBay sale notification."""
        if "ebay" not in body.lower():
            return None

        if "you've sold" not in body.lower() and "item sold" not in body.lower():
            return None

        # Extract item title
        title_match = re.search(r"(?:Item|Title):\s*([^\n]+?)(?:\n|$)", body, re.IGNORECASE)
        title = title_match.group(1) if title_match else "Unknown"

        # Extract price
        price_match = re.search(r"(?:Price|Amount):\s*[£$€]?([\d,]+\.?\d{0,2})", body, re.IGNORECASE)
        price = float(price_match.group(1).replace(",", "")) if price_match else 0.0

        # Extract the eBay listing/item number — either spelled out ("Item
        # number: 123456789012") or embedded in an itm/ link — so the sale
        # can be matched to a Flip by ebay_listing_id, not just fuzzy title.
        listing_id_match = re.search(r"Item\s*number:?\s*(\d{9,15})", body, re.IGNORECASE)
        if not listing_id_match:
            listing_id_match = re.search(r"/itm/(?:[^/\s]+/)?(\d{9,15})", body, re.IGNORECASE)
        listing_id = listing_id_match.group(1) if listing_id_match else None

        return {
            "marketplace": "ebay",
            "title": title,
            "price": price,
            "ebay_listing_id": listing_id,
        }

    def detect_vinted_sale(self, body: str) -> Optional[dict]:
        """Detect Vinted sale notification."""
        if "vinted" not in body.lower():
            return None

        if "you've sold" not in body.lower():
            return None

        # Extract item and price
        title_match = re.search(r"(?:Item|Title):\s*([^\n]+?)(?:\n|$)", body, re.IGNORECASE)
        title = title_match.group(1) if title_match else "Unknown"

        price_match = re.search(r"[£€$]?([\d,]+\.?\d{0,2})", body)
        price = float(price_match.group(1).replace(",", "")) if price_match else 0.0

        return {
            "marketplace": "vinted",
            "title": title,
            "price": price,
        }

    async def fetch_unread_messages(self, imap: imaplib.IMAP4_SSL):
        """Fetch unread messages from IMAP server."""
        try:
            imap.select(self.imap_folder)
            status, messages = imap.search(None, "UNSEEN")
            if status != "OK":
                log.warning("Failed to fetch unread messages")
                return []

            message_ids = messages[0].split()
            results = []
            for msg_id in message_ids:
                status, msg_data = imap.fetch(msg_id, "(RFC822)")
                if status == "OK":
                    msg = email.message_from_bytes(msg_data[0][1])
                    subject = self.decode_header_value(msg.get("Subject", ""))
                    sender = self.decode_header_value(msg.get("From", ""))
                    body = self.get_email_body(msg)

                    results.append({
                        "msg_id": msg_id,
                        "subject": subject,
                        "sender": sender,
                        "body": body,
                    })

            return results
        except Exception as e:
            log.error(f"Error fetching messages: {e}")
            return []

    async def process_message(self, msg: dict, db: AsyncSession):
        """Process a single email message."""
        log.info(f"Processing email: {msg['subject']}")

        body = msg["body"]

        # Try to parse as purchase receipt
        receipt = None
        for parser in [
            self.parse_ebay_receipt,
            self.parse_vinted_receipt,
            self.parse_amazon_receipt,
            self.parse_temu_receipt,
            self.parse_overclockers_receipt,
            self.parse_storefront_receipt,
        ]:
            receipt = parser(body)
            if receipt:
                await self.process_purchase_receipt(receipt, db)
                break

        # If not a receipt, try sale detection
        if not receipt:
            sale = None
            for detector in [self.detect_ebay_sale, self.detect_vinted_sale]:
                sale = detector(body)
                if sale:
                    await self.process_sale_detection(sale, db)
                    break

    async def process_purchase_receipt(self, receipt: dict, db: AsyncSession):
        """Process a purchase receipt and create/update inventory items."""
        log.info(f"Processing {receipt['marketplace']} purchase receipt: £{receipt['total_price']}")

        marketplace = receipt["marketplace"]
        base_price = receipt["total_price"] / len(receipt["items"]) if receipt["items"] else receipt["total_price"]

        for item_name in receipt["items"]:
            # Check if item already exists (dedup on marketplace + item name)
            result = await db.execute(
                select(InventoryItem).where(
                    (InventoryItem.marketplace == marketplace) & (InventoryItem.component_name == item_name)
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing item with confirmed status
                existing.reconciliation_status = "CONFIRMED"
                existing.purchase_date = datetime.utcnow()
                existing.updated_at = datetime.utcnow()
                log.info(f"Updated existing inventory item: {item_name}")
            else:
                # Create new inventory item
                new_item = InventoryItem(
                    component_name=item_name,
                    component_type="unknown",  # Will be updated by admin or AI classification
                    quantity=1,
                    base_price=base_price,
                    shipping_cost=0.0,
                    discount_amount=0.0,
                    purchase_date=datetime.utcnow(),
                    source=marketplace,
                    marketplace=marketplace,
                    purchase_status="EMAIL_CONFIRMED",
                    reconciliation_status="CONFIRMED",
                )
                db.add(new_item)
                log.info(f"Created new inventory item: {item_name}")

        await db.commit()

    async def process_sale_detection(self, sale: dict, db: AsyncSession):
        """Process external sale detection (eBay, Vinted) and update build/product status."""
        log.info(f"Processing {sale['marketplace']} sale: {sale['title']} @ £{sale['price']}")

        marketplace = sale["marketplace"]
        title = sale["title"]
        price = sale["price"]

        # Fast path: an eBay sold email that carries the item number can be
        # matched straight to a Flip and marked sold immediately, instead of
        # waiting for the next ebay_sales_tracker poll cycle.
        ebay_listing_id = sale.get("ebay_listing_id")
        if marketplace == "ebay" and ebay_listing_id and price > 0:
            from app.services.flip_sale_processor import find_flip_by_ebay_listing_id, process_flip_sale

            flip = await find_flip_by_ebay_listing_id(db, ebay_listing_id)
            if flip:
                updated = await process_flip_sale(
                    db,
                    flip,
                    sale_price=price,
                    sale_platform="ebay",
                    source="ebay_sold_email",
                )
                if updated:
                    await db.commit()
                return

        # Try to find matching Product by title and price (with tolerance for fees)
        price_tolerance = price * 0.1  # 10% tolerance
        result = await db.execute(
            select(Product).where(
                (Product.hero_title == title) |
                (Product.hero_title.ilike(f"%{title[:20]}%"))
            )
        )
        matching_products = result.scalars().all()

        for product in matching_products:
            # Check if price is within tolerance
            if product.suggested_price and abs(product.suggested_price - price) < price_tolerance:
                product.status = "SOLD"
                product.sold_via_channel = marketplace
                product.updated_at = datetime.utcnow()
                log.info(f"Marked product {product.id} as SOLD via {marketplace}")

                # If it's a Made-to-Order build, set needs_attention
                if product.build and product.build.build_type.value == "made_to_order":
                    product.build.needs_attention = True
                    log.info(f"Set Build {product.build.id} needs_attention=True")

                await db.commit()
                break

    async def run(self, db: AsyncSession):
        """Main email monitor loop — fetch and process unread emails."""
        if not self.settings.email_monitor_enabled:
            log.debug("Email monitor is disabled")
            return

        imap = self.connect()
        if not imap:
            return

        try:
            messages = await self.fetch_unread_messages(imap)
            log.info(f"Fetched {len(messages)} unread messages")

            for msg in messages:
                try:
                    await self.process_message(msg, db)
                except Exception as e:
                    log.error(f"Error processing message {msg['subject']}: {e}")

            log.info("Email monitor run completed")
        finally:
            imap.close()
            imap.logout()
