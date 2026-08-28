import logging
from pathlib import Path

import pymupdf4llm

from lexiguard.config import PROJECT_ROOT, RAW_DATA_DIR, get_settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def parse_contract(pdf_path: Path, use_llama_cloud: bool = False) -> str:
    """Parse a PDF contract into clean Markdown."""
    if not pdf_path.exists():
        raise FileNotFoundError(f"File not found: {pdf_path}")

    settings = get_settings()

    if use_llama_cloud and settings.llama_cloud_api_key:
        logger.info(f"Parsing {pdf_path.name} with LlamaParse")
        try:
            from llama_parse import LlamaParse
            parser = LlamaParse(
                api_key=settings.llama_cloud_api_key,
                result_type="markdown"
            )
            docs = parser.load_data(str(pdf_path))
            return "\n\n".join([doc.text for doc in docs])
        except Exception as e:
            logger.error(f"LlamaParse failed: {e}. Falling back to pymupdf4llm.")

    logger.info(f"Parsing {pdf_path.name} with pymupdf4llm")
    try:
        # pymupdf4llm extracts tables, headers, and formatted text effectively to Markdown
        md_text = pymupdf4llm.to_markdown(str(pdf_path))
        return md_text
    except Exception as e:
        logger.error(f"pymupdf4llm failed on {pdf_path.name}: {e}")
        raise

def parse_all_contracts(input_dir: Path = None, output_dir: Path = None) -> list[Path]:
    """Parse all PDF contracts in a directory to Markdown."""
    in_dir = input_dir or RAW_DATA_DIR
    out_dir = output_dir or PROJECT_ROOT / "data" / "parsed"

    out_dir.mkdir(parents=True, exist_ok=True)
    parsed_files = []

    if not in_dir.exists():
        logger.warning(f"Input directory does not exist: {in_dir}")
        return parsed_files

    for pdf_path in in_dir.glob("*.pdf"):
        md_path = out_dir / f"{pdf_path.stem}.md"

        if md_path.exists():
            logger.info(f"Skipping {pdf_path.name}, already parsed")
            parsed_files.append(md_path)
            continue

        try:
            markdown = parse_contract(pdf_path)
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown)
            logger.info(f"Saved parsed markdown to {md_path.name}")
            parsed_files.append(md_path)
        except Exception as e:
            logger.error(f"Error processing {pdf_path.name}: {e}")

    return parsed_files

if __name__ == "__main__":
    parse_all_contracts()
