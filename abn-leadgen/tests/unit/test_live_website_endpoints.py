"""Phone-only extraction does not reinterpret other number classes or index email."""
from types import SimpleNamespace

import pytest

from abr_engine.live.enrichment import _endpoints


@pytest.mark.parametrize("number", ["1300123456", "1800123456", "1900123456", "+12025550123", "131234"])
def test_non_mobile_or_fixed_line_number_is_not_collected(number):
    page = SimpleNamespace(html=f'<html><a href="tel:{number}">Business phone</a></html>')
    assert _endpoints(page, ["mobile", "landline"]) == []


def test_only_actual_allowed_mobile_and_landline_are_extracted():
    page = SimpleNamespace(html='<html>hello@example.com <a href="mailto:other@example.com">Email</a>'
        '<a href="tel:+61412345678">Mobile</a><a href="tel:+61731234567">Landline</a></html>')
    assert _endpoints(page, ["mobile", "landline"]) == [
        ("mobile", "+61412345678"), ("landline", "+61731234567")]
    assert _endpoints(page, ["landline"]) == [("landline", "+61731234567")]
    assert _endpoints(page, ["email"]) == []


def test_visible_office_phone_is_collected_without_tel_link():
    page = SimpleNamespace(html='<html><p>Office phone: (07) 3123 4567</p><p>Mobile: 0412 345 678</p></html>')
    assert set(_endpoints(page, ["mobile", "landline"])) == {("landline", "+61731234567"), ("mobile", "+61412345678")}


@pytest.mark.parametrize("text", ["ABN: 53 004 085 616", "ACN: 004 085 616", "QBCC licence: 12345678",
    "Licence number: 0731234567", "Office: (07) 3123 4567 ext 123", "Phone: 1300 123 456",
    "0412345678@example.com", "<script>Office: 0731234567</script>"])
def test_plain_text_identifiers_extensions_and_other_classes_are_excluded(text):
    assert _endpoints(SimpleNamespace(html='<html>'+text+'</html>'), ["mobile", "landline"]) == []
