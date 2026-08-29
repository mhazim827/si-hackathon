# Deployment and database notes

## Supabase setup

Create a Supabase project and copy its PostgreSQL connection string into `DATABASE_URL` in your local `.env` file. Run the SQL files in this order:

1. `supabase_schema.sql`
2. `supabase_learning_programs_migration.sql`
3. `supabase_announcements_migration.sql`

Run them using Supabase Dashboard → SQL Editor. Do not paste credentials into source files or commit `.env`.

## Duplicate email migration error

The learning-programme migration creates a case-insensitive unique index for account email addresses. If an older database contains duplicate emails, find them with:

```sql
select lower(email) as email, array_agg(id) as account_ids
from public.accounts
where email is not null and email <> ''
group by lower(email)
having count(*) > 1;
```

Choose which account should retain the address, change the other account to its real unique email, then rerun the migration:

```sql
update public.accounts
set email = 'different-email@example.com'
where id = REPLACE_WITH_THE_DUPLICATE_ACCOUNT_ID;
```

## Email delivery

The app sends email through Gmail SMTP over SSL. Use an app password rather than a normal Gmail password. Set `SMTP_EMAIL` and `SMTP_PASSWORD` in `.env`; omit either one to keep email output local to the server console.

## Production checklist

- Set a strong, unique `SKILLBRIDGE_SECRET_KEY`.
- Use a production WSGI server and HTTPS rather than Flask’s built-in server.
- Restrict Supabase database access to trusted application credentials.
- Back up database data and monitor SMTP delivery failures.
- Add a privacy notice and a data-retention policy before handling real student records.
