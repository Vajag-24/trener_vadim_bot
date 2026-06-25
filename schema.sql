-- ТРЕНЕР-БОТ — схема Supabase
-- Запусти один раз в Supabase → SQL Editor

create table if not exists players (
    user_id       bigint primary key,
    stamina       int     not null default 5,
    stamina_date  date    not null default current_date,
    streak        int     not null default 0,
    best_streak   int     not null default 0,
    xp            int     not null default 0,
    rank_idx      int     not null default 0,
    total_days    int     not null default 0,
    last_active   date,
    last_suit     text,
    equipment     text    not null default 'floor,bar,dips,db',
    energy_today  text,                          -- high | normal | low | null
    created_at    timestamptz default now()
);

create table if not exists prs (
    user_id   bigint not null,
    pattern   text   not null,
    pr        int    not null default 0,
    easy_run  int    not null default 0,
    primary key (user_id, pattern)
);

create table if not exists logs (
    id        bigserial primary key,
    user_id   bigint not null,
    pattern   text   not null,
    reps      int    not null,
    effort    text   not null default 'normal',
    ts        timestamptz default now()
);

create index if not exists logs_user_ts on logs(user_id, ts desc);
create index if not exists logs_user_pattern on logs(user_id, pattern);
