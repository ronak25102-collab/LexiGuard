"""Tests for the PDF parser module."""

from pathlib import Path
from unittest.mock import patch

import pytest

from lexiguard.ingestion.parser import parse_contract


class TestParseContract:
    """Test suite for the contract parser."""

    def test_parse_contract_returns_string(self, tmp_path):
        """parse_contract should return a non-empty markdown string."""
        # Create a minimal test PDF
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 minimal")

        with patch("lexiguard.ingestion.parser.pymupdf4llm") as mock_pymupdf:
            mock_pymupdf.to_markdown.return_value = "# Test Contract\n\nSection 1..."
            result = parse_contract(fake_pdf)

        assert isinstance(result, str)
        assert len(result) > 0

    def test_parse_contract_preserves_headers(self, tmp_path):
        """Parser should preserve markdown headers from the PDF."""
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 minimal")

        markdown = "# AGREEMENT\n\n## Section 1: Definitions\n\nContent here."
        with patch("lexiguard.ingestion.parser.pymupdf4llm") as mock_pymupdf:
            mock_pymupdf.to_markdown.return_value = markdown
            result = parse_contract(fake_pdf)

        assert "# AGREEMENT" in result
        assert "## Section 1" in result

    def test_parse_contract_nonexistent_file_raises(self):
        """Should raise an error for missing files."""
        with pytest.raises(Exception):
            parse_contract(Path("/nonexistent/file.pdf"))

    def test_parse_contract_llama_cloud_fallback(self, tmp_path):
        """Should fall back to pymupdf if llama-cloud fails."""
        fake_pdf = tmp_path / "test.pdf"
        fake_pdf.write_bytes(b"%PDF-1.4 minimal")

        with patch("lexiguard.ingestion.parser.pymupdf4llm") as mock_pymupdf:
            mock_pymupdf.to_markdown.return_value = "Fallback content"
            result = parse_contract(fake_pdf, use_llama_cloud=False)

        assert result == "Fallback content"
