# Lead handoff — Ray's side

Your machine scrapes the boards bonbon can't reach (Indeed, ZipRecruiter);
bonbon's sweep pulls the results from here every 6 hours.

## One-time setup (5 minutes)

1. **Create the GitHub repo.** New repo, name it `jobberworkee-lead-handoff`,
   **public** (job listings are public data; bonbon has no GitHub login, so a
   private repo won't work for her). No README/gitignore needed.

2. **Clone it and install the script:**
   ```bash
   git clone <your-new-repo-url> /home/rswan/lead-handoff
   # then unzip this bundle and copy handoff.py into /home/rswan/lead-handoff/
   cp /path/to/unzipped/handoff.py /home/rswan/lead-handoff/handoff.py
   chmod +x /home/rswan/lead-handoff/handoff.py
   ```

3. **Smoke test** (runs one scrape + export + push right now):
   ```bash
   /home/rswan/miniconda3/bin/python3 /home/rswan/lead-handoff/handoff.py
   ```
   Expect log lines ending in `pushed OK`. Check the repo on GitHub — you
   should see `leads/<timestamp>.json` and `watermarks/rswan.json`.

4. **Install the cron** (every 6 hours, offset so your push lands before
   bonbon's pull):
   ```bash
   (crontab -l 2>/dev/null; echo "17 */6 * * * /home/rswan/miniconda3/bin/python3 /home/rswan/lead-handoff/handoff.py >> /home/rswan/lead-handoff/cron.log 2>&1") | crontab -
   ```

5. **Send bonbon the repo URL** so she can clone it on her side.

## What it does each run

- Makes sure your Jobberworkee API is up (starts it if not).
- Scrapes Indeed + ZipRecruiter for the 8 Salesforce/AI query families,
  Houston + Remote, last 48h.
- Writes fresh leads to `leads/YYYY-MM-DD-HHMM.json`, updates
  `watermarks/rswan.json`, commits and pushes.

Overlap between runs is fine — bonbon dedupes by job ID on import.

## Notes

- Python is `/home/rswan/miniconda3/bin/python3` (conda base), per your setup.
- Logs go to `/home/rswan/lead-handoff/cron.log`.
- Your scraped leads also upsert into the shared Pinecone index automatically
  (your API already does that on save).
- To stop: `crontab -e` and delete the line.
