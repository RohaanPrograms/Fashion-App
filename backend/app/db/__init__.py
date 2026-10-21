"""The only code that reads or writes Supabase tables for the API.

Each store takes a client, so tests can hand it a recording fake, and every
per-user query filters by user_id itself (the admin key bypasses Row Level
Security). Endpoints depend on the get_*_store functions, which tests replace
with in-memory fakes.
"""
