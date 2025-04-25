from typing import Any, List, Optional
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server with working directory
mcp = FastMCP("drugbank-mcp")

# Constants
API_BASE_URL = "https://api.drugbank.com/v1"
TOOL_NAME = "drugbank-mcp"
API_KEY = ""  # Replace with your DrugBank API key

async def make_api_request(endpoint: str, params: dict = None) -> Any:
    """Make a request to the DrugBank API with proper error handling."""
    url = f"{API_BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {API_KEY}"}
    
    if not API_KEY:
        return {"error": "DrugBank API key not configured. Please set API_KEY in the script."}
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, headers=headers, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

@mcp.tool()
async def search_drugs(query: str, max_results: int = 10) -> str:
    """Search DrugBank for drugs matching the query.
    
    Args:
        query: Search query for drug names
        max_results: Maximum number of results to return (default: 10)
    """
    params = {
        "q": query,
        "limit": max_results
    }
    
    results = await make_api_request("drugs", params)
    
    if isinstance(results, dict) and "error" in results:
        return f"Error searching DrugBank: {results['error']}"
    
    drugs = results.get("data", [])
    if not drugs:
        return "No drugs found for your query."
    
    formatted_results = []
    for drug in drugs:
        drug_id = drug.get("id", "Unknown ID")
        name = drug.get("name", "No name")
        synonyms = ", ".join(drug.get("synonyms", []))[:100] + ("..." if len(", ".join(drug.get("synonyms", []))) > 100 else "")
        cas_number = drug.get("cas_number", "Not available")
        
        formatted_results.append(
            f"Name: {name}\n"
            f"DrugBank ID: {drug_id}\n"
            f"CAS Number: {cas_number}\n"
            f"Synonyms: {synonyms or 'None listed'}"
        )
    
    if not formatted_results:
        return "No drug details could be retrieved."
        
    return "\n\n---\n\n".join(formatted_results)

@mcp.tool()
async def get_drug_details(drug_id: str) -> str:
    """Get detailed information about a specific drug by its DrugBank ID.
    
    Args:
        drug_id: DrugBank ID of the drug (e.g., "DB00001")
    """
    results = await make_api_request(f"drugs/{drug_id}")
    
    if isinstance(results, dict) and "error" in results:
        return f"Error retrieving drug details: {results['error']}"
    
    drug = results.get("data", {})
    if not drug:
        return f"No drug found with ID: {drug_id}"
    
    name = drug.get("name", "No name")
    description = drug.get("description", "No description available")
    cas_number = drug.get("cas_number", "Not available")
    groups = ", ".join(drug.get("groups", []))
    indication = drug.get("indication", "Not available")
    mechanism_of_action = drug.get("mechanism_of_action", "Not available")
    
    formatted_details = (
        f"Name: {name}\n\n"
        f"DrugBank ID: {drug_id}\n\n"
        f"CAS Number: {cas_number}\n\n"
        f"Groups: {groups or 'None listed'}\n\n"
        f"Indication: {indication}\n\n"
        f"Mechanism of Action: {mechanism_of_action}\n\n"
        f"Description: {description[:500]}..." if len(description) > 500 else f"Description: {description}"
    )
    
    return formatted_details

@mcp.tool()
async def find_drugs_by_indication(indication: str, max_results: int = 10) -> str:
    """Search for drugs used to treat a specific medical condition.
    
    Args:
        indication: Medical condition or disease
        max_results: Maximum number of results to return (default: 10)
    """
    params = {
        "q": f"indication:{indication}",
        "limit": max_results
    }
    
    results = await make_api_request("drugs", params)
    
    if isinstance(results, dict) and "error" in results:
        return f"Error searching by indication: {results['error']}"
    
    return await format_drug_results(results)

@mcp.tool()
async def find_drugs_by_category(category: str, max_results: int = 10) -> str:
    """Search for drugs in a specific category.
    
    Args:
        category: Drug category (e.g., "antibiotic", "antidepressant")
        max_results: Maximum number of results to return (default: 10)
    """
    params = {
        "q": f"category:{category}",
        "limit": max_results
    }
    
    results = await make_api_request("drugs", params)
    
    if isinstance(results, dict) and "error" in results:
        return f"Error searching by category: {results['error']}"
    
    return await format_drug_results(results)

@mcp.tool()
async def get_drug_interactions(drug_id: str, max_results: int = 10) -> str:
    """Get drug interactions for a specific drug.
    
    Args:
        drug_id: DrugBank ID of the drug (e.g., "DB00001")
        max_results: Maximum number of interactions to return (default: 10)
    """
    results = await make_api_request(f"drugs/{drug_id}/interactions")
    
    if isinstance(results, dict) and "error" in results:
        return f"Error retrieving drug interactions: {results['error']}"
    
    interactions = results.get("data", [])[:max_results]
    if not interactions:
        return f"No interactions found for drug with ID: {drug_id}"
    
    formatted_results = []
    for interaction in interactions:
        interacting_drug = interaction.get("interacting_drug", {})
        interacting_name = interacting_drug.get("name", "Unknown drug")
        interacting_id = interacting_drug.get("id", "Unknown ID")
        description = interaction.get("description", "No description available")
        
        formatted_results.append(
            f"Interacting Drug: {interacting_name} ({interacting_id})\n"
            f"Description: {description[:200]}..." if len(description) > 200 else f"Description: {description}"
        )
    
    if not formatted_results:
        return "No interaction details could be retrieved."
        
    return "\n\n---\n\n".join(formatted_results)

async def format_drug_results(results: dict) -> str:
    """Helper function to format drug search results."""
    drugs = results.get("data", [])
    if not drugs:
        return "No drugs found for your query."
    
    formatted_results = []
    for drug in drugs:
        drug_id = drug.get("id", "Unknown ID")
        name = drug.get("name", "No name")
        cas_number = drug.get("cas_number", "Not available")
        groups = ", ".join(drug.get("groups", []))
        
        formatted_results.append(
            f"Name: {name}\n"
            f"DrugBank ID: {drug_id}\n"
            f"CAS Number: {cas_number}\n"
            f"Groups: {groups or 'None listed'}"
        )
    
    if not formatted_results:
        return "No drug details could be retrieved."
        
    return "\n\n---\n\n".join(formatted_results)

if __name__ == "__main__":
    mcp.run(transport='stdio')