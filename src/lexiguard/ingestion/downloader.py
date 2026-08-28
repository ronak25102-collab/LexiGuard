import logging
from pathlib import Path

from huggingface_hub import hf_hub_download

from lexiguard.config import CUAD_QA_DIR, RAW_DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def download_cuad_contracts(num_contracts: int = 10, output_dir: Path = None) -> list[Path]:
    """Download CUAD PDF contracts from HuggingFace."""
    out_dir = output_dir or RAW_DATA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Finding CUAD contract PDFs on HuggingFace...")
    try:
        from huggingface_hub import HfApi
        api = HfApi()
        files = api.list_repo_files("theatticusproject/cuad", repo_type="dataset")
        pdf_files = [f for f in files if f.endswith(".pdf") and "full_contract_pdf" in f]

        downloaded = []
        count = 0
        for file_path in pdf_files:
            if count >= num_contracts:
                break

            pdf_name = Path(file_path).name
            out_path = out_dir / pdf_name

            if out_path.exists():
                logger.info(f"Skipping {pdf_name}, already exists")
                downloaded.append(out_path)
                count += 1
                continue

            logger.info(f"Downloading {pdf_name}...")
            try:
                downloaded_file = hf_hub_download(
                    repo_id="theatticusproject/cuad",
                    filename=file_path,
                    repo_type="dataset"
                )

                with open(downloaded_file, 'rb') as f_in:
                    with open(out_path, 'wb') as f_out:
                        f_out.write(f_in.read())

                downloaded.append(out_path)
                count += 1
            except Exception as e:
                logger.error(f"Failed to download {pdf_name}: {e}")

        return downloaded
    except Exception as e:
        logger.error(f"Error accessing dataset: {e}")
        return []

def download_cuad_qa(output_dir: Path = None) -> Path | None:
    """Download CUAD QA JSON file for evaluation."""
    out_dir = output_dir or CUAD_QA_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    file_name = "CUAD_v1.json"
    out_path = out_dir / file_name

    if out_path.exists():
        logger.info(f"QA file {file_name} already exists at {out_path}")
        return out_path

    logger.info(f"Downloading {file_name}...")
    try:
        file_path = hf_hub_download(
            repo_id="theatticusproject/cuad",
            filename="CUAD_v1/CUAD_v1.json",
            repo_type="dataset"
        )

        with open(file_path, 'rb') as f_in:
            with open(out_path, 'wb') as f_out:
                f_out.write(f_in.read())

        logger.info(f"Successfully downloaded {file_name}")
        return out_path
    except Exception as e:
        logger.error(f"Failed to download QA JSON: {e}")
        return None

if __name__ == "__main__":
    download_cuad_contracts(num_contracts=5)
    download_cuad_qa()
