import json
import psycopg2
from psycopg2.extras import Json
from getpass import getpass
from pathlib import Path

# Read the extracted research papers
file_path = Path(__file__).parent / "data" / "llm_extracted_parameters.json"

with open(file_path, "r", encoding="utf-8") as file:
    papers = json.load(file)

# Connect to PostgreSQL
password = getpass("Enter PostgreSQL password: ")

conn = psycopg2.connect(
    dbname="genesis_twin",
    user="postgres",
    password=password,
    host="localhost",
    port="5432"
)

cursor = conn.cursor()

try:
    for paper in papers:

        # Insert each paper as a separate record
        cursor.execute("""
            INSERT INTO papers
            (doi, title, abstract, extraction_status, llm_model, datasets)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id;
        """, (
            paper.get("doi") or None,
            paper.get("title"),
            paper.get("abstract"),
            paper.get("extraction_status"),
            paper.get("llm_model"),
            Json(paper.get("datasets", []))
        ))

        paper_id = cursor.fetchone()[0]

        # Insert only meaningful extracted parameters
        for parameter in paper.get("parameters", []):
            name = parameter.get("name")
            value = parameter.get("value")

            if not name or name == "null" or value is None or str(value).lower() == "null":
                continue

            cursor.execute("""
                INSERT INTO extracted_parameters
                (paper_id, parameter_name, parameter_value, unit, evidence)
                VALUES (%s, %s, %s, %s, %s);
            """, (
                paper_id,
                name,
                str(value),
                parameter.get("unit"),
                parameter.get("evidence")
            ))

    conn.commit()
    print("Import completed successfully!")
    print("Total papers imported:", len(papers))

except Exception:
    conn.rollback()
    raise

finally:
    cursor.close()
    conn.close()