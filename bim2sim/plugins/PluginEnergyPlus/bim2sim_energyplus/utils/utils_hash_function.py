import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_hash(ifc_path) -> str:
    """Generate SHA-256 hash for IFC file"""
    sha256_hash = hashlib.sha256()

    with open(ifc_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256_hash.update(chunk)
    ifc_hash = sha256_hash.hexdigest()
    ifc_filename = Path(ifc_path).name
    hash_prefix = "IFC_GEOMETRY_HASH"  # prefix
    hash_line = f"! {hash_prefix}: {ifc_hash} | IFC_FILENAME: {ifc_filename}\n"
    logger.info(f"Generated hash for IFC file {ifc_filename}: {ifc_hash}")
    return hash_line


def add_hash_into_idf(hash_line, idf_path):
    """Add hash with specific prefix for easy search"""
    with open(idf_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    # Insert at first line
    lines.insert(0, hash_line)
    with open(idf_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)

    logger.info(f"Added hash to IDF file")
