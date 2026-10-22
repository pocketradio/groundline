from groundline.embeddings import document_mime_type


def test_document_mime_type_uses_filename_extension() -> None:
    assert document_mime_type("metadata.json") == "application/json"
    assert document_mime_type("unknown.bin") == "application/octet-stream"
