"""
Design Inspiration MCP Server
==============================
This is the main file that runs our MCP (Model Context Protocol) server.

What is MCP?
    MCP is a protocol that lets AI assistants (like Claude) use external tools.
    Think of it like giving an AI the ability to search the web, query databases,
    or — in our case — fetch design inspiration from the internet.

What does this server do?
    It provides a "tool" called `get_design_inspiration` that searches for
    design-related content using the Serper API (a Google Search API).

How does it work?
    1. An AI assistant connects to this server via the MCP protocol
    2. The assistant can call our tool with a search query
    3. We send that query to the Serper API
    4. We format the results and send them back to the assistant

Key Python concepts used:
    - async/await: For handling network requests without blocking
    - Decorators (@): Special syntax to register functions with the MCP framework
    - Type hints (str, int): Labels that describe what type of data a variable holds
    - Environment variables: Secure way to store sensitive data like API keys
"""

import os
import json
import logging

import httpx
from mcp.server.fastmcp import FastMCP

from config import (
    SERPER_API_KEY,
    SERPER_API_URL,
    DEFAULT_NUM_RESULTS,
    SERVER_NAME,
    SERVER_HOST,
    SERVER_PORT,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(SERVER_NAME)

mcp = FastMCP(SERVER_NAME)


async def search_serper(query: str, num_results: int = DEFAULT_NUM_RESULTS) -> dict:
    """
    Send a search query to the Serper API and return the results.

    Parameters:
        query (str): The search terms to look for (e.g., "minimal website design")
        num_results (int): How many results to return (default from config)

    Returns:
        dict: The JSON response from Serper containing search results

    Raises:
        ValueError: If the SERPER_API_KEY is not configured
        httpx.HTTPStatusError: If the API returns an error status code

    How this function works step-by-step:
        1. Check that we have a valid API key
        2. Build the request headers (including our API key for authentication)
        3. Build the request body (our search query and number of results)
        4. Send a POST request to the Serper API
        5. Check for errors and return the response as a Python dictionary
    """
    if not SERPER_API_KEY:
        raise ValueError(
            "SERPER_API_KEY is not set. "
            "Please add it to your environment variables or .env file. "
            "Get your key at https://serper.dev"
        )

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "q": query,
        "num": num_results,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            SERPER_API_URL,
            headers=headers,
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()


def format_results(raw_results: dict) -> str:
    """
    Convert raw Serper API results into a clean, readable string.

    Parameters:
        raw_results (dict): The JSON response from the Serper API

    Returns:
        str: A formatted string with numbered results

    This function processes three types of results:
        1. Organic search results (regular web pages)
        2. Image results (if available)
        3. "People Also Ask" questions (related queries)
    """
    output_parts = []

    organic = raw_results.get("organic", [])
    if organic:
        output_parts.append("=== Web Results ===\n")
        for i, result in enumerate(organic, start=1):
            title = result.get("title", "No title")
            link = result.get("link", "No link")
            snippet = result.get("snippet", "No description available")
            output_parts.append(
                f"{i}. {title}\n"
                f"   URL: {link}\n"
                f"   Description: {snippet}\n"
            )

    images = raw_results.get("images", [])
    if images:
        output_parts.append("\n=== Image Results ===\n")
        for i, img in enumerate(images, start=1):
            title = img.get("title", "No title")
            link = img.get("link", "No link")
            image_url = img.get("imageUrl", "No image URL")
            output_parts.append(
                f"{i}. {title}\n"
                f"   Page: {link}\n"
                f"   Image: {image_url}\n"
            )

    people_also_ask = raw_results.get("peopleAlsoAsk", [])
    if people_also_ask:
        output_parts.append("\n=== People Also Ask ===\n")
        for i, item in enumerate(people_also_ask, start=1):
            question = item.get("question", "No question")
            snippet = item.get("snippet", "No answer available")
            output_parts.append(f"{i}. Q: {question}\n   A: {snippet}\n")

    if not output_parts:
        return "No results found for your query. Try different search terms."

    return "\n".join(output_parts)


@mcp.tool()
async def get_design_inspiration(
    query: str,
    num_results: int = DEFAULT_NUM_RESULTS,
) -> str:
    """
    Search for design inspiration based on your query.

    This tool fetches design-related search results from the web using the
    Serper API. Use it to find inspiration for UI/UX design, graphic design,
    web design, branding, typography, color palettes, and more.

    Args:
        query: What kind of design inspiration you're looking for.
               Examples: "modern dashboard UI design", "minimalist logo ideas",
               "color palette for nature app"
        num_results: Number of results to return (1-20, default 10)

    Returns:
        Formatted search results with titles, URLs, and descriptions.
    """
    logger.info("Searching for design inspiration: '%s' (num_results=%d)", query, num_results)

    num_results = max(1, min(20, num_results))

    design_query = f"{query} design inspiration"

    try:
        raw_results = await search_serper(design_query, num_results)
        formatted = format_results(raw_results)
        logger.info("Successfully fetched %d results", len(raw_results.get("organic", [])))
        return formatted

    except ValueError as e:
        logger.error("Configuration error: %s", e)
        return f"Configuration Error: {e}"

    except httpx.HTTPStatusError as e:
        logger.error("Serper API error: %s", e)
        return f"API Error: The Serper API returned status {e.response.status_code}. Please check your API key."

    except httpx.RequestError as e:
        logger.error("Network error: %s", e)
        return f"Network Error: Could not connect to the Serper API. Details: {e}"

    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return f"Unexpected Error: {e}"


@mcp.tool()
async def search_design_images(
    query: str,
    num_results: int = DEFAULT_NUM_RESULTS,
) -> str:
    """
    Search specifically for design-related images.

    This tool is optimized for finding visual design references and
    inspiration images. It uses Serper's image search endpoint.

    Args:
        query: What kind of design images you're looking for.
               Examples: "flat illustration style", "dark mode UI screenshots",
               "watercolor texture backgrounds"
        num_results: Number of image results to return (1-20, default 10)

    Returns:
        Formatted image results with titles and URLs.
    """
    logger.info("Searching for design images: '%s' (num_results=%d)", query, num_results)

    num_results = max(1, min(20, num_results))

    if not SERPER_API_KEY:
        return (
            "Configuration Error: SERPER_API_KEY is not set. "
            "Please add it to your environment variables or .env file."
        )

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "q": f"{query} design",
        "num": num_results,
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://google.serper.dev/images",
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

        images = data.get("images", [])
        if not images:
            return "No image results found. Try different search terms."

        output_parts = [f"=== Design Image Results for '{query}' ===\n"]
        for i, img in enumerate(images, start=1):
            title = img.get("title", "No title")
            link = img.get("link", "No link")
            image_url = img.get("imageUrl", "No image URL")
            source = img.get("source", "Unknown source")
            output_parts.append(
                f"{i}. {title}\n"
                f"   Source: {source}\n"
                f"   Page: {link}\n"
                f"   Image: {image_url}\n"
            )

        return "\n".join(output_parts)

    except httpx.HTTPStatusError as e:
        logger.error("Serper API error: %s", e)
        return f"API Error: The Serper API returned status {e.response.status_code}."

    except httpx.RequestError as e:
        logger.error("Network error: %s", e)
        return f"Network Error: Could not connect to the Serper API. Details: {e}"

    except Exception as e:
        logger.error("Unexpected error: %s", e)
        return f"Unexpected Error: {e}"


if __name__ == "__main__":
    logger.info("Starting %s on %s:%d", SERVER_NAME, SERVER_HOST, SERVER_PORT)
    logger.info("Transport: SSE (Server-Sent Events)")
    logger.info("Connect your MCP client to http://%s:%d/sse", SERVER_HOST, SERVER_PORT)

    mcp.settings.host = SERVER_HOST
    mcp.settings.port = SERVER_PORT
    mcp.run(transport="sse")
