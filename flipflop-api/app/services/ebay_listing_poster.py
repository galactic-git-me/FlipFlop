"""
eBay Listing Poster — Create and post new listings to eBay via Inventory API.

Uses the official Inventory API workflow:
  1. Create inventory item (sku-based)
  2. Create offer (links item to marketplace)
  3. Publish offer (activates listing and returns listing_id)

Authentication:
  Uses OAuth 2.0 token from eBay API (Application Token with sell.inventory scope).

Requires:
  - EBAY_APP_ID, EBAY_CLIENT_SECRET in environment
  - Valid OAuth tokens in database or session
"""

import asyncio
import httpx
import structlog
from typing import Optional
from datetime import datetime
import uuid
import base64
import csv
import io
import re
import gzip
from urllib.parse import urlparse
from html import unescape
from html.parser import HTMLParser
from bs4 import BeautifulSoup

log = structlog.get_logger(__name__)

EBAY_API_BASE = {
    "sandbox": "https://api.sandbox.ebay.com",
    "production": "https://api.ebay.com",
}

EBAY_PRODUCT_DESCRIPTION_MAX_LENGTH = 4000
EBAY_LISTING_DESCRIPTION_MAX_LENGTH = 500_000
EBAY_MAX_IMAGE_URLS = 24


def _feed_task_id(response: httpx.Response) -> str | None:
    """Extract a Sell Feed task ID from JSON or eBay's Location header.

    eBay's create-task response is allowed to have an empty body; the
    documented task URL is returned in ``Location`` instead.
    """
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict) and payload.get("taskId"):
        return str(payload["taskId"])

    location = response.headers.get("location", "")
    match = re.search(r"/task/([^/?#]+)", location)
    return match.group(1) if match else None


def _feed_task_status(payload: object) -> str:
    """Read the task status across the Sell Feed response variants."""
    if not isinstance(payload, dict):
        return "UNKNOWN"
    return str(payload.get("status") or payload.get("taskStatus") or "UNKNOWN").upper()


def _feed_result_text(response: httpx.Response) -> str:
    """Turn eBay's result-file response into a short actionable error."""
    body = response.content
    if response.headers.get("content-encoding", "").lower() == "gzip" or body[:2] == b"\x1f\x8b":
        try:
            body = gzip.decompress(body)
        except OSError:
            pass
    text = body.decode("utf-8", errors="replace").strip()
    return text[:1200] or "eBay returned an empty result file"


def _normalise_ebay_image_urls(image_urls: list[str]) -> list[str]:
    """Return the public HTTPS image URLs accepted by eBay's Inventory API.

    Build photos can contain duplicate entries after reordering/re-uploading,
    and old records can contain relative or non-HTTP URLs. eBay sometimes
    reports those cases as a generic Core Inventory Service 500, so reject
    them locally with an actionable message instead.
    """
    normalised: list[str] = []
    invalid: list[str] = []
    for raw_url in image_urls or []:
        url = str(raw_url or "").strip()
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc:
            if url:
                invalid.append(url)
            continue
        if url not in normalised:
            normalised.append(url)

    if invalid:
        raise ValueError(
            "eBay listing photos must use public HTTPS URLs. "
            f"Invalid photo URL: {invalid[0]}"
        )
    if len(normalised) > EBAY_MAX_IMAGE_URLS:
        log.warning(
            "ebay.image_urls_truncated",
            supplied=len(normalised),
            retained=EBAY_MAX_IMAGE_URLS,
        )
        normalised = normalised[:EBAY_MAX_IMAGE_URLS]
    if not normalised:
        raise ValueError("At least one public HTTPS image URL is required for an eBay listing")
    return normalised


class _DescriptionTextExtractor(HTMLParser):
    """Extract readable product text without sending template markup."""

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())


def _inventory_product_description(description: str, title: str) -> str:
    """Build the short Product.description required by Inventory API.

    The complete HTML belongs in Offer.listingDescription. Keeping markup out
    of this field makes its documented 4,000-character limit deterministic.
    """
    parser = _DescriptionTextExtractor()
    parser.feed(description or "")
    plain_text = unescape(" ".join(parser.parts))
    normalized = " ".join(plain_text.split())
    value = normalized or title.strip() or "Custom PC"
    # eBay documents characters, but its validation can occur after UTF-8
    # serialization. Truncate on a valid code-point boundary so both counts
    # remain within the same 4,000-unit ceiling for £, dashes, and emoji.
    encoded = value.encode("utf-8")[:EBAY_PRODUCT_DESCRIPTION_MAX_LENGTH]
    return encoded.decode("utf-8", errors="ignore")


def prepare_ebay_listing_description(description: str) -> str:
    """Make FlipFlop listing HTML reliable in eBay's constrained renderer."""
    if not description or "ff-page" not in description:
        return description

    soup = BeautifulSoup(description, "html.parser")

    def add_style(node, declarations: str) -> None:
        existing = (node.get("style") or "").strip().rstrip(";")
        node["style"] = f"{existing};{declarations}" if existing else declarations

    for image in soup.find_all("img"):
        src = (image.get("src") or "").strip()
        if not src or "{{" in src or "}}" in src:
            image.decompose()
            continue
        add_style(image, "display:block;max-width:100%;height:auto;border:0")

    for node in soup.select(".ff-page, .ff-wrap"):
        add_style(
            node,
            "width:100%;max-width:1000px;margin:0 auto;background:#0d1015;"
            "color:#f5f7fa;overflow:hidden;font-family:Arial,Helvetica,sans-serif;"
            "line-height:1.55",
        )

    for node in soup.select(".ff-section, .ff-image-section, .ff-card-row"):
        add_style(node, "background:#0d1015;color:#f5f7fa;max-width:100%;overflow:hidden")

    for node in soup.select(".ff-card"):
        add_style(
            node,
            "display:inline-block;width:42%;min-height:220px;margin:12px 2%;"
            "padding:34px 20px;vertical-align:top;text-align:center;background:#171c24;"
            "color:#f5f7fa;border:1px solid #2a3442;border-top:4px solid #ff6700;"
            "border-radius:14px;overflow-wrap:anywhere",
        )

    for node in soup.select(".ff-hero"):
        add_style(node, "padding:52px 34px;text-align:center;background:#0d1015")

    for node in soup.select(".ff-hero-logo"):
        add_style(node, "margin:0 auto 28px")

    for node in soup.select(".ff-hero-copy"):
        add_style(node, "max-width:780px;margin-left:auto;margin-right:auto;text-align:center")

    for node in soup.select(".ff-card-row, .ff-promise-grid, .ff-performance"):
        add_style(node, "text-align:center")

    for node in soup.select(".ff-card-icon"):
        add_style(node, "font-size:44px;line-height:1;margin-bottom:16px")

    for node in soup.select(".ff-benefit"):
        add_style(
            node,
            "display:inline-block;width:29%;min-height:235px;margin:10px 1.5%;"
            "padding:28px 18px;vertical-align:top;text-align:center;background:#171c24;"
            "border:1px solid #2a3442;border-radius:12px;font-size:15px",
        )

    for node in soup.select(".ff-benefit-icon"):
        add_style(node, "font-size:38px;line-height:1;margin-bottom:18px")

    for node in soup.select(".ff-standout"):
        add_style(node, "margin:18px 0;padding:26px;background:#171c24;border:1px solid #2a3442;border-radius:12px")

    for node in soup.select(".ff-standout-icon"):
        add_style(node, "display:inline-block;min-width:58px;margin-bottom:14px;padding:10px 12px;background:#102a43;color:#42a5ff;border:1px solid #1d78bd;border-radius:10px;font-size:17px;font-weight:bold;text-align:center")

    for node in soup.select(".ff-performance"):
        add_style(node, "max-width:820px;margin:34px auto 0;font-size:0")

    for node in soup.select(".ff-performance-card"):
        add_style(node, "display:inline-block;width:44%;min-height:130px;margin:8px 2%;padding:22px 16px;vertical-align:top;background:#171c24;border:1px solid #2a3442;border-radius:12px;font-size:14px;text-align:center")

    for node in soup.select(".ff-performance-value"):
        add_style(node, "display:block;color:#fff;font-size:28px;font-weight:bold")

    for node in soup.select(".ff-performance-source"):
        add_style(node, "display:block;margin-top:8px;color:#9fb0c3;font-size:12px")

    for node in soup.select(".ff-case-layout"):
        add_style(node, "width:100%;border-collapse:separate;border-spacing:0")

    for node in soup.select(".ff-case-layout td"):
        add_style(node, "width:50%;padding:30px;vertical-align:middle;color:#d8e2ee")

    for node in soup.select(".ff-spec-icon"):
        add_style(node, "display:inline-block;width:44px;margin-right:12px;padding:7px 3px;background:#102a43;color:#42a5ff;border:1px solid #1d78bd;border-radius:7px;font-size:11px;font-weight:bold;text-align:center")

    for node in soup.select(".ff-about"):
        add_style(node, "padding:48px 8%;text-align:center;background:#171c24;border-top:3px solid #ff6700;border-bottom:3px solid #008cff")

    for node in soup.select(".ff-heading"):
        add_style(node, "width:100%;max-width:100%;height:auto;object-fit:contain")

    for node in soup.select(".ff-page p, .ff-page li, .ff-page td, .ff-page strong"):
        style = (node.get("style") or "").lower()
        if "color:" not in style:
            add_style(node, "color:#d8e2ee")
        add_style(node, "overflow-wrap:anywhere;word-break:normal")

    for node in soup.select(".ff-benefit div"):
        add_style(node, "color:#cbd5e1")

    for node in soup.select(".ff-spec-table, .ff-use-grid"):
        add_style(node, "width:100%;max-width:100%;color:#f5f7fa")

    return str(soup)


class EbayListingPoster:
    """Posts listings to eBay via Inventory API (official workflow)."""

    def __init__(
        self,
        environment: str = "production",
        access_token: Optional[str] = None,
        app_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        self.environment = environment
        self.access_token = access_token
        self.app_id = app_id
        self.client_secret = client_secret
        self.base_url = EBAY_API_BASE[environment]
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-EBAY-API-SITEID": "EBAY_GB",
        }

    async def get_application_token(self) -> str:
        """Get an Application Token using client credentials (server-to-server auth)."""
        if not self.app_id or not self.client_secret:
            raise ValueError("App ID and Client Secret required for Application Token")

        # Base64 encode credentials for Basic Auth
        credentials = f"{self.app_id}:{self.client_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()

        async with httpx.AsyncClient(timeout=30.0) as client:
            token_resp = await client.post(
                f"{self.base_url}/identity/v1/oauth2/token",
                headers={
                    "Authorization": f"Basic {encoded}",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"grant_type": "client_credentials"},
            )

            if token_resp.status_code != 200:
                try:
                    error_json = token_resp.json()
                    error_msg = error_json.get("error_description", token_resp.text)
                except:
                    error_msg = token_resp.text

                log.error(
                    "ebay.token_generation_failed",
                    status=token_resp.status_code,
                    error=error_msg,
                    app_id=self.app_id,
                )
                raise ValueError(f"Failed to get Application Token: {error_msg}")

            token_data = token_resp.json()
            return token_data.get("access_token")

    async def create_item_draft(
        self,
        title: str,
        description: str,
        price: float,
        image_urls: list[str],
        category_id: str = "179",
        condition: str = "USED_EXCELLENT",
        aspects: Optional[dict[str, list[str]]] = None,
    ) -> dict:
        """Create an eBay-native draft for the seller's eBay listing UX."""
        try:
            image_urls = _normalise_ebay_image_urls(image_urls)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        if not self.access_token:
            return {"success": False, "error": "eBay user OAuth token required"}

        product_aspects = [
            {"name": name, "values": [str(value) for value in values]}
            for name, values in (aspects or {}).items()
            if values
        ]
        payload = {
            "categoryId": str(category_id),
            "condition": condition,
            "format": "FIXED_PRICE",
            "pricingSummary": {"price": {"currency": "GBP", "value": f"{price:.2f}"}},
            "product": {
                "title": title[:80],
                "description": description,
                "imageUrls": image_urls,
                "aspects": product_aspects,
            },
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Content-Language": "en-GB",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/sell/listing/v1_beta/item_draft",
                    json=payload,
                    headers=headers,
                )
            if response.status_code not in (200, 201):
                return {
                    "success": False,
                    "error": f"eBay Seller Hub draft creation failed ({response.status_code}): {response.text[:500]}",
                }
            data = response.json()
            return {
                "success": True,
                "draft_id": data.get("itemDraftId"),
                "draft_url": data.get("sellFlowUrl") or data.get("sellFlowNativeUri"),
                "status": "DRAFT",
            }
        except Exception as exc:
            log.exception("ebay.item_draft_creation_failed")
            return {"success": False, "error": f"eBay Seller Hub draft request failed: {exc}"}

    async def create_seller_hub_draft(
        self,
        title: str,
        category_id: str = "179",
        sku: Optional[str] = None,
    ) -> dict:
        """Upload the minimal Seller Hub Reports draft template via Sell Feed.

        This is the documented path that creates a row in Seller Hub >
        Listings > Drafts. The feed is asynchronous; eBay may take several
        minutes to process it.
        """
        if not self.access_token:
            return {"success": False, "error": "eBay user OAuth token required"}

        # Seller Hub's upload parser is sensitive to the template's line ending
        # format. Generate the same Windows CSV shape as eBay's downloaded
        # templates, including the final CRLF.
        csv_buffer = io.StringIO(newline="")
        writer = csv.writer(csv_buffer, lineterminator="\r\n")
        writer.writerow(["Action", "Custom label (SKU)", "Category ID", "Title"])
        writer.writerow(["Draft", sku or f"FLP-{uuid.uuid4().hex[:12].upper()}", str(category_id), title[:80]])
        feed_headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                task_response = await client.post(
                    f"{self.base_url}/sell/feed/v1/task",
                    # eBay's current production mapper accepts the Draft
                    # action under the dedicated FX_DRAFT task type. Using
                    # FX_LISTING creates the task but later fails with
                    # BAF.Error.5: "Unable to find Task Action Id for task
                    # Draft" before any Seller Hub row is created.
                    json={"feedType": "FX_DRAFT", "schemaVersion": "1.0"},
                    headers=feed_headers,
                )
                if task_response.status_code not in (200, 201, 202):
                    return {"success": False, "error": f"eBay Seller Hub feed task failed ({task_response.status_code}): {task_response.text[:500]}"}
                task_id = _feed_task_id(task_response)
                if not task_id:
                    return {
                        "success": False,
                        "error": (
                            "eBay did not return a Seller Hub feed task ID "
                            f"(Location: {task_response.headers.get('location', 'missing')})"
                        ),
                    }

                upload_response = await client.post(
                    f"{self.base_url}/sell/feed/v1/task/{task_id}/upload_file",
                    files={"file": ("flipflop-seller-hub-draft.csv", csv_buffer.getvalue(), "text/csv")},
                    headers={
                        "Authorization": f"Bearer {self.access_token}",
                        "Accept": "application/json",
                        "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
                    },
                )
                if upload_response.status_code not in (200, 201, 202):
                    return {"success": False, "error": f"eBay Seller Hub draft upload failed ({upload_response.status_code}): {upload_response.text[:500]}"}

                # Uploading a feed only queues it.  Do not report a draft as
                # created until eBay has processed the task; otherwise a
                # rejected CSV looks successful while Seller Hub stays empty.
                task_headers = {
                    "Authorization": f"Bearer {self.access_token}",
                    "Accept": "application/json",
                    "X-EBAY-C-MARKETPLACE-ID": "EBAY_GB",
                }
                terminal_status = None
                task_payload: object = None
                for delay in (0.5, 1.0, 2.0, 3.0, 5.0):
                    await asyncio.sleep(delay)
                    status_response = await client.get(
                        f"{self.base_url}/sell/feed/v1/task/{task_id}",
                        headers=task_headers,
                    )
                    if status_response.status_code != 200:
                        log.warning(
                            "ebay.seller_hub_feed_status_failed",
                            task_id=task_id,
                            status_code=status_response.status_code,
                            response=status_response.text[:500],
                        )
                        continue
                    try:
                        task_payload = status_response.json()
                    except ValueError:
                        task_payload = None
                    status = _feed_task_status(task_payload)
                    log.info("ebay.seller_hub_feed_status", task_id=task_id, status=status)
                    if status in {"COMPLETED", "COMPLETED_WITH_ERROR", "FAILED", "CANCELLED"}:
                        terminal_status = status
                        break

                if terminal_status in {"COMPLETED_WITH_ERROR", "FAILED", "CANCELLED"}:
                    result_response = await client.get(
                        f"{self.base_url}/sell/feed/v1/task/{task_id}/download_result_file",
                        headers=task_headers,
                    )
                    result_detail = (
                        _feed_result_text(result_response)
                        if result_response.status_code == 200
                        else f"Unable to download eBay result file ({result_response.status_code})"
                    )
                    if result_detail.count(",") > 8 and result_detail.count("\n") <= 1:
                        summary = ""
                        if isinstance(task_payload, dict):
                            upload_summary = task_payload.get("uploadSummary")
                            if upload_summary:
                                summary = f" Task summary: {upload_summary}."
                        result_detail = "eBay returned no row-level error details." + summary
                    return {
                        "success": False,
                        "error": (
                            f"eBay rejected the Seller Hub draft feed (task {task_id}, "
                            f"{terminal_status}): {result_detail}"
                        ),
                    }

                if terminal_status == "COMPLETED":
                    return {
                        "success": True,
                        "draft_id": task_id,
                        "draft_url": "https://www.ebay.co.uk/sh/lst/drafts",
                        "status": "DRAFT",
                    }
            return {
                "success": True,
                "draft_id": task_id,
                "draft_url": "https://www.ebay.co.uk/sh/lst/drafts",
                "status": "PROCESSING",
                "message": "eBay accepted the feed and is still processing it",
            }
        except Exception as exc:
            log.exception("ebay.seller_hub_draft_upload_failed")
            return {"success": False, "error": f"eBay Seller Hub draft upload failed: {exc}"}

    async def create_listing(
        self,
        title: str,
        description: str,
        price: float,
        image_urls: list[str],
        category_id: str = "179",  # PC Desktops & All-in-Ones
        condition: str = "USED",
        quantity: int = 1,
        location: str = "UK",
        shipping_cost: float = 15.0,
        merchant_location_key: str = "UK_WAREHOUSE",
        payment_policy_id: Optional[str] = None,
        return_policy_id: Optional[str] = None,
        fulfillment_policy_id: Optional[str] = None,
        aspects: Optional[dict[str, list[str]]] = None,
        publish: bool = True,
    ) -> dict:
        """
        Create a new fixed-price listing on eBay using Inventory API.

        Follows official workflow:
          1. Create inventory item
          2. Create offer
          3. Publish offer

        Returns: {
            "listing_id": "...",
            "sku": "...",
            "url": "https://ebay.co.uk/itm/...",
            "status": "ACTIVE",
        }
        """
        try:
            image_urls = _normalise_ebay_image_urls(image_urls)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        sku = f"FLP-{uuid.uuid4().hex[:12].upper()}"

        try:
            # Use the provided user token directly
            if not self.access_token:
                raise ValueError("eBay user OAuth token required")

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "Content-Language": "en-GB",
                "Accept": "application/json",
                "X-EBAY-API-SITEID": "EBAY_GB",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                # Step 1: Create or verify merchant location (required for all listings)
                log.info("ebay.ensuring_merchant_location")
                location_key = merchant_location_key

                # Try to create location (safe — POST returns 409 if it already exists)
                location_create_resp = await client.post(
                    f"{self.base_url}/sell/inventory/v1/location/{location_key}",
                    json={
                        "merchantLocationStatus": "ENABLED",
                        "name": f"FlipFlop {location} Warehouse",
                        "locationTypes": ["WAREHOUSE"],
                        "location": {
                            "address": {
                                "addressLine1": "1 Example Street",
                                "city": "London",
                                "stateOrProvince": "London",
                                "postalCode": "SW1A 1AA",
                                "country": "GB",
                            }
                        },
                    },
                    headers=headers,
                )

                location_already_exists = "already exists" in location_create_resp.text
                if location_create_resp.status_code not in [200, 201, 204, 409] and not location_already_exists:
                    log.error(
                        "ebay.location_creation_failed",
                        status=location_create_resp.status_code,
                        body=location_create_resp.text,
                    )
                    return {
                        "success": False,
                        "error": f"Failed to create merchant location: {location_create_resp.status_code}: {location_create_resp.text}",
                    }

                # Step 2: Create inventory item
                log.info("ebay.creating_inventory_item", sku=sku, title=title[:50])

                # Normalize condition to eBay's actual ConditionEnum values.
                # Plain "USED" is NOT valid — eBay requires a specific grade.
                _VALID_CONDITIONS = {
                    "NEW",
                    "LIKE_NEW",
                    "NEW_OTHER",
                    "NEW_WITH_DEFECTS",
                    "MANUFACTURER_REFURBISHED",
                    "CERTIFIED_REFURBISHED",
                    "EXCELLENT_REFURBISHED",
                    "VERY_GOOD_REFURBISHED",
                    "GOOD_REFURBISHED",
                    "SELLER_REFURBISHED",
                    "USED_EXCELLENT",
                    "USED_VERY_GOOD",
                    "USED_GOOD",
                    "USED_ACCEPTABLE",
                    "FOR_PARTS_OR_NOT_WORKING",
                }

                if not all((payment_policy_id, return_policy_id, fulfillment_policy_id)):
                    return {
                        "success": False,
                        "error": "eBay business policy IDs are required (payment, returns and fulfilment). Configure the seller's policy IDs before posting.",
                    }
                condition_normalized = condition.upper()
                if condition_normalized not in _VALID_CONDITIONS:
                    condition_normalized = "USED_EXCELLENT"

                item_aspects = dict(aspects) if aspects else {}
                item_aspects.setdefault("Brand", ["FlipFlop"])
                item_aspects.setdefault("Type", ["Desktop"])

                inventory_item = {
                    "product": {
                        "title": title[:80],
                        "description": _inventory_product_description(description, title),
                        "imageUrls": image_urls,
                        "aspects": item_aspects,
                    },
                    "condition": condition_normalized,
                    "availability": {
                        "shipToLocationAvailability": {
                            "quantity": quantity,
                        }
                    },
                }

                log.info(
                    "ebay.sending_inventory_request",
                    url=f"{self.base_url}/sell/inventory/v1/inventory_item/{sku}",
                    payload=inventory_item,
                )
                inventory_url = f"{self.base_url}/sell/inventory/v1/inventory_item/{sku}"
                inventory_resp = await client.put(
                    inventory_url,
                    json=inventory_item,
                    headers=headers,
                )
                # PUT is idempotent for this SKU. eBay occasionally returns a
                # generic Core Inventory Service 500/503 during a brief
                # backend outage; one short retry avoids losing an otherwise
                # valid draft without creating a duplicate inventory item.
                if inventory_resp.status_code in (500, 503):
                    log.warning(
                        "ebay.inventory_retry",
                        status=inventory_resp.status_code,
                        sku=sku,
                        request_id=inventory_resp.headers.get("X-EBAY-C-REQUEST-ID"),
                    )
                    await asyncio.sleep(1.0)
                    inventory_resp = await client.put(
                        inventory_url,
                        json=inventory_item,
                        headers=headers,
                    )
                log.info(
                    "ebay.inventory_response",
                    status=inventory_resp.status_code,
                    body=inventory_resp.text,
                )

                if inventory_resp.status_code not in [200, 201, 204]:
                    error_msg = inventory_resp.text
                    try:
                        error_json = inventory_resp.json()
                        errors = error_json.get("errors", [])
                        error_details = []
                        for err in errors:
                            # Try different error message fields
                            msg = (
                                err.get("longMessage")
                                or err.get("message")
                                or err.get("errorDescription")
                                or str(err)
                            )
                            error_details.append(msg)
                        if error_details:
                            error_msg = " | ".join(error_details)
                    except Exception as parse_err:
                        log.warning("ebay.error_parse_failed", error=str(parse_err))

                    log.error(
                        "ebay.inventory_item_failed",
                        status=inventory_resp.status_code,
                        error=error_msg,
                        sku=sku,
                        request_payload=inventory_item,
                        full_response=inventory_resp.text,
                    )
                    return {
                        "success": False,
                        "error": f"Failed to create inventory item: {inventory_resp.status_code}: {error_msg}",
                        "details": {
                            "status": inventory_resp.status_code,
                            "response": error_msg,
                            "sku": sku,
                            "ebay_request_id": inventory_resp.headers.get("X-EBAY-C-REQUEST-ID"),
                        },
                    }

                log.info("ebay.inventory_item_created", sku=sku)

                # Step 2: Create offer
                log.info("ebay.creating_offer", sku=sku)

                offer = {
                    "sku": sku,
                    "marketplaceId": "EBAY_GB",  # UK marketplace
                    "format": "FIXED_PRICE",
                    "categoryId": category_id,
                    "listingDescription": prepare_ebay_listing_description(
                        description or title
                    )[:EBAY_LISTING_DESCRIPTION_MAX_LENGTH],
                    "merchantLocationKey": merchant_location_key,
                    "pricingSummary": {
                        "price": {
                            "currency": "GBP",
                            "value": str(price),
                        }
                    },
                    "listingPolicies": {
                        "paymentPolicyId": payment_policy_id,
                        "returnPolicyId": return_policy_id,
                        "fulfillmentPolicyId": fulfillment_policy_id,
                        "bestOfferTerms": {
                            "bestOfferEnabled": True,
                            "autoAcceptPrice": {
                                "currency": "GBP",
                                "value": str(round(price * 0.90, 2)),
                            },
                            "autoDeclinePrice": {
                                "currency": "GBP",
                                "value": str(round(price * 0.80, 2)),
                            },
                        },
                    },
                }

                offer_resp = await client.post(
                    f"{self.base_url}/sell/inventory/v1/offer",
                    json=offer,
                    headers=headers,
                )

                if offer_resp.status_code not in [200, 201]:
                    error_msg = offer_resp.text
                    log.error(
                        "ebay.offer_creation_failed",
                        status=offer_resp.status_code,
                        error=error_msg,
                        sku=sku,
                    )
                    return {
                        "success": False,
                        "error": f"Failed to create offer: {offer_resp.status_code}: {error_msg}",
                    }

                offer_data = offer_resp.json()
                offer_id = offer_data.get("offerId")

                if not offer_id:
                    log.error("ebay.offer_no_id", response=offer_data)
                    return {
                        "success": False,
                        "error": "No offerId returned from offer creation",
                    }

                log.info("ebay.offer_created", offer_id=offer_id, sku=sku)

                # An eBay offer can remain unpublished. This is the real eBay
                # draft state; it is not a local-only placeholder.
                if not publish:
                    log.info("ebay.offer_saved_as_draft", offer_id=offer_id, sku=sku)
                    return {
                        "success": True,
                        "offer_id": offer_id,
                        "sku": sku,
                        "status": "DRAFT",
                    }

                # Step 3: Publish offer (this creates the actual listing)
                log.info("ebay.publishing_offer", offer_id=offer_id)

                publish_resp = await client.post(
                    f"{self.base_url}/sell/inventory/v1/offer/{offer_id}/publish",
                    headers=headers,
                )

                if publish_resp.status_code not in [200, 201]:
                    error_msg = publish_resp.text
                    log.error(
                        "ebay.publish_failed",
                        status=publish_resp.status_code,
                        error=error_msg,
                        offer_id=offer_id,
                    )
                    return {
                        "success": False,
                        "error": f"Failed to publish listing: {publish_resp.status_code}: {error_msg}",
                    }

                publish_data = publish_resp.json()
                listing_id = publish_data.get("listingId")

                if not listing_id:
                    log.error("ebay.publish_no_listing_id", response=publish_data)
                    return {
                        "success": False,
                        "error": "No listingId returned from publish",
                    }

                domain = "www.ebay.co.uk" if self.environment == "production" else "sandbox.ebay.com"
                listing_url = f"https://{domain}/itm/{listing_id}"

                log.info(
                    "ebay.listing_created",
                    listing_id=listing_id,
                    sku=sku,
                    title=title[:50],
                    price=price,
                )

                return {
                    "success": True,
                    "listing_id": listing_id,
                    "sku": sku,
                    "url": listing_url,
                    "status": "ACTIVE",
                    "offer_id": offer_id,
                }

        except Exception as exc:
            log.error("ebay.listing_exception", error=str(exc))
            return {
                "success": False,
                "error": f"Failed to post listing: {str(exc)}",
            }

    async def publish_offer(self, offer_id: str) -> dict:
        """Publish an existing unpublished Inventory API offer."""
        if not offer_id:
            return {"success": False, "error": "No eBay draft offer is saved for this build."}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/sell/inventory/v1/offer/{offer_id}/publish",
                    headers={**self.headers, "Content-Language": "en-GB"},
                )
            if response.status_code not in (200, 201):
                return {"success": False, "error": f"Failed to publish eBay draft: {response.status_code}: {response.text}"}
            data = response.json()
            listing_id = data.get("listingId")
            if not listing_id:
                return {"success": False, "error": "eBay did not return a listing ID when publishing the draft."}
            domain = "www.ebay.co.uk" if self.environment == "production" else "sandbox.ebay.com"
            return {
                "success": True,
                "listing_id": listing_id,
                "url": f"https://{domain}/itm/{listing_id}",
                "offer_id": offer_id,
                "status": "ACTIVE",
            }
        except Exception as exc:
            log.error("ebay.draft_publish_exception", offer_id=offer_id, error=str(exc))
            return {"success": False, "error": f"Failed to publish eBay draft: {exc}"}

    async def update_listing(
        self,
        listing_id: str,
        sku: str,
        title: str,
        description: str,
        price: float,
        image_urls: list[str],
        condition: str,
        payment_policy_id: Optional[str],
        return_policy_id: Optional[str],
        fulfillment_policy_id: Optional[str],
        aspects: Optional[dict[str, list[str]]] = None,
    ) -> dict:
        """Update an Inventory-API listing using its SKU and offer.

        Inventory-created listings cannot be revised with Trading API
        ReviseFixedPriceItem. The offer is looked up by SKU, then both the
        inventory item and offer are updated with business-policy IDs.
        """
        if not sku:
            return {"success": False, "error": "Existing eBay listing has no inventory SKU; it must be relisted."}
        if not all((payment_policy_id, return_policy_id, fulfillment_policy_id)):
            return {"success": False, "error": "eBay business policy IDs are required (payment, returns and fulfilment)."}
        try:
            image_urls = _normalise_ebay_image_urls(image_urls)
        except ValueError as exc:
            return {"success": False, "error": str(exc)}

        valid_conditions = {
            "NEW", "LIKE_NEW", "NEW_OTHER", "NEW_WITH_DEFECTS",
            "MANUFACTURER_REFURBISHED", "CERTIFIED_REFURBISHED",
            "EXCELLENT_REFURBISHED", "VERY_GOOD_REFURBISHED",
            "GOOD_REFURBISHED", "SELLER_REFURBISHED", "USED_EXCELLENT",
            "USED_VERY_GOOD", "USED_GOOD", "USED_ACCEPTABLE",
            "FOR_PARTS_OR_NOT_WORKING",
        }
        normalized_condition = (condition or "USED_EXCELLENT").upper()
        if normalized_condition not in valid_conditions:
            normalized_condition = "USED_EXCELLENT"
        item_aspects = dict(aspects) if aspects else {}
        item_aspects.setdefault("Brand", ["FlipFlop"])
        item_aspects.setdefault("Type", ["Desktop"])
        headers = {**self.headers, "Content-Language": "en-GB"}
        inventory_item = {
            "product": {
                "title": title[:80],
                "description": _inventory_product_description(description, title),
                "imageUrls": image_urls,
                "aspects": item_aspects,
            },
            "condition": normalized_condition,
            "availability": {"shipToLocationAvailability": {"quantity": 1}},
        }
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                item_resp = await client.put(
                    f"{self.base_url}/sell/inventory/v1/inventory_item/{sku}",
                    json=inventory_item,
                    headers=headers,
                )
                if item_resp.status_code not in (200, 201, 204):
                    return {"success": False, "error": f"Failed to update eBay inventory item: {item_resp.status_code}: {item_resp.text}"}

                offers_resp = await client.get(
                    f"{self.base_url}/sell/inventory/v1/offer",
                    params={"sku": sku, "marketplace_id": "EBAY_GB"},
                    headers=headers,
                )
                if offers_resp.status_code != 200:
                    return {"success": False, "error": f"Could not find the eBay offer for SKU {sku}: {offers_resp.status_code}: {offers_resp.text}"}
                offers = offers_resp.json().get("offers") or []
                offer = next((o for o in offers if o.get("marketplaceId") == "EBAY_GB"), None)
                if not offer or not offer.get("offerId"):
                    return {"success": False, "error": f"No active eBay Inventory API offer was found for SKU {sku}; relist this build to repair the listing."}
                offer_id = offer["offerId"]
                offer_payload = {
                    "sku": sku,
                    "marketplaceId": "EBAY_GB",
                    "format": "FIXED_PRICE",
                    "availableQuantity": offer.get("availableQuantity") or 1,
                    "categoryId": offer.get("categoryId") or "179",
                    "listingDescription": prepare_ebay_listing_description(description or title)[:EBAY_LISTING_DESCRIPTION_MAX_LENGTH],
                    "merchantLocationKey": offer.get("merchantLocationKey") or "UK_WAREHOUSE",
                    "pricingSummary": {"price": {"currency": "GBP", "value": str(price)}},
                    "listingPolicies": {
                        "paymentPolicyId": payment_policy_id,
                        "returnPolicyId": return_policy_id,
                        "fulfillmentPolicyId": fulfillment_policy_id,
                        "bestOfferTerms": {
                            "bestOfferEnabled": True,
                            "autoAcceptPrice": {
                                "currency": "GBP",
                                "value": str(round(price * 0.90, 2)),
                            },
                            "autoDeclinePrice": {
                                "currency": "GBP",
                                "value": str(round(price * 0.80, 2)),
                            },
                        },
                    },
                }
                offer_resp = await client.put(
                    f"{self.base_url}/sell/inventory/v1/offer/{offer_id}",
                    json=offer_payload,
                    headers=headers,
                )
                if offer_resp.status_code not in (200, 201, 204):
                    return {"success": False, "error": f"Failed to update eBay offer: {offer_resp.status_code}: {offer_resp.text}"}
                # eBay's updateOffer response intentionally does not include
                # listingId. The listing ID supplied by the caller remains
                # authoritative for an existing active listing.
                if not listing_id:
                    return {"success": False, "error": "Existing eBay listing ID is missing; relist this build."}
                domain = "www.ebay.co.uk" if self.environment == "production" else "sandbox.ebay.com"
                return {"success": True, "listing_id": listing_id, "sku": sku, "offer_id": offer_id, "url": f"https://{domain}/itm/{listing_id}", "status": "ACTIVE"}
        except Exception as exc:
            log.error("ebay.inventory_update_exception", error=str(exc), sku=sku)
            return {"success": False, "error": f"Failed to update eBay listing: {exc}"}


async def post_flip_to_ebay(
    title: str,
    description: str,
    price: float,
    image_urls: list[str],
    access_token: str,
    environment: str = "production",
    app_id: Optional[str] = None,
    client_secret: Optional[str] = None,
    condition: str = "USED_EXCELLENT",
    payment_policy_id: Optional[str] = None,
    return_policy_id: Optional[str] = None,
    fulfillment_policy_id: Optional[str] = None,
    aspects: Optional[dict[str, list[str]]] = None,
    listing_id: Optional[str] = None,  # If provided, update existing listing; else create new
    sku: Optional[str] = None,
    publish: bool = True,
) -> dict:
    """
    Convenience function to post or update a flip's listing on eBay.

    If listing_id is provided, updates the existing listing.
    If listing_id is None, creates a new listing.

    Uses Application Token (server-to-server) auth if app_id and client_secret are provided.
    Falls back to user token if not provided.

    Usage in API endpoint:
        result = await post_flip_to_ebay(
            title=title,
            description=description,
            price=price,
            image_urls=["https://example.com/image1.jpg"],
            access_token=user_token,
            app_id=settings.ebay_app_id,
            client_secret=settings.ebay_client_secret,
            listing_id=None  # Pass existing listing_id to update, None to create
        )
        if result["success"]:
            flip.ebay_listing_id = result["listing_id"]
            flip.ebay_listing_url = result["url"]
    """
    poster = EbayListingPoster(
        environment=environment,
        access_token=access_token,
        app_id=app_id,
        client_secret=client_secret,
    )
    async def revise(existing_listing_id: str) -> dict:
        return await poster.update_listing(
            listing_id=existing_listing_id,
            sku=sku or "",
            title=title,
            description=description,
            price=price,
            image_urls=image_urls,
            condition=condition,
            payment_policy_id=payment_policy_id,
            return_policy_id=return_policy_id,
            fulfillment_policy_id=fulfillment_policy_id,
            aspects=aspects,
        )

    if listing_id:
        return await revise(listing_id)

    result = await poster.create_listing(
        title=title,
        description=description,
        price=price,
        image_urls=image_urls,
        shipping_cost=15.0,
        condition=condition,
        payment_policy_id=payment_policy_id,
        return_policy_id=return_policy_id,
        fulfillment_policy_id=fulfillment_policy_id,
        aspects=aspects,
        publish=publish,
    )

    # Recover builds whose original successful listing ID was never saved by
    # the old broken update path. eBay includes that active item ID in its
    # duplicate-listing rejection; adopt and revise it instead of asking the
    # seller to manually repair local state.
    if not result.get("success"):
        duplicate = re.search(
            r"already have on eBay:.*?\((\d{9,19})\)",
            result.get("error", ""),
            flags=re.IGNORECASE | re.DOTALL,
        )
        if duplicate:
            return await revise(duplicate.group(1))

    return result
