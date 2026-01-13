#!/usr/bin/env python3
"""Script to import cards from Anki via AnkiConnect into AnkiRAG."""

import asyncio
import json
import httpx

ANKI_CONNECT_URL = "http://localhost:8765"
BACKEND_URL = "http://localhost:8000/api/v1"

async def anki_request(action: str, params: dict = None) -> dict:
    """Send request to AnkiConnect."""
    payload = {"action": action, "version": 6}
    if params:
        payload["params"] = params

    async with httpx.AsyncClient() as client:
        resp = await client.post(ANKI_CONNECT_URL, json=payload)
        result = resp.json()
        if result.get("error"):
            raise Exception(f"AnkiConnect error: {result['error']}")
        return result["result"]

async def backend_request(method: str, endpoint: str, token: str, data: dict = None) -> dict:
    """Send request to backend API."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        if method == "GET":
            resp = await client.get(f"{BACKEND_URL}{endpoint}", headers=headers)
        else:
            resp = await client.post(f"{BACKEND_URL}{endpoint}", headers=headers, json=data)

        if resp.status_code >= 400:
            print(f"Error {resp.status_code}: {resp.text[:200]}")
            return None
        return resp.json()

async def register_or_login() -> str:
    """Register or login and get token."""
    async with httpx.AsyncClient() as client:
        # Try login first
        resp = await client.post(
            f"{BACKEND_URL}/auth/login",
            json={"email": "anki-import@example.com", "password": "importpassword123"}
        )
        if resp.status_code == 200:
            return resp.json()["access_token"]

        # Register if login failed
        resp = await client.post(
            f"{BACKEND_URL}/auth/register",
            json={
                "email": "anki-import@example.com",
                "password": "importpassword123",
                "display_name": "Anki Importer"
            }
        )
        if resp.status_code == 201:
            return resp.json()["access_token"]

        raise Exception(f"Auth failed: {resp.text}")

async def get_or_create_template(token: str) -> str:
    """Get or create Basic template."""
    # Try to get existing template
    resp = await backend_request("GET", "/templates/", token)
    if resp and resp.get("items"):
        for t in resp["items"]:
            if t["name"].lower() == "basic":
                return t["id"]

    # Create Basic template if not exists
    template_data = {
        "name": "Basic",
        "display_name": "Basic",
        "fields_schema": {
            "type": "object",
            "properties": {
                "Front": {"type": "string"},
                "Back": {"type": "string"}
            },
            "required": ["Front", "Back"]
        },
        "front_template": "<div class='front'>{{Front}}</div>",
        "back_template": "<div class='back'>{{FrontSide}}<hr id='answer'>{{Back}}</div>",
        "css": ".card { font-family: arial; font-size: 20px; text-align: center; }"
    }
    resp = await backend_request("POST", "/templates/", token, template_data)
    if resp:
        return resp["id"]
    return None

async def main():
    print("=== Importing cards from Anki to AnkiRAG ===\n")

    # 1. Get auth token
    print("1. Authenticating...")
    token = await register_or_login()
    print(f"   Token obtained: {token[:20]}...\n")

    # 2. Get template
    print("2. Getting template...")
    template_id = await get_or_create_template(token)
    if not template_id:
        print("   ERROR: Could not get/create template")
        return
    print(f"   Template ID: {template_id}\n")

    # 3. Get decks from Anki
    print("3. Getting decks from Anki...")
    deck_names = await anki_request("deckNames")
    print(f"   Found {len(deck_names)} decks\n")

    # 4. Create decks in AnkiRAG
    print("4. Creating decks in AnkiRAG...")
    deck_map = {}  # anki_name -> ankirag_id

    for deck_name in deck_names:
        if deck_name == "Default" or deck_name == "По умолчанию":
            continue

        # Check if it's a subdeck (contains ::)
        parent_id = None
        if "::" in deck_name:
            parent_name = "::".join(deck_name.split("::")[:-1])
            parent_id = deck_map.get(parent_name)

        deck_data = {
            "name": deck_name.split("::")[-1],  # Last part of name
            "description": f"Imported from Anki: {deck_name}"
        }
        if parent_id:
            deck_data["parent_id"] = parent_id

        resp = await backend_request("POST", "/decks/", token, deck_data)
        if resp:
            deck_map[deck_name] = resp["id"]
            print(f"   Created: {deck_name} -> {resp['id']}")
        else:
            print(f"   Skipped: {deck_name} (may already exist)")

    print(f"\n   Created {len(deck_map)} decks\n")

    # 5. Get all notes from Anki and create cards
    print("5. Importing cards...")
    total_imported = 0
    total_failed = 0

    for deck_name, deck_id in deck_map.items():
        # Get notes for this deck
        note_ids = await anki_request("findNotes", {"query": f'deck:"{deck_name}"'})
        if not note_ids:
            continue

        # Get note info
        notes = await anki_request("notesInfo", {"notes": note_ids[:100]})  # Limit to 100 per deck

        cards_to_create = []
        for note in notes:
            fields = note.get("fields", {})
            # Extract field values
            front = fields.get("Front", {}).get("value", "")
            back = fields.get("Back", {}).get("value", "")

            # Skip if empty
            if not front or not back:
                # Try other field names
                for key in fields:
                    if not front and "front" in key.lower():
                        front = fields[key].get("value", "")
                    elif not back and ("back" in key.lower() or "answer" in key.lower()):
                        back = fields[key].get("value", "")

            if front and back:
                cards_to_create.append({
                    "fields": {"Front": front[:5000], "Back": back[:5000]},  # Limit size
                    "tags": note.get("tags", [])
                })

        if cards_to_create:
            # Bulk create cards
            bulk_data = {
                "deck_id": deck_id,
                "template_id": template_id,
                "cards": cards_to_create
            }
            resp = await backend_request("POST", "/cards/bulk", token, bulk_data)
            if resp:
                created = resp.get("total_created", 0)
                failed = resp.get("total_failed", 0)
                total_imported += created
                total_failed += failed
                print(f"   {deck_name}: {created} cards imported, {failed} failed")
            else:
                total_failed += len(cards_to_create)
                print(f"   {deck_name}: bulk import failed")

    print(f"\n=== Import complete ===")
    print(f"Total imported: {total_imported}")
    print(f"Total failed: {total_failed}")

    # 6. Get user info for RAG operations
    print("\n6. Getting user info...")
    user_resp = await backend_request("GET", "/users/me", token)
    if not user_resp:
        print("   ERROR: Could not get user info")
        return
    user_id = user_resp.get("id")
    print(f"   User ID: {user_id}")

    # 7. Index cards for RAG
    print("\n7. Indexing cards for RAG...")
    index_data = {"user_id": user_id, "force_reindex": False}
    resp = await backend_request("POST", "/rag/index", token, index_data)
    if resp:
        print(f"   Indexed: {resp.get('indexed_count', 0)}")
        print(f"   Skipped: {resp.get('skipped_count', 0)}")
        print(f"   Failed: {resp.get('failed_count', 0)}")
    else:
        print("   Indexing failed or returned no results")

    # 8. Verify RAG search
    print("\n8. Checking RAG search...")
    search_data = {"query": "python programming", "user_id": user_id, "k": 5}
    resp = await backend_request("POST", "/rag/search", token, search_data)
    if resp:
        results = resp.get("results", [])
        print(f"   RAG search found {len(results)} results")
        for r in results[:3]:
            print(f"   - Score {r.get('similarity', 0):.2f}: {r.get('fields', {}).get('Front', '')[:50]}...")
    else:
        print("   RAG search failed or returned no results")

if __name__ == "__main__":
    asyncio.run(main())
