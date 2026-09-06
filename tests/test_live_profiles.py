"""Gated live acceptance for extraction profiles. Skipped without --run-live."""
import pytest

from _ai_processing import extract_metadata_from_text
from _document_processing import render_filename
from _profiles import build_metadata_model, select_profile


@pytest.mark.live
@pytest.mark.parametrize("config_fixture", [
    pytest.param("openai_config", marks=pytest.mark.openai, id="openai"),
    pytest.param("anthropic_config", marks=pytest.mark.anthropic, id="anthropic"),
    pytest.param("ollama_config", marks=pytest.mark.ollama, id="ollama"),
])
@pytest.mark.parametrize("profile_id,source,expected,filename", [
    pytest.param("business", "INVOICE\nFrom: ACME\nBill to: Owner\nInvoice date: 06.09.2026\nInvoice number: 12345\nSubtotal: 10,00\nTax: 2,13\nFinal total including tax: 12,13\n", {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "IN", "description": "12,13"}, "20260906 ACME IN 12,13.pdf", id="incoming-final-total"),
    pytest.param("business", "INVOICE\nFrom: Owner\nBill to: ACME\nInvoice date: 06.09.2026\nInvoice number: 12345\nFinal total including tax: 1.234,56\n", {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "OUT", "description": "1.234,56"}, "20260906 ACME OUT 1.234,56.pdf", id="outgoing-grouped-total"),
    pytest.param("business", "INVOICE\nFrom: ACME\nBill to: Owner\nInvoice date: 06.09.2026\nInvoice number: 12345\nFinal total including tax: EUR 12,13\n", {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "IN", "description": "EUR 12,13"}, "20260906 ACME IN EUR 12,13.pdf", id="printed-currency"),
    pytest.param("business", "INVOICE\nFrom: ACME\nBill to: Owner\nInvoice date: 06.09.2026\nInvoice number: 12345\nItem: consultation\nQuantity: 2\nUnit price: 6,00\n", {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "IN", "description": ""}, "20260906 ACME IN.pdf", id="no-total-no-calculation-or-id"),
    pytest.param("business", "Letter\nFrom: ACME\nTo: Owner\nDate: 06.09.2026\nSubject: Terminbestätigung\nIhr Termin findet nächste Woche statt.\n", {"document_date": "06.09.2026", "company_name": "ACME", "document_type": "Letter", "description": "Terminbestätigung"}, "20260906 ACME Letter Terminbestätigung.pdf", id="verbatim-original-language-subject"),
    pytest.param("academic", "Untersuchung der Netze - Methoden und Ergebnisse\nAlice Smith, Bob Jones\nPublication year: 2026\nAbstract: We study networks.\n", {"document_date": "01.01.2026", "first_author_surname": "Smith", "journal_name": "", "title": "Untersuchung der Netze - Methoden und Ergebnisse"}, "20260101 Smith Untersuchung der Netze - Methoden und Ergebnisse.pdf", id="academic-year-only-full-title-no-venue"),
])
def test_live_profile_extraction(request, config_fixture, profile_id, source, expected, filename):
    config = request.getfixturevalue(config_fixture)
    config["company"]["name"] = "Owner"
    config["output"]["language"] = "English"
    config["pdf"].update(incoming_invoice="IN", outgoing_invoice="OUT")
    selected, profile = select_profile(config, profile_id)
    model = build_metadata_model(profile)
    metadata = extract_metadata_from_text(source, config, profile=profile, metadata_model=model)
    assert metadata.model_dump() == expected
    assert render_filename(selected, profile, metadata.model_dump(), config) == filename
