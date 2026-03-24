# hello-world
This repository is for practicing the GitHub Flow.

## Troubleshooting: Beeline / HiveServer2 Connection Issues

### Error: `Failed to connect to localhost:10000`

```
Could not open connection to the HS2 server. Please check the server URI and if the URI is correct,
then ask the administrator to check the server status.
Error: Could not open client transport with JDBC Uri: jdbc:hive2://localhost:10000:
java.net.ConnectException: Connection refused (state=08S01,code=0)
```

**Cause:** HiveServer2 (HS2) is not running. Beeline cannot connect because the server process is not listening on port 10000.

**Fix: Start HiveServer2**

1. **Start HiveServer2** (run as the Hive service user, e.g. `hive`):

   ```bash
   hive --service hiveserver2 &
   ```

   Or, if your environment uses `hiveserver2` directly:

   ```bash
   hiveserver2 &
   ```

2. **Wait for HiveServer2 to be ready.** It may take 30–60 seconds to fully start. Watch for a log line similar to:

   ```
   Starting HiveServer2
   ```

   You can tail the log to confirm:

   ```bash
   tail -f $HIVE_HOME/logs/hiveserver2.log
   ```

3. **Verify the port is listening** before connecting with Beeline:

   ```bash
   # Linux
   ss -tlnp | grep 10000
   # or
   netstat -tlnp | grep 10000
   ```

   You should see a process listening on `0.0.0.0:10000` or `:::10000`.

4. **Connect with Beeline:**

   ```bash
   beeline -u jdbc:hive2://localhost:10000
   ```

---

**Common additional causes and fixes:**

| Symptom | Likely cause | Fix |
|---|---|---|
| Port 10000 not in `ss`/`netstat` output | HS2 not started | Start HiveServer2 (step 1 above) |
| HS2 starts then exits immediately | Configuration error | Check `$HIVE_HOME/logs/hiveserver2.log` for stack traces |
| HS2 running but connection still refused | Firewall blocking port 10000 | Open port: `sudo firewall-cmd --add-port=10000/tcp` (RHEL/CentOS) or `sudo ufw allow 10000` (Ubuntu) |
| Permission denied starting HS2 | Wrong user | Run as the `hive` OS user or the user that owns `$HIVE_HOME` |

**Run HiveServer2 as a foreground process for debugging:**

```bash
hive --service hiveserver2 --hiveconf hive.root.logger=INFO,console
```

This prints all log messages to stdout, making it easier to spot configuration or startup errors.
