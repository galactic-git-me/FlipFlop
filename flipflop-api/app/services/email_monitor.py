"""Email monitor — reconciles purchases via receipt email parsing and detects external sales."""
import imaplib
import email
from email.header import decode_header
from datetime import datetime
from typing import Optional
import re
import secrets
from email.utils import parseaddr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import get_settings
from app.models.inventory import InventoryItem
from app.models.build import Build
from app.models.product import Product
from app.models.email_event import EmailEvent
from app.models.manual_build import ManualBuild
from app.models.channel_listing import ChannelListing
from app.models.customer_review import CustomerReview
from app.models.customer import Customer
from app.services.alerts import emit_alert
from app.services.auth_service import hash_password
from app.services.email_service import send_email_async
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

        # Keep a durable operator-readable copy of every marketplace email.
        # This makes the notification link useful even when the provider has
        # no webmail deep-link format we can safely infer from IMAP.
        existing = (await db.execute(select(EmailEvent).where(EmailEvent.message_id == str(msg["msg_id"])))) .scalar_one_or_none()
        if existing:
            return
        marketplace = self._marketplace_for_email(msg["subject"], msg.get("sender", ""), body)
        event = EmailEvent(
            message_id=str(msg["msg_id"]), subject=msg["subject"], sender=msg.get("sender", ""),
            body=body[:200000], marketplace=marketplace,
            summary=self._email_summary(msg["subject"], body),
        )
        db.add(event)
        await db.flush()
        await emit_alert(
            code="listing_email_received",
            source=marketplace or "email_monitor",
            severity="info",
            message=f"Listing update: {event.summary}",
            link_url=f"/email-events/{event.id}",
        )

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
            for detector in [self.detect_ebay_sale, self.detect_vinted_sale, self.detect_generic_marketplace_sale]:
                sale = detector(body)
                if sale:
                    sender_name, sender_email = parseaddr(msg.get("sender", ""))
                    buyer_match = re.search(r"(?:buyer|customer|ship to|deliver to).*?([\w.+-]+@[\w.-]+\.[A-Za-z]{2,})", body, re.I | re.S)
                    sale["customer_name"] = sender_name or "FlipFlop customer"
                    sale["customer_email"] = buyer_match.group(1).lower() if buyer_match else None
                    await self.process_sale_detection(sale, db)
                    build = await self._match_manual_build_sale(sale, db)
                    if build:
                        event.event_type = "sold"
                        event.manual_build_id = build.id
                        event.marketplace = sale.get("marketplace") or event.marketplace
                        event.summary = f"Sold on {sale.get('marketplace', 'marketplace')}: {build.name} for £{sale.get('price', 0):.2f}. Other channel listings were withdrawn locally."
                    break

        # Delivery confirmations are deliberately handled after sale parsing;
        # this is idempotent and becomes Day 1 of the warranty clock.
        if self._is_delivery_confirmation(msg["subject"], body):
            event.event_type = "delivered"
            # Match by a known tracking number when possible. The operator can
            # still review unmatched confirmations from the email event page.
            builds = (await db.execute(select(ManualBuild).where(ManualBuild.tracking_number.is_not(None)))).scalars().all()
            matched = next((b for b in builds if b.tracking_number and b.tracking_number.lower() in body.lower()), None)
            if matched:
                matched.delivered_at = datetime.utcnow()
                matched.warranty_started_at = matched.delivered_at
                matched.dispatch_status = "delivered"
                event.manual_build_id = matched.id
                event.summary = f"Delivered: {matched.name}. Warranty Day 1 starts {matched.warranty_started_at.date().isoformat()}."
            else:
                event.summary = "Delivery confirmation received; no tracking number matched a build."

        review = self.detect_customer_review(msg["subject"], msg.get("sender", ""), body)
        if review and review["rating"] >= 4:
            customer_email = parseaddr(msg.get("sender", ""))[1].lower() or None
            existing = None
            if customer_email:
                existing = (await db.execute(select(CustomerReview).where(CustomerReview.customer_email == customer_email, CustomerReview.review_text == review["text"]))).scalars().first()
            if not existing:
                customer = None
                if customer_email:
                    customer = (await db.execute(select(Customer).where(Customer.email == customer_email))).scalars().first()
                db.add(CustomerReview(
                    manual_build_id=event.manual_build_id,
                    customer_id=customer.id if customer else None,
                    author_name=parseaddr(msg.get("sender", ""))[0] or "Verified customer",
                    customer_email=customer_email,
                    rating=review["rating"], review_text=review["text"],
                    source=review["source"], source_url=review.get("source_url"),
                    approved=True, is_public=True,
                ))
                event.summary = f"Positive {review['rating']}/5 customer review captured and published."
                await emit_alert(code="customer_review_published", source=review["source"], severity="info", message=event.summary, link_url="/reviews")

        await db.commit()

    @staticmethod
    def detect_customer_review(subject: str, sender: str, body: str) -> Optional[dict]:
        text = f"{subject} {sender} {body}".lower()
        if not any(term in text for term in ("review", "feedback", "rating", "stars")):
            return None
        rating_match = re.search(r"([1-5](?:\.\d)?)\s*(?:/\s*5|out of 5|stars?)", text, re.I)
        if not rating_match:
            words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5}
            word_match = re.search(r"\b(one|two|three|four|five)\s+stars?\b", text, re.I)
            if not word_match:
                return None
            rating = float(words[word_match.group(1).lower()])
        else:
            rating = float(rating_match.group(1))
        quote_match = re.search(r"(?:review|feedback|comment)\s*[:\-]\s*(.{20,2000})", body, re.I | re.S)
        quote = (quote_match.group(1) if quote_match else body).strip()
        quote = re.sub(r"\s+", " ", quote)[:2000]
        url_match = re.search(r"https?://[^\s<>]+", body)
        return {"rating": rating, "text": quote, "source": EmailMonitor._marketplace_for_email(subject, sender, body) or "email", "source_url": url_match.group(0) if url_match else None}

    async def _match_manual_build_sale(self, sale: dict, db: AsyncSession) -> ManualBuild | None:
        title = (sale.get("title") or "").strip()
        if not title:
            return None
        result = await db.execute(select(ManualBuild).where(ManualBuild.status != "sold"))
        candidates = result.scalars().all()
        build = next((b for b in candidates if title.lower() in (b.generated_title or b.name or "").lower() or (b.generated_title or b.name or "").lower() in title.lower()), None)
        if not build:
            return None
        build.status = "sold"
        build.dispatch_status = "awaiting_dispatch"
        build.sale_price_actual = sale.get("price") or build.ebay_price
        build.updated_at = datetime.utcnow()
        if sale.get("customer_email"):
            customer = (await db.execute(select(Customer).where(Customer.email == sale["customer_email"]))).scalars().first()
            temporary_password = None
            if not customer:
                temporary_password = secrets.token_urlsafe(12)
                customer = Customer(email=sale["customer_email"], name=sale.get("customer_name") or "FlipFlop customer", password_hash=hash_password(temporary_password))
                db.add(customer)
                await db.flush()
            build.customer_id = customer.id
            build.customer_email = customer.email
            build.buyer_name = build.buyer_name or customer.name
            if temporary_password:
                await send_email_async(customer.email, "Your FlipFlop customer account", f"<p>Hello {customer.name},</p><p>We created your secure FlipFlop customer account for Build {build.id}.</p><p>Email: <strong>{customer.email}</strong><br>Temporary password: <strong>{temporary_password}</strong></p><p>Please sign in and change this password at <a href=\"https://theflipflop.shop/my-builds/{build.id}\">your My Builds page</a>.</p>", f"customer-account-build-{build.id}")
        # Mark every local cross-listing withdrawn immediately. Provider API
        # withdrawal is channel-specific and is retried/handled by its adapter.
        listings = (await db.execute(select(ChannelListing).where(ChannelListing.manual_build_id == build.id, ChannelListing.status.in_(["published", "scheduled"])))) .scalars().all()
        for listing in listings:
            listing.status = "withdrawn"
            listing.withdrawn_at = datetime.utcnow()
        if sale.get("marketplace") != "ebay" and build.ebay_sku:
            from app.config import get_settings
            from app.services.cross_channel_guard import withdraw_ebay_for_sold_build
            await withdraw_ebay_for_sold_build(build, get_settings().ebay_listing_environment)
        return build

    @staticmethod
    def _marketplace_for_email(subject: str, sender: str, body: str) -> str | None:
        text = f"{subject} {sender} {body[:4000]}".lower()
        for key, names in {"ebay": ("ebay",), "vinted": ("vinted",), "facebook": ("facebook", "marketplace"), "flipflop_shop": ("flipflop", "theflipflop.shop")}.items():
            if any(name in text for name in names):
                return key
        return None

    @staticmethod
    def _email_summary(subject: str, body: str) -> str:
        clean = re.sub(r"\s+", " ", body).strip()
        return (subject.strip() + " — " + clean[:240]).strip(" —")

    @staticmethod
    def _is_delivery_confirmation(subject: str, body: str) -> bool:
        text = f"{subject} {body}".lower()
        return any(term in text for term in ("delivered", "delivery confirmed", "has been delivered", "parcel delivered"))

    def detect_generic_marketplace_sale(self, body: str) -> Optional[dict]:
        """Conservative fallback for Facebook/other channel sale emails."""
        lower = body.lower()
        marketplace = self._marketplace_for_email("", "", body)
        if not marketplace or marketplace in {"ebay", "vinted", "flipflop_shop"}:
            return None
        if not any(term in lower for term in ("you've sold", "you have sold", "item sold", "sold your")):
            return None
        title_match = re.search(r"(?:item|listing|product)\s*[:\-]\s*(.+?)(?:\n|£|$)", body, re.I)
        price_match = re.search(r"£\s*([\d,]+(?:\.\d{1,2})?)", body)
        return {"marketplace": marketplace, "title": (title_match.group(1).strip() if title_match else ""), "price": float(price_match.group(1).replace(",", "")) if price_match else 0.0}

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
