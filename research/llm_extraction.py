import json
import urllib.request
import urllib.error
from pathlib import Path

# 1. Find the research folder
BASE_DIR = Path(__file__).parent

# 2. Connect to Ollama
MODEL = "llama3.2"
OLLAMA_URL = "http://localhost:11434/api/generate"

# 3. Input and output files
input_file = BASE_DIR / "data" / "extracted_parameters.json"
output_file = BASE_DIR / "data" / "llm_extracted_parameters.json"

# 4. Read the 62 prepared research papers
with open(input_file, "r", encoding="utf-8") as file:
    papers = json.load(file)

# 5. Extract information from one paper first
MAX_PAPERS = len(papers)

for index, paper in enumerate(papers[:MAX_PAPERS], start=1):

    print(f"\nProcessing paper {index}: {paper.get('title', 'Unknown')}")

    title = paper.get("title", "")
    abstract = paper.get("abstract", "")

    prompt = f"""
You are a scientific research extraction assistant.

Read the research paper title and abstract carefully.

Extract only information explicitly supported by the text.

Return valid JSON with these two fields:

{{
    "parameters": [
        {{
            "name": "parameter name",
            "value": "reported value or null",
            "unit": "unit or null",
            "evidence": "supporting text or null"
        }}
    ],
    "datasets": [
        {{
            "name": "dataset name",
            "description": "description or null",
            "evidence": "supporting text or null"
        }}
    ]
}}

Rules:
- Never invent information.
- Use null when information is not reported.
- Do not assume missing values.
- Include only parameters and datasets supported by the abstract.
- Return JSON only.

PAPER TITLE:
{title}

PAPER ABSTRACT:
{abstract}
"""

    try:
        # 6. Send the paper to Ollama AI
        request_data = {
            "model": MODEL,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0
            }
        }

        request = urllib.request.Request(
            OLLAMA_URL,
            data=json.dumps(request_data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        with urllib.request.urlopen(request, timeout=300) as response:
            response_data = json.loads(response.read().decode("utf-8"))

        # 7. Convert Ollama response into Python data
        result = json.loads(response_data["response"])

        paper["parameters"] = result.get("parameters", [])
        paper["datasets"] = result.get("datasets", [])
        paper["extraction_status"] = "completed"
        paper["llm_model"] = MODEL

        print("Extraction completed successfully!")

    except Exception as error:
        paper["extraction_status"] = "error"
        print("Extraction error:", error)

# 8. Save all papers in a separate output file
with open(output_file, "w", encoding="utf-8") as file:
    json.dump(papers, file, indent=4, ensure_ascii=False)

print("\nLLM extraction test completed!")
print("Total papers in file:", len(papers))
print("Saved to:", output_file)