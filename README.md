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

2. **Wait for HiveServer2 to be ready.** It may take 30–60 seconds to fully start. Watch for a log line indicating the server is listening, such as:

   ```
   Started ThriftBinaryCLIService on port 10000
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

---

### Message: `HiveServer2 running as process XXXXX. Stop it first.`

```
HiveServer2 running as process 20878.  Stop it first.
    PID TTY      STAT   TIME COMMAND
  20878 pts/5    Tl     0:16 /usr/lib/jvm/java-21-openjdk-amd64//bin/java -Dproc_jar -Dproc_hiveserver2 ...
```

**This message means HiveServer2 is already running** — it is not an error. You do not need to start it again.

**Step 1 — Try connecting with Beeline directly:**

```bash
beeline -u jdbc:hive2://localhost:10000
```

**Step 2 — If Beeline still fails, check whether HS2 has finished starting up.** The process can be alive but still initializing (this typically takes 30–60 seconds). Confirm the port is open:

```bash
ss -tlnp | grep 10000
```

If port 10000 is not yet listed, wait a moment and try again.

**Step 3 — If you need to restart HS2** (e.g. after a config change), stop the existing process first, then start a fresh one:

```bash
# Stop the running instance — replace <PID> with the number shown in the message
kill <PID>

# Wait a few seconds, then start HS2 again
hive --service hiveserver2 &
```

Alternatively, if your Hive installation provides a stop script:

```bash
hive --service hiveserver2 stop
```

---

### Warning: `SLF4J: Class path contains multiple SLF4J bindings`

```
SLF4J: Class path contains multiple SLF4J bindings.
SLF4J: Found binding in [.../log4j-slf4j-impl-2.24.3.jar!/org/slf4j/impl/StaticLoggerBinder.class]
SLF4J: Found binding in [.../slf4j-reload4j-1.7.36.jar!/org/slf4j/impl/StaticLoggerBinder.class]
SLF4J: Actual binding is of type [org.apache.logging.slf4j.Log4jLoggerFactory]
```

**These warnings are harmless.** They appear because both Hive (`log4j-slf4j-impl`) and Hadoop (`slf4j-reload4j`) ship their own SLF4J binding. SLF4J picks one (Hive's Log4j binding in this case) and logs a warning about the others.

- HiveServer2 will start and function normally despite these warnings.
- To silence them, you can exclude Hadoop's `slf4j-reload4j` JAR from Hive's classpath, but this is optional and only cosmetic:

  ```bash
  # Optional: exclude Hadoop's SLF4J binding from Hive's classpath
  export HADOOP_USER_CLASSPATH_FIRST=true
  ```

  A permanent fix is to remove (or rename) the conflicting JAR:

  ```bash
  sudo mv /usr/local/hadoop/share/hadoop/common/lib/slf4j-reload4j-1.7.36.jar \
          /usr/local/hadoop/share/hadoop/common/lib/slf4j-reload4j-1.7.36.jar.bak
  ```

  > **Note:** Removing a Hadoop JAR may affect Hadoop utilities that rely on it. Test thoroughly before doing this in a production environment.
