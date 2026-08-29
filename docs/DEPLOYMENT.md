# Local setup notes

SkillBridge uses SQLite by default. Its complete database is a single local
file at `data/skillbridge.db`, created automatically when `python app.py` is
started for the first time. No cloud database account or SQL migration is
needed.

## Keeping or resetting data

All accounts, applications, programme registrations, announcements, and
collaboration requests are kept in `data/skillbridge.db` on this computer.
Keep that file to retain the demo data you create. To return to a fresh
Ayush-themed demo, stop the app and delete that file; the next launch creates
it again.

## Email delivery

Email is optional. To send real messages through Gmail SMTP, add these values
to a local `.env` file:

```env
SMTP_EMAIL=your-sending-address@example.com
SMTP_PASSWORD=your-gmail-app-password
```

Without both values, registrations, candidate updates, collaboration updates,
and announcements still work in the app. Their email content is printed in the
server console instead of being sent.

## Sharing the demo

For a local hackathon demonstration, run `python app.py` and open
`http://127.0.0.1:5000` in the browser on that computer. SQLite is ideal for
this single-computer setup. A hosted, multi-user version would need a managed
database and a production web server.
