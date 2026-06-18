-- ============================================
-- ContractAI — Supabase Schema
-- Run this in your Supabase SQL editor
-- ============================================

-- Reviews table (core)
create table if not exists reviews (
  id                uuid primary key default gen_random_uuid(),
  user_id           uuid references auth.users not null,
  filename          text not null,
  storage_path      text,
  word_count        int,
  overall_risk      text check (overall_risk in ('low', 'medium', 'high')),
  contract_type     text,
  flag_count_red    int default 0,
  flag_count_amber  int default 0,
  flag_count_total  int default 0,
  result            jsonb,          -- full AI output
  created_at        timestamptz default now()
);

-- Subscriptions table
create table if not exists subscriptions (
  id                      uuid primary key default gen_random_uuid(),
  user_id                 uuid references auth.users not null unique,
  stripe_subscription_id  text unique,
  stripe_customer_id      text,
  plan                    text default 'free',
  status                  text default 'active',
  created_at              timestamptz default now(),
  updated_at              timestamptz default now()
);

-- Row-level security: users can only see their own data
alter table reviews enable row level security;
alter table subscriptions enable row level security;

create policy "Users see own reviews"
  on reviews for all
  using (auth.uid() = user_id);

create policy "Users see own subscription"
  on subscriptions for all
  using (auth.uid() = user_id);

-- Storage bucket for contract files
insert into storage.buckets (id, name, public)
values ('contracts', 'contracts', false)
on conflict do nothing;

-- Storage policy: users can only access their own folder
create policy "Users access own contracts"
  on storage.objects for all
  using (
    bucket_id = 'contracts'
    and auth.uid()::text = (storage.foldername(name))[1]
  );

-- Index for fast lookups
create index if not exists reviews_user_id_idx on reviews(user_id);
create index if not exists reviews_created_at_idx on reviews(created_at desc);
create index if not exists subscriptions_user_id_idx on subscriptions(user_id);
