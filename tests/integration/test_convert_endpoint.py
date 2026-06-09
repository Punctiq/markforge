from io import BytesIO
from pathlib import Path
import pytest

SAMPLES = Path(__file__).parent.parent / "samples"

def _post(client, filename, ai_cleanup="false"):
    data = {"file": (BytesIO((SAMPLES/filename).read_bytes()), filename), "ai_cleanup": ai_cleanup}
    return client.post("/api/v1/convert", data=data, content_type="multipart/form-data")

def test_no_file_returns_400(client):
    assert client.post("/api/v1/convert", data={}, content_type="multipart/form-data").status_code == 400

def test_unsupported_format_returns_422(client):
    r = client.post("/api/v1/convert", data={"file": (BytesIO(b"hi"), "file.txt")}, content_type="multipart/form-data")
    assert r.status_code == 422

def test_docx_returns_200(client):         assert _post(client, "sample.docx").status_code == 200
def test_docx_has_markdown(client):        assert len(_post(client,"sample.docx").get_json()["markdown"]) > 20
def test_docx_filename(client):            assert _post(client,"sample.docx").get_json()["filename"] == "sample.md"
def test_docx_has_stats(client):           assert "duration_ms" in _post(client,"sample.docx").get_json()["stats"]
def test_docx_ai_false(client):            assert _post(client,"sample.docx","false").get_json()["stats"]["ai_applied"] is False
def test_docx_content(client):             assert "Vendor" in _post(client,"sample.docx").get_json()["markdown"]

def test_pdf_returns_200(client):          assert _post(client, "sample.pdf").status_code == 200
def test_pdf_has_markdown(client):         assert len(_post(client,"sample.pdf").get_json()["markdown"]) > 10
def test_pdf_filename(client):             assert _post(client,"sample.pdf").get_json()["filename"] == "sample.md"

def test_odt_returns_200(client):          assert _post(client, "sample.odt").status_code == 200
def test_odt_has_markdown(client):         assert len(_post(client,"sample.odt").get_json()["markdown"]) > 20
def test_odt_content(client):              assert "Vendor" in _post(client,"sample.odt").get_json()["markdown"]

def test_doc_returns_200(client):          assert _post(client, "sample.doc").status_code == 200
def test_doc_has_markdown(client):         assert len(_post(client,"sample.doc").get_json()["markdown"]) > 20
def test_doc_content(client):              assert "Vendor" in _post(client,"sample.doc").get_json()["markdown"]
