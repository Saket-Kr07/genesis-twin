import json
from pathlib import Path

# 1. Find the research data folder
DATA_FOLDER = Path(__file__).parent / "data"

# 2. Locate the fetched papers
PAPERS_FILE = DATA_FOLDER / "papers.json"

# 3. Create the output file path
OUTPUT_FILE = DATA_FOLDER / "extracted_parameters.json"


# 4. Read the fetched research papers
def load_papers():
    with open(PAPERS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


# 5. Prepare a structured record for each paper
def prepare_extraction(paper):

    return {
        "doi": paper.get("doi", ""),
        "title": paper.get("title", ""),
        "abstract": paper.get("abstract", ""),
        "parameters": [],
        "datasets": [],
        "extraction_status": "pending"
    }


# 6. Main program
def main():

    papers = load_papers()

    extracted_records = []

    for paper in papers:

        record = prepare_extraction(paper)

        extracted_records.append(record)

    # 7. Save the prepared records
    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            extracted_records,
            file,
            indent=4,
            ensure_ascii=False
        )

    print("Extraction preparation completed!")
    print("Total papers processed:", len(extracted_records))
    print("Saved to:", OUTPUT_FILE)


if __name__ == "__main__":
    main()