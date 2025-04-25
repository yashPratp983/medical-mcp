from typing import Any, List, Optional
import httpx
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server with working directory
mcp = FastMCP("opentargets-mcp")

# Constants
API_BASE_URL = "https://api.platform.opentargets.org/api/v4"
TOOL_NAME = "opentargets-mcp"

async def make_api_request(endpoint: str, params: dict = None) -> Any:
    """Make a request to the Open Targets API with proper error handling."""
    url = f"{API_BASE_URL}/{endpoint}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

@mcp.tool()
async def search_targets(query: str, max_results: int = 10) -> str:
    """Search Open Targets for gene targets matching the query.
    
    Args:
        query: Search query for target names or symbols
        max_results: Maximum number of results to return (default: 10)
    """
    params = {
        "q": query,
        "size": max_results
    }
    
    results = await make_api_request("search", params)
    
    if isinstance(results, dict) and "error" in results:
        return f"Error searching Open Targets: {results['error']}"
    
    targets = [item for item in results.get("data", []) 
              if item.get("entity") == "target"][:max_results]
    
    if not targets:
        return "No targets found for your query."
    
    formatted_results = []
    for target in targets:
        target_id = target.get("id", "Unknown ID")
        name = target.get("name", "No name")
        symbol = target.get("approved_symbol", "Unknown symbol")
        
        formatted_results.append(
            f"Symbol: {symbol}\n"
            f"Name: {name}\n"
            f"Target ID: {target_id}"
        )
    
    return "\n\n---\n\n".join(formatted_results)

@mcp.tool()
async def get_target_details(target_id: str) -> str:
    """Get detailed information about a specific target by ID.
    
    Args:
        target_id: Open Targets ID for the target (e.g., "ENSG00000157764")
    """
    results = await make_api_request(f"target/{target_id}")
    
    if isinstance(results, dict) and "error" in results:
        return f"Error retrieving target details: {results['error']}"
    
    if not results:
        return f"No target found with ID: {target_id}"
    
    target = results
    name = target.get("approvedName", "No name")
    symbol = target.get("approvedSymbol", "Unknown symbol")
    biotype = target.get("biotype", "Unknown biotype")
    functions = "\n  - ".join([f.get("label", "") for f in target.get("functionDescriptions", [])])
    genomic_location = target.get("genomicLocation", {})
    
    formatted_details = (
        f"Symbol: {symbol}\n"
        f"Name: {name}\n"
        f"Target ID: {target_id}\n"
        f"Biotype: {biotype}\n"
        f"Chromosome: {genomic_location.get('chromosome', 'Unknown')}\n"
        f"Gene Function:\n  - {functions or 'Not available'}"
    )
    
    return formatted_details

@mcp.tool()
async def search_diseases(query: str, max_results: int = 10) -> str:
    """Search for diseases in Open Targets.
    
    Args:
        query: Search query for disease names
        max_results: Maximum number of results to return (default: 10)
    """
    params = {
        "q": query,
        "size": max_results
    }
    
    results = await make_api_request("search", params)
    
    if isinstance(results, dict) and "error" in results:
        return f"Error searching diseases: {results['error']}"
    
    diseases = [item for item in results.get("data", []) 
               if item.get("entity") == "disease"][:max_results]
    
    if not diseases:
        return "No diseases found for your query."
    
    formatted_results = []
    for disease in diseases:
        disease_id = disease.get("id", "Unknown ID")
        name = disease.get("name", "No name")
        
        formatted_results.append(
            f"Disease: {name}\n"
            f"Disease ID: {disease_id}"
        )
    
    return "\n\n---\n\n".join(formatted_results)

@mcp.tool()
async def get_target_associated_diseases(target_id: str, max_results: int = 10) -> str:
    """Get diseases associated with a specific target.
    
    Args:
        target_id: Open Targets ID for the target (e.g., "ENSG00000157764")
        max_results: Maximum number of results to return (default: 10)
    """
    params = {
        "target": target_id,
        "size": max_results
    }
    
    results = await make_api_request("association/filter", params)
    
    if isinstance(results, dict) and "error" in results:
        return f"Error retrieving associated diseases: {results['error']}"
    
    associations = results.get("data", [])
    if not associations:
        return f"No diseases associated with target ID: {target_id}"
    
    formatted_results = []
    for assoc in associations:
        disease = assoc.get("disease", {})
        disease_id = disease.get("id", "Unknown ID")
        name = disease.get("name", "No name")
        score = assoc.get("score", 0)
        
        formatted_results.append(
            f"Disease: {name}\n"
            f"Disease ID: {disease_id}\n"
            f"Association Score: {score:.3f}"
        )
    
    return "\n\n---\n\n".join(formatted_results)

@mcp.tool()
async def get_disease_associated_targets(disease_id: str, max_results: int = 10) -> str:
    """Get targets associated with a specific disease.
    
    Args:
        disease_id: Open Targets disease ID
        max_results: Maximum number of results to return (default: 10)
    """
    params = {
        "disease": disease_id,
        "size": max_results
    }
    
    results = await make_api_request("association/filter", params)
    
    if isinstance(results, dict) and "error" in results:
        return f"Error retrieving associated targets: {results['error']}"
    
    associations = results.get("data", [])
    if not associations:
        return f"No targets associated with disease ID: {disease_id}"
    
    formatted_results = []
    for assoc in associations:
        target = assoc.get("target", {})
        target_id = target.get("id", "Unknown ID")
        symbol = target.get("approvedSymbol", "Unknown symbol")
        name = target.get("approvedName", "No name")
        score = assoc.get("score", 0)
        
        formatted_results.append(
            f"Symbol: {symbol}\n"
            f"Name: {name}\n"
            f"Target ID: {target_id}\n"
            f"Association Score: {score:.3f}"
        )
    
    return "\n\n---\n\n".join(formatted_results)

@mcp.tool()
async def search_drugs(query: str, max_results: int = 10) -> str:
    """Search for drugs in Open Targets.
    
    Args:
        query: Search query for drug names
        max_results: Maximum number of results to return (default: 10)
    """
    params = {
        "q": query,
        "size": max_results
    }
    
    results = await make_api_request("search", params)
    
    if isinstance(results, dict) and "error" in results:
        return f"Error searching drugs: {results['error']}"
    
    drugs = [item for item in results.get("data", []) 
            if item.get("entity") == "drug"][:max_results]
    
    if not drugs:
        return "No drugs found for your query."
    
    formatted_results = []
    for drug in drugs:
        drug_id = drug.get("id", "Unknown ID")
        name = drug.get("name", "No name")
        
        formatted_results.append(
            f"Drug: {name}\n"
            f"Drug ID: {drug_id}"
        )
    
    return "\n\n---\n\n".join(formatted_results)

if __name__ == "__main__":
    mcp.run(transport='stdio') 