import json
import urllib.parse
import urllib.request
from pathlib import Path

# 1. Choose the research topic
query = 'TITLE_ABS:"digital twin" AND (human OR healthcare OR physiology)'

# 2. Europe PMC API address
url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# 3. Set search options
params = {
    "query": query,
    "format": "json",
    "resultType": "core",
    "pageSize": 20
}

# 4. Create the complete API URL
api_url = url + "?" + urllib.parse.urlencode(params)

# 5. Connect to Europe PMC
request = urllib.request.Request(
    api_url,
    headers={"User-Agent": "GenesisTwin-Research/1.0"}
)

print("Fetching research papers...")

with urllib.request.urlopen(request, timeout=30) as response:
    data = json.loads(response.read().decode("utf-8"))

# 6. Extract the research papers
papers = []

for item in data["resultList"]["result"]:
    publication_types = item.get("pubTypeList", {}).get("pubType", [])

    if isinstance(publication_types, str):
        publication_types = [publication_types]

    paper = {
        "title": item.get("title", ""),
        "doi": item.get("doi", ""),
        "date": item.get("firstPublicationDate", ""),
        "abstract": item.get("abstractText", ""),
        "type": publication_types,
        "isPreprint": item.get("isPreprint", False)
    }

    papers.append(paper)

# 7. Create the data folder
output_folder = Path(__file__).parent / "data"
output_folder.mkdir(parents=True, exist_ok=True)

# 8. Save papers in JSON format
output_file = output_folder / "papers.json"

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(papers, file, indent=4, ensure_ascii=False)

print(f"Successfully collected {len(papers)} research papers!")
print(f"Saved to: {output_file}")