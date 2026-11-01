from types import SimpleNamespace

from app.services.playbook_service import _verified_windows_licence_listing


def listing_with_capture(*, title="Microsoft Windows 11 Pro", dimensions="14.8 x 11.1 x 2.1 cm; 50 g",
                        manufacturer="Microsoft Software", rank="328 in Software; 10 in Operating Systems"):
    return SimpleNamespace(title=title, raw_specs={
        "bestseller": {"list_name": "Amazon Operating Systems Best Sellers"},
        "playbook_product_capture": {
            "status": "captured",
            "url": "https://www.amazon.co.uk/dp/B09XJ8PM2X",
            "sku": "B09XJ8PM2X",
            "title": title,
            "product_properties": {
                "Product Dimensions\n                                            ‏": f"‎ {dimensions}",
                "Manufacturer\n                                            ‏": f"‎ {manufacturer}",
                "Best Sellers Rank": rank,
            },
        },
    })


def test_amazon_physical_windows_listing_is_not_an_operating_system_licence_candidate():
    assert not _verified_windows_licence_listing(listing_with_capture())


def test_os_candidate_rejects_missing_physical_or_manufacturer_evidence():
    assert not _verified_windows_licence_listing(listing_with_capture(dimensions=""))
    assert not _verified_windows_licence_listing(listing_with_capture(manufacturer="Third Party"))
    assert not _verified_windows_licence_listing(listing_with_capture(rank="328 in Software"))


def test_royalcdkeys_exact_reviewed_windows_offer_is_a_candidate_for_review():
    url="https://royalcdkeys.com/en-gb/products/windows-11-pro-oem-cd-key"
    capture={"status":"captured","url":url,"digital_product":True,
        "licence_review_required":True,"licence_resale_rights_verified":False,
        "supplier_product_handle":"windows-11-pro-oem-cd-key",
        "product_properties":{"License type (supplier listing)":"OEM",
            "Key uniqueness (supplier claim)":"No key-reuse statement captured"}}
    listing=SimpleNamespace(title="Windows 11 Pro OEM CD Key",url=url,raw_specs={
        "royalcdkeys":{"category":"os","handle":"windows-11-pro-oem-cd-key"},
        "playbook_product_capture":capture})
    assert _verified_windows_licence_listing(listing)
    listing.raw_specs["playbook_product_capture"]["supplier_product_handle"]="wrong-handle"
    assert not _verified_windows_licence_listing(listing)
