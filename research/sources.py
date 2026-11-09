def get_sources():
    sources = [
        {
            "name": "Europe PMC",
            "url": "https://europepmc.org/",
            "type": "Research Papers",
            "description": "Provides scientific research papers and abstracts."
        },
        {
            "name": "PubMed",
            "url": "https://pubmed.ncbi.nlm.nih.gov/",
            "type": "Medical Research",
            "description": "Provides medical and healthcare research papers."
        },
        {
            "name": "Crossref",
            "url": "https://www.crossref.org/",
            "type": "Research Metadata",
            "description": "Provides research paper details and DOI information."
        }
    ]

    return sources


if __name__ == "__main__":
    for source in get_sources():
        print(source["name"], "-", source["url"])