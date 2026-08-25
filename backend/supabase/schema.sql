-- =====================================================================
--  Fashion App — database schema
-- =====================================================================
--
--  HOW TO RUN THIS
--  ---------------
--  Supabase dashboard -> SQL Editor -> New query -> paste this whole file
--  -> Run. It is safe to run more than once: every statement either uses
--  "if not exists" or drops-then-recreates, so re-running brings the
--  database up to date rather than erroring or duplicating anything.
--
--  WHY THIS FILE EXISTS
--  --------------------
--  This is the single source of truth for the database structure. Creating
--  tables by clicking around the dashboard leaves no record of what was
--  done; this file can be re-run to rebuild the database from scratch, or
--  to set up a second one for staging.
--
--  A NOTE ON ROW LEVEL SECURITY (RLS)
--  ----------------------------------
--  The mobile app carries the Supabase "anon key", which ships inside the
--  app on every user's phone and is trivially extractable. It is not a
--  secret. The only thing standing between that key and every user's data
--  is RLS: per-table rules, enforced by the database itself, deciding who
--  may see which rows. Every table below has RLS enabled.
--
--  The backend's service role key bypasses RLS entirely — that is why it
--  must never leave the server.
-- =====================================================================


-- gen_random_uuid(), used for primary keys below.
create extension if not exists pgcrypto;


-- =====================================================================
--  Shared helper: keep updated_at honest
-- =====================================================================
-- A trigger function that stamps updated_at on every UPDATE, so we can't
-- forget to set it in application code.
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;


-- =====================================================================
--  users — profile rows for the accounts Supabase Auth manages
-- =====================================================================
-- Supabase owns auth.users (emails, passwords, confirmation state) and we
-- must not modify it. This table holds OUR fields and points at it, so
-- deleting an account cleans up everything downstream via "on delete cascade".
create table if not exists public.users (
  id uuid primary key references auth.users (id) on delete cascade,
  email text,

  -- ---- Onboarding quiz answers ----
  -- Screen 1: what the user shops for. Applied as a catalogue filter.
  gender_preference text check (gender_preference in ('womens', 'mens', 'both')),
  -- Screen 2: usual spend per item. Seeds the default budget filter.
  budget_min numeric(10, 2) check (budget_min >= 0),
  budget_max numeric(10, 2) check (budget_max >= 0),
  -- Screen 3: aesthetic tiles the user picked, as cluster ids ('A'..'I').
  -- An array because the quiz is multi-select (users pick 2-4).
  style_clusters text[] not null default '{}',
  onboarding_complete boolean not null default false,

  -- Set in Phase 3, once we build a style vector from interaction history.
  style_vector_pinecone_id text,

  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),

  -- A max below the min would silently break every budget filter.
  constraint budget_range_valid check (
    budget_min is null or budget_max is null or budget_min <= budget_max
  )
);

drop trigger if exists users_touch_updated_at on public.users;
create trigger users_touch_updated_at
  before update on public.users
  for each row execute function public.touch_updated_at();


-- Create the profile row automatically the moment an account is created,
-- so a user can never exist without one.
--
-- "security definer" lets this run with the privileges of its owner, which
-- it needs because the signing-up user has no rights on public.users yet.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
begin
  insert into public.users (id, email)
  values (new.id, new.email)
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Backfill: give any account that already existed before this file was run
-- (e.g. accounts made while testing auth) its missing profile row.
insert into public.users (id, email)
select id, email from auth.users
on conflict (id) do nothing;


-- =====================================================================
--  products — the clothing catalogue
-- =====================================================================
create table if not exists public.products (
  id uuid primary key default gen_random_uuid(),

  -- Where this came from: 'asos', 'farfetch', 'etsy', ...
  source text not null,
  -- The id the retailer uses. Together with source this identifies a
  -- product uniquely, which is what makes the daily re-sync an idempotent
  -- "upsert" instead of creating duplicates every night.
  source_id text not null,

  name text not null,
  brand text,
  url text not null,                    -- affiliate deep link
  price numeric(10, 2) check (price >= 0),
  currency text not null default 'GBP',

  -- Link to the retailer's image. We deliberately do not copy product
  -- images into our own storage: it would burn the free tier and add
  -- bandwidth cost for no benefit.
  image_url text,

  -- Flagged rather than deleted when out of stock, so trend analysis keeps
  -- its history, which is what keeps catalogue freshness measurable.
  in_stock boolean not null default true,
  category text,

  -- Flexible bag of attributes: { colour, fit, occasion, material }.
  -- jsonb rather than columns because the auto-tagger's output will keep
  -- changing shape as it improves.
  attributes jsonb not null default '{}'::jsonb,

  -- Phase 1: the matching vector in Pinecone.
  pinecone_id text,
  -- Which model produced that vector. Mixing vectors from different models
  -- silently returns nonsense results, so we
  -- record the version and re-embed the catalogue when the model changes.
  embedding_model_version text,

  created_at timestamptz not null default now(),
  last_synced_at timestamptz not null default now(),

  unique (source, source_id)
);

-- Indexes matching how the feed and search actually query this table.
-- Without them Postgres reads every row; fine at 500 products, not at 500k.
create index if not exists products_category_idx on public.products (category);
create index if not exists products_price_idx on public.products (price);
create index if not exists products_in_stock_idx on public.products (in_stock) where in_stock;
create index if not exists products_pinecone_id_idx on public.products (pinecone_id);
-- GIN is the index type for searching inside jsonb, e.g. attributes->>'colour'.
create index if not exists products_attributes_idx on public.products using gin (attributes);


-- =====================================================================
--  interactions — every swipe, like, and dwell time
-- =====================================================================
-- The highest-write table in the system and the fuel for the entire
-- recommendation engine. Everything in Phase 3 is computed from this.
create table if not exists public.interactions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  product_id uuid not null references public.products (id) on delete cascade,

  type text not null check (
    type in ('like', 'dislike', 'wishlist', 'cart', 'view', 'skip')
  ),

  -- Milliseconds spent looking at the item before acting. Capped at 60s
  -- because anything longer means the user put their phone down, not that
  -- they were fascinated.
  dwell_time_ms integer check (dwell_time_ms >= 0 and dwell_time_ms <= 60000),

  source text not null check (source in ('feed', 'search', 'similar')),
  created_at timestamptz not null default now()
);

-- "This user's recent activity" — the style-vector build in Phase 3.
create index if not exists interactions_user_created_idx
  on public.interactions (user_id, created_at desc);
-- "Has this user already seen this product?" — feed de-duplication, run
-- on every single feed request, so it must be fast.
create index if not exists interactions_user_product_idx
  on public.interactions (user_id, product_id);
-- "What is trending?" — most-liked items over the last 7 days, which is
-- what a brand new user's first feed is built from.
create index if not exists interactions_product_created_idx
  on public.interactions (product_id, created_at desc);


-- =====================================================================
--  wishlist_items / cart_items
-- =====================================================================
-- The unique constraint makes saving the same item twice a no-op at the
-- database level, so a double-tap can't create duplicate rows.
create table if not exists public.wishlist_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  product_id uuid not null references public.products (id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (user_id, product_id)
);

create table if not exists public.cart_items (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.users (id) on delete cascade,
  product_id uuid not null references public.products (id) on delete cascade,
  created_at timestamptz not null default now(),
  unique (user_id, product_id)
);

create index if not exists wishlist_user_idx on public.wishlist_items (user_id);
create index if not exists cart_user_idx on public.cart_items (user_id);


-- =====================================================================
--  Row Level Security
-- =====================================================================
-- Enabling RLS switches a table from "anyone with the anon key reads
-- everything" to "nothing is readable until a policy says so".
alter table public.users          enable row level security;
alter table public.products       enable row level security;
alter table public.interactions   enable row level security;
alter table public.wishlist_items enable row level security;
alter table public.cart_items     enable row level security;

-- auth.uid() is the id of whoever's token accompanied the request. It is
-- set by Supabase from the verified JWT and cannot be spoofed by the client.

-- ---- users: you may only ever touch your own profile row ----
drop policy if exists users_select_own on public.users;
create policy users_select_own on public.users
  for select to authenticated using (auth.uid() = id);

drop policy if exists users_update_own on public.users;
create policy users_update_own on public.users
  for update to authenticated using (auth.uid() = id) with check (auth.uid() = id);

-- Normally the signup trigger creates this row; this policy is the fallback.
drop policy if exists users_insert_own on public.users;
create policy users_insert_own on public.users
  for insert to authenticated with check (auth.uid() = id);

-- ---- products: shared catalogue, readable by any signed-in user ----
-- No insert/update/delete policy on purpose. Only the backend writes here,
-- using the service role key, which bypasses RLS.
drop policy if exists products_select_all on public.products;
create policy products_select_all on public.products
  for select to authenticated using (true);

-- ---- interactions: your own history, nobody else's ----
drop policy if exists interactions_select_own on public.interactions;
create policy interactions_select_own on public.interactions
  for select to authenticated using (auth.uid() = user_id);

-- "with check" validates rows being written: you cannot log a swipe under
-- someone else's user_id.
drop policy if exists interactions_insert_own on public.interactions;
create policy interactions_insert_own on public.interactions
  for insert to authenticated with check (auth.uid() = user_id);

-- ---- wishlist: read/add/remove your own ----
drop policy if exists wishlist_select_own on public.wishlist_items;
create policy wishlist_select_own on public.wishlist_items
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists wishlist_insert_own on public.wishlist_items;
create policy wishlist_insert_own on public.wishlist_items
  for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists wishlist_delete_own on public.wishlist_items;
create policy wishlist_delete_own on public.wishlist_items
  for delete to authenticated using (auth.uid() = user_id);

-- ---- cart: same shape as wishlist ----
drop policy if exists cart_select_own on public.cart_items;
create policy cart_select_own on public.cart_items
  for select to authenticated using (auth.uid() = user_id);

drop policy if exists cart_insert_own on public.cart_items;
create policy cart_insert_own on public.cart_items
  for insert to authenticated with check (auth.uid() = user_id);

drop policy if exists cart_delete_own on public.cart_items;
create policy cart_delete_own on public.cart_items
  for delete to authenticated using (auth.uid() = user_id);


-- =====================================================================
--  Storage: the user-uploads bucket
-- =====================================================================
-- Holds photos users upload for visual search (Phase 2) and, later,
-- full-body photos for virtual try-on (Phase 5).
--
-- public = false is deliberate and important. In a public bucket, anyone
-- holding the URL can view the file. These are photographs of users.
insert into storage.buckets (id, name, public)
values ('user-uploads', 'user-uploads', false)
on conflict (id) do nothing;

-- Files are stored as "<user-id>/<filename>", so the first path segment
-- says who owns the file. These policies compare that segment to the
-- caller's id: you can only reach your own folder.
drop policy if exists user_uploads_select_own on storage.objects;
create policy user_uploads_select_own on storage.objects
  for select to authenticated
  using (
    bucket_id = 'user-uploads'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists user_uploads_insert_own on storage.objects;
create policy user_uploads_insert_own on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'user-uploads'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- Users must be able to delete their own photos: required for the
-- try-on consent flow and for GDPR deletion requests (risks 15 and 16).
drop policy if exists user_uploads_delete_own on storage.objects;
create policy user_uploads_delete_own on storage.objects
  for delete to authenticated
  using (
    bucket_id = 'user-uploads'
    and (storage.foldername(name))[1] = auth.uid()::text
  );
