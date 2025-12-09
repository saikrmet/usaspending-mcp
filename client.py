# client.py
import asyncio

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def main() -> None:
    # Connect to the MCP server running on localhost:8000 via streamable HTTP
    transport = StreamableHttpTransport(url="http://localhost:8000/mcp")

    client = Client(transport)

    async with client:
        # Basic connectivity check
        await client.ping()
        print("✅ ping ok")

        # List tools exposed by server
        tools = await client.list_tools()
        print("\n🧰 tools:")
        for t in tools:
            # tool objects are pydantic-like; fall back to dict access if needed
            name = getattr(t, "name", None) or (t.get("name") if isinstance(t, dict) else str(t))
            desc = getattr(t, "description", None) or (t.get("description") if isinstance(t, dict) else "")
            print(f" - {name}: {desc}")

        # Call recipient_autocomplete
        print("\n▶ calling recipient_autocomplete...")
        auto = await client.call_tool(
            "recipient_autocomplete",
            {"search_text": "Holdings", "limit": 5},
        )
        print("recipient_autocomplete result (truncated):", str(auto)[:500])

        # Call spending_by_award (minimal example)
        print("\n▶ calling spending_by_award...")
        sba = await client.call_tool(
            "spending_by_award",
            {
                "subawards": False,
                "limit": 2,
                "page": 1,
                "filters": {
                    "award_type_codes": ["A", "B", "C"],
                    "time_period": [{"start_date": "2018-10-01", "end_date": "2019-09-30"}],
                },
                "fields": ["Award ID", "Recipient Name", "Award Amount"],
                "order": "desc",
                "spending_level": "awards",
            },
        )
        print("spending_by_award result (truncated):", str(sba)[:800])

        # Call recipient_children (use a sample from the docs)
        print("\n▶ calling recipient_children...")
        kids = await client.call_tool(
            "recipient_children",
            {"duns_or_uei": "001006360", "year": "2017"},
        )
        print("recipient_children result (truncated):", str(kids)[:800])

        # Call recipient_list (use a sample agency/year from docs)
        print("\n▶ calling recipient_list...")
        rlist = await client.call_tool(
            "recipient_list",
            {"awarding_agency_id": 183, "fiscal_year": 2017, "limit": 5, "page": 1},
        )
        print("recipient_list result (truncated):", str(rlist)[:800])

    print("\n✅ done")


if __name__ == "__main__":
    asyncio.run(main())
