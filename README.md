# AutoSplit

Turn a UPI payment screenshot into a Splitwise expense. Share a PhonePe receipt
from your phone, pick a group, and AutoSplit reads the amount, UTR, date and
participants off the image with OCR and files the expense for you.

## How it works

```
Phone (Termux)                 Server (Docker Compose)
──────────────                 ───────────────────────────────────────────
share receipt ─► autosplit-    web (Flask)  ──enqueue──►  Redis  ──►  worker (RQ)
                 upload.sh       /upload                                │
                 (fzf group      /groups                                ├─ Tesseract OCR
                  picker)        /jobs/<id>                             ├─ alias matching
                                                                        ├─ duplicate-UTR check
                                                                        └─ Splitwise API
```

1. `termux/autosplit-upload.sh` fetches your Splitwise groups from `/groups`
   (active groups first, then groups settled for more than 30 days), lets you
   pick one with `fzf`, and uploads the image to `/upload`.
2. The web service saves the image and enqueues a job. The worker OCRs it,
   extracts amount, UTR, date and the payment message.
3. The payment message is the convention that drives the split:

   ```
   <description> - <participant> <participant> ...
   Breakfast - me alex sam
   ```

   Text before the dash becomes the expense description. Each name after it
   is matched to a Splitwise friend (exact name, substring, then aliases from
   `aliases.json` with fuzzy matching). `me` is you.
4. You are recorded as paying the full amount; the cost is split equally, one
   share per participant. Names that match no friend are counted as an extra
   share for you rather than dropped.
5. The UTR is recorded so the same receipt is never filed twice.

## Setup

### Server

Requirements: Docker with Compose, and a Splitwise app
(register one at <https://secure.splitwise.com/apps> to get the keys below).

Create `.env` in the repo root:

```env
SPLITWISE_MODE=api
SPLITWISE_CONSUMER_KEY=...
SPLITWISE_CONSUMER_SECRET=...
SPLITWISE_API_KEY=...

PORT=8090
LOG_LEVEL=INFO
REJECT_DUPLICATE_UTR=true
```

Optionally create `data/aliases.json` mapping Splitwise names to the
nicknames you type in payment messages:

```json
{
  "Alex Rivera": ["alex", "ar"],
  "Sam Lee": ["sam"]
}
```

Start it:

```bash
docker compose up -d --build
curl http://localhost:8090/health
```

`data/` is bind-mounted, so aliases and the processed-UTR log survive
rebuilds.

### Phone

1. Install [Termux](https://termux.dev/), Termux:API and Termux:Widget, then
   `pkg install termux-api fzf curl python`.
2. Copy `termux/autosplit-upload.sh` to `~/.shortcuts/` and `chmod +x` it.
3. Point it at your server in `~/.bashrc`. The script tries the LAN address
   first and falls back to the second one (e.g. a Tailscale IP) when you are
   away from home:

   ```bash
   export AUTOSPLIT_LAN="http://192.168.1.x:8090"
   export AUTOSPLIT_TAILSCALE="http://100.x.x.x:8090"
   ```

4. Share a receipt to Termux and run the script with the shared file path.
   You get a notification when the job is queued.

## API

| Method | Path          | Purpose                                        |
| ------ | ------------- | ---------------------------------------------- |
| GET    | `/health`     | Liveness check                                 |
| GET    | `/groups`     | `{active: [...], inactive: [...]}` group names |
| POST   | `/upload`     | Multipart `image` + `group`; returns `job_id`  |
| GET    | `/jobs/<id>`  | Job status and result                          |
| GET    | `/aliases`    | Current alias map                              |
| POST   | `/aliases`    | `{canonical_name, alias}` adds an alias        |
| GET    | `/utrs`       | Processed UTRs                                 |

## Configuration

| Variable                    | Default                    | Notes                                   |
| --------------------------- | -------------------------- | --------------------------------------- |
| `SPLITWISE_MODE`            | `api`                      | `api` or `mcp`                          |
| `SPLITWISE_CONSUMER_KEY`    |                            | Required in `api` mode                  |
| `SPLITWISE_CONSUMER_SECRET` |                            | Required in `api` mode                  |
| `SPLITWISE_API_KEY`         |                            | Required in `api` mode                  |
| `REJECT_DUPLICATE_UTR`      | `true`                     | Refuse receipts whose UTR was seen      |
| `REDIS_URL`                 | `redis://localhost:6381/0` | Overridden in `compose.yml`             |
| `UPLOAD_DIR`                | `/tmp/autosplit/uploads`   | Images are deleted after processing     |
| `UTR_TRACKING_FILE`         | `processed_utrs.json`      | `/app/data/...` under Compose           |
| `ALIAS_FILE_PATH`           | `./aliases.json`           | `/app/data/...` under Compose           |
| `TESSERACT_CMD`             | `/usr/bin/tesseract`       |                                         |
| `PORT`                      | `8090`                     |                                         |
| `LOG_LEVEL`                 | `INFO`                     |                                         |

## Development

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt   # also needs the tesseract binary installed
pytest
```

The tests in `tests/` run real OCR against the receipts in
`tests/test_images/`.

The older Cloud Run / GCS deployment is described in `DEPLOYMENT.md` and
`SETUP_GCLOUD.md`; the Docker Compose setup above is the current one.

## License

[MIT](LICENSE)
