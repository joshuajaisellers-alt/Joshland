# Correspondence Tracker

A lightweight, standalone correspondence tracker that logs letters, emails, and other interactions, keeps follow-up reminders, and surfaces relationship insights from the command line.

## Features

* **Contact management** – maintain a directory of the people you write to, including notes on preferred channels.
* **Correspondence logging** – capture structured metadata, free-form text, or attachment references for every message.
* **Reminders** – see pending follow-ups and overdue replies using simple heuristics.
* **Insights** – summarize relationship health with counts, sentiment snapshots, and suggested next touchpoints.

The tracker stores data locally in a SQLite database located at `~/.correspondence_tracker/tracker.db` by default.

## Getting Started

1. Ensure you have Python 3.11+ installed.
2. Clone this repository and change into the project directory.
3. Run tracker commands via `python main.py <command>`.

### Initialize contacts

```bash
python main.py add-contact "Ada Lovelace" --email ada@example.com --preferred-channel email \
  --notes "Met at the computing history meetup"
```

List contacts:

```bash
python main.py list-contacts
```

### Log correspondence

```bash
python main.py log 1 outgoing 2024-03-12T10:00:00 \
  --medium email --subject "Follow up on meetup" \
  --body "Wonderful speaking with you. Would love to connect soon." \
  --tags networking,meetup --follow-up 2024-03-19T09:00:00
```

See correspondence history:

```bash
python main.py history
# filter for a single contact
python main.py history --contact-id 1
```

### Stay on top of follow-ups

```bash
python main.py reminders
# only show items past their due date
python main.py reminders --overdue-only
```

### Relationship insights

```bash
python main.py insights 1
python main.py active
```

## Project Structure

```
correspondence_tracker/
  __init__.py
  database.py        # SQLite schema management and helpers
  services.py        # Domain logic, reminders, insights
main.py               # Command-line interface
```

## Roadmap Ideas

* Attach full documents and store them alongside metadata.
* Integrate with email providers to import conversation threads automatically.
* Plug in NLP services for richer tone analysis and draft suggestions.
* Provide a GUI on top of the same database and service layer.

## License

This project is provided as-is for demonstration purposes.
