import re
from typing import List, Tuple

from ...config.config import logger


def find_markdown_tables(md_text: str) -> List[Tuple[int, int, str]]:
    logger.debug(f"Searching for markdown tables in text ({len(md_text)} characters)")
    lines = md_text.splitlines()
    tables: List[Tuple[int, int, str]] = []

    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("|") and "|" in lines[i].strip()[1:]:
            header_idx = i
            if i + 1 < len(lines):
                sep = lines[i + 1].strip()
                if sep.startswith("|") and re.fullmatch(r"\|[\-:\s\|]+\|", sep):
                    j = i + 2
                    while j < len(lines) and lines[j].strip().startswith("|"):
                        j += 1
                    table_block = "\n".join(lines[header_idx:j]).strip()
                    start_char = len("\n".join(lines[:header_idx])) + (1 if header_idx > 0 else 0)
                    end_char = start_char + len(table_block)
                    tables.append((start_char, end_char, table_block))
                    logger.debug(f"Found table at lines {header_idx+1}-{j}, length: {len(table_block)} characters")
                    i = j
                    continue
        i += 1

    logger.info(f"Extracted {len(tables)} markdown table(s) from document")
    return tables




def normalize_markdown_table(table_md: str) -> str:
    lines = [ln for ln in table_md.splitlines() if ln.strip()]
    if len(lines) < 2:
        return table_md

    def cells(line: str) -> List[str]:
        return [c.strip() for c in line.strip().strip("|").split("|")]

    header = cells(lines[0])
    ncols = len(header)
    if ncols == 0:
        return table_md

    def fmt(row: List[str]) -> str:
        if len(row) < ncols:
            row = row + [""] * (ncols - len(row))
        elif len(row) > ncols:
            row = row[: ncols - 1] + [" ".join(row[ncols - 1:])]
        return "| " + " | ".join(row) + " |"

    out = [fmt(header), "| " + " | ".join(["---"] * ncols) + " |"]
    for line in lines[2:]:
        out.append(fmt(cells(line)))
    return "\n".join(out)


def table_has_data_rows(table_md: str) -> bool:
    rows = [ln for ln in table_md.splitlines() if ln.strip().startswith("|")]
    for row in rows[2:]:
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if any(cells):  
            return True
    return False


def extract_tables_from_text(text: str) -> List[str]:
    logger.info("Extracting markdown tables from text...")
    tables = find_markdown_tables(text)
    if not tables:
        logger.info("No markdown tables found in text")
        return []

    kept = [tb[2] for tb in tables if table_has_data_rows(tb[2])]
    dropped = len(tables) - len(kept)
    if dropped:
        logger.info(f"Dropped {dropped} headers-only table(s) (likely mis-parsed diagrams)")

    table_strings = [normalize_markdown_table(t) for t in kept]
    logger.info(f"Extracted {len(table_strings)} table(s) from document")
    return table_strings
