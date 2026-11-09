
import json
import urllib.parse
import urllib.request
from pathlib import Path

# 1. Choose multiple research topics
TOPICS = [
    'TITLE_ABS:"digital twin" AND (human OR healthcare OR physiology)',
    'TITLE_ABS:"digital twin" AND cardiovascular',
    'TITLE_ABS:"digital twin" AND respiratory',
    'TITLE_ABS:"digital twin" AND diabetes',
    'TITLE_ABS:"digital twin" AND medical'
]

# 2. Europe PMC API address
url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

# 3. Create an empty list to store papers
papers = []

# 4. Keep track of papers already collected
seen_papers = set()

# 5. Search every research topic
for query in TOPICS:

    print("\nSearching:", query)

    # 6. Set search options
    params = {
        "query": query,
        "format": "json",
        "resultType": "core",
        "pageSize": 20
    }

    # 7. Create the complete API URL
    api_url = url + "?" + urllib.parse.urlencode(params)

    # 8. Connect to Europe PMC
    request = urllib.request.Request(
        api_url,
        headers={"User-Agent": "GenesisTwin-Research/1.0"}
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        # 9. Extract research papers
        for item in data["resultList"]["result"]:

            doi = item.get("doi", "").strip()
            title = item.get("title", "").strip()

            # 10. Identify duplicate papers
            paper_key = doi.lower() if doi else title.lower()

            if not paper_key or paper_key in seen_papers:
                continue

            seen_papers.add(paper_key)

            publication_types = (
                item.get("pubTypeList", {}).get("pubType", [])
            )

            if isinstance(publication_types, str):
                publication_types = [publication_types]

            # 11. Store paper information
            paper = {
                "title": title,
                "doi": doi,
                "date": item.get("firstPublicationDate", ""),
                "abstract": item.get("abstractText", ""),
                "type": publication_types,
                "isPreprint": item.get("isPreprint", False),
                "searchTopic": query
            }

            papers.append(paper)

    except Exception as error:
        print("Error while fetching papers:", error)

# 12. Create the data folder
output_folder = Path(__file__).parent / "data"
output_folder.mkdir(parents=True, exist_ok=True)

# 13. Save papers in JSON format
output_file = output_folder / "papers.json"

with open(output_file, "w", encoding="utf-8") as file:
    json.dump(papers, file, indent=4, ensure_ascii=False)

# 14. Display final results
print("\nResearch fetching completed!")
print("Total unique papers collected:", len(papers))
print("Saved to:", output_file)
