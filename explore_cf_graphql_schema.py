#!/usr/bin/env python3
"""
explore_cf_graphql_schema.py

Interactively discover and list all the fields of any Cloudflare Analytics
GraphQL type ending in "Adaptive" by performing GraphQL introspection.

Credentials are read from cf_env.ini in the same directory.
"""

import requests
import sys
import os
import configparser

# ———————————————————————————————
# Load credentials from cf_env.ini
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "cf_env.ini")
config = configparser.ConfigParser()
if not os.path.isfile(CONFIG_FILE):
    print(f"[ERROR] Missing config file: {CONFIG_FILE}", file=sys.stderr)
    sys.exit(1)
config.read(CONFIG_FILE)

if "cloudflare" not in config:
    print("[ERROR] cf_env.ini must contain a [cloudflare] section", file=sys.stderr)
    sys.exit(1)

EMAIL   = config["cloudflare"].get("email")
API_KEY = config["cloudflare"].get("api_key")
GRAPHQL_ENDPOINT = config["cloudflare"].get(
    "graphql_endpoint",
    "https://api.cloudflare.com/client/v4/graphql"
)

if not EMAIL or not API_KEY:
    print("[ERROR] cf_env.ini must define email and api_key under [cloudflare]", file=sys.stderr)
    sys.exit(1)
# ———————————————————————————————

# 1) Introspect all types
INTROSPECT_ALL_TYPES = """
query {
  __schema {
    types {
      name
    }
  }
}
"""

# 2) Introspect a specific type’s fields
INTROSPECT_TYPE = """
query IntrospectType($typeName: String!) {
  __type(name: $typeName) {
    name
    kind
    description
    fields {
      name
      description
      type {
        kind
        name
        ofType {
          kind
          name
          ofType {
            kind
            name
          }
        }
      }
    }
  }
}
"""

def fetch_graphql(query: str, variables: dict = None) -> dict:
    """Send a GraphQL query and return the 'data' key from the response."""
    headers = {
        "X-Auth-Email": EMAIL,
        "X-Auth-Key":   API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    r = requests.post(GRAPHQL_ENDPOINT, headers=headers, json=payload)
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise Exception(body["errors"])
    return body["data"]

def render_type(t: dict) -> str:
    """Recursively render GraphQL type signatures (handles NON_NULL, LIST)."""
    kind = t["kind"]
    name = t.get("name")
    of = t.get("ofType")
    if kind == "NON_NULL" and of:
        return render_type(of) + "!"
    if kind == "LIST" and of:
        return "[" + render_type(of) + "]"
    return name or kind

def main():
    # Fetch all type names
    try:
        data = fetch_graphql(INTROSPECT_ALL_TYPES)
    except Exception as e:
        print(f"[ERROR] Schema introspection failed: {e}", file=sys.stderr)
        sys.exit(1)

    all_types = [t["name"] for t in data["__schema"]["types"]]
    # Filter for types ending in 'Adaptive'
    adaptive_types = sorted([n for n in all_types if n.endswith("Adaptive")])
    if not adaptive_types:
        print("No types ending with 'Adaptive' were found in the schema.", file=sys.stderr)
        sys.exit(1)

    # Present a menu
    print("Available Analytics types:")
    for idx, name in enumerate(adaptive_types, start=1):
        print(f"  {idx}. {name}")
    choice = input("Enter the number of the type to explore: ").strip()
    if not choice.isdigit() or not (1 <= int(choice) <= len(adaptive_types)):
        print("Invalid selection.", file=sys.stderr)
        sys.exit(1)

    selected_type = adaptive_types[int(choice) - 1]
    print(f"\nInspecting type: {selected_type}\n")

    # Introspect the chosen type
    try:
        type_data = fetch_graphql(INTROSPECT_TYPE, {"typeName": selected_type})
    except Exception as e:
        print(f"[ERROR] Could not introspect {selected_type}: {e}", file=sys.stderr)
        sys.exit(1)

    t = type_data["__type"]
    print(f"Type: {t['name']}   (kind: {t['kind']})")
    if t.get("description"):
        print(f"Description: {t['description']}\n")

    # Print fields
    print(f"{'Field':<30} {'Type':<30} Description")
    print("-" * 80)
    for fld in t.get("fields", []):
        name = fld["name"]
        ftype = render_type(fld["type"])
        desc = fld.get("description", "") or ""
        print(f"{name:<30} {ftype:<30} {desc}")

if __name__ == "__main__":
    main()
