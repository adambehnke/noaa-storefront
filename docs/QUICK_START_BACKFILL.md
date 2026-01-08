# NOAA Historical Backfill - Quick Start

## 1. Fix Gold Dashboard (5 minutes)

```bash
cd /Users/adambehnke/Projects/noaa_storefront
AWS_PROFILE=noaa-target bash scripts/fix_gold_dashboard.sh
```

**Result:** Gold layer modal will work without 502 errors

---

## 2. Test Backfill (10 minutes)

```bash
# Test with 7 days of atmospheric data
AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --ponds atmospheric \
  --days-back 7 \
  --test
```

**Expected:** 
- ~1-2 weeks of data ingested
- Checkpoint file created
- Data appears in S3 Bronze layer

---

## 3. Run 90-Day Backfill (6-12 hours)

```bash
# Run all ponds for 90 days
AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --ponds all \
  --days-back 90 \
  > backfill_90d_$(date +%Y%m%d).log 2>&1 &

echo $! > backfill.pid
```

**Monitor:**
```bash
tail -f backfill_90d_*.log
cat backfill_checkpoint.json | python3 -m json.tool
```

---

## 4. Full Year Backfill (24-36 hours)

```bash
# Use screen for long-running process
screen -S noaa-backfill

AWS_PROFILE=noaa-target python3 scripts/historical_backfill_system.py \
  --ponds all \
  --days-back 365

# Detach: Ctrl+A, D
# Reattach: screen -r noaa-backfill
```

---

## 5. Verify Data

```bash
# Check Bronze layer
AWS_PROFILE=noaa-target aws s3 ls \
  s3://noaa-federated-lake-899626030376-dev/bronze/atmospheric/ \
  --recursive --human-readable | tail -20

# Query in Athena
# (Use AWS Console or Athena CLI)
SELECT DATE(observation_time) as date, COUNT(*) as records
FROM gold_atmospheric
WHERE year = 2024
GROUP BY DATE(observation_time)
ORDER BY date DESC;
```

---

## Quick Reference

| Command | Purpose |
|---------|---------|
| `bash scripts/fix_gold_dashboard.sh` | Fix dashboard 502 errors |
| `python3 scripts/historical_backfill_system.py --test` | Test mode (7 days) |
| `python3 scripts/historical_backfill_system.py --ponds all --days-back 90` | 90-day backfill |
| `python3 scripts/historical_backfill_system.py --resume` | Resume from checkpoint |
| `tail -f backfill.log` | Monitor progress |
| `cat backfill_checkpoint.json` | View progress |

---

**Dashboard:** https://d2azko4sm6tkua.cloudfront.net/dashboard_comprehensive.html

**Documentation:**
- Full Guide: `HISTORICAL_BACKFILL_GUIDE.md`
- System Status: `INGESTION_STATUS_REPORT.md`
- All Enhancements: `SYSTEM_ENHANCEMENTS_DEC11.md`
