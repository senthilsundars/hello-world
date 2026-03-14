# hello-world
This repository is for practicing the GitHub Flow.

## Apache Spark Download and Install

### Prerequisites

- Java 17 or later (required for Spark 4.1+)

```bash
java -version
```

### 1. Download

Run all of the following commands in the **same terminal session** so the `VER` variable is available to each command:

```bash
VER=4.1.1
wget https://dlcdn.apache.org/spark/spark-$VER/spark-$VER-bin-hadoop3.tgz
```

### 2. Extract and Install

```bash
tar xzf spark-$VER-bin-hadoop3.tgz
sudo mv spark-$VER-bin-hadoop3 /opt/spark
```

### 3. Configure Environment Variables

Add the following lines to your shell configuration file:
- **bash** users: `~/.bashrc`
- **zsh** users (default on macOS): `~/.zshrc`

```bash
export SPARK_HOME=/opt/spark
export PATH=$PATH:$SPARK_HOME/bin:$SPARK_HOME/sbin
```

Then reload your shell configuration. For **bash**:

```bash
source ~/.bashrc
```

For **zsh**:

```bash
source ~/.zshrc
```

> **Tip:** Alternatively, simply open a new terminal window — the variables will be loaded automatically.

### 4. Verify Installation

```bash
spark-shell --version
```

If you see `spark-shell: command not found`, ensure step 3 was completed and that you have sourced (or reopened) your shell configuration.

---

## Apache ZooKeeper 3.9.5 Download and Install

### Prerequisites

- Java 8 or later

```bash
java -version
```

### 1. Download

Run all of the following commands in the **same terminal session** so the `ZK_VER` variable is available to each command:

```bash
ZK_VER=3.9.5
wget https://dlcdn.apache.org/zookeeper/zookeeper-$ZK_VER/apache-zookeeper-$ZK_VER-bin.tar.gz
```

### 2. Extract and Install

```bash
tar xzf apache-zookeeper-$ZK_VER-bin.tar.gz
sudo mkdir -p /usr/local/zookeeper
sudo mv apache-zookeeper-$ZK_VER-bin /usr/local/zookeeper/apache-zookeeper-$ZK_VER-bin
```

### 3. Configure

Copy the sample configuration file and keep the defaults for a standalone setup:

```bash
cp /usr/local/zookeeper/apache-zookeeper-$ZK_VER-bin/conf/zoo_sample.cfg \
   /usr/local/zookeeper/apache-zookeeper-$ZK_VER-bin/conf/zoo.cfg
```

The default configuration sets `dataDir=/tmp/zookeeper`. Create that directory so ZooKeeper can write its data files — **this is the most common cause of the `FAILED TO START` error**:

```bash
sudo mkdir -p /tmp/zookeeper
```

> **Note:** For a production setup, replace `/tmp/zookeeper` with a persistent path (e.g. `/var/lib/zookeeper`) and update the `dataDir` line in `zoo.cfg` to match, then create that directory instead.

### 4. Configure Environment Variables

Add the following lines to your shell configuration file:
- **bash** users: `~/.bashrc`
- **zsh** users (default on macOS): `~/.zshrc`

```bash
ZK_VER=3.9.5
export ZOOKEEPER_HOME=/usr/local/zookeeper/apache-zookeeper-$ZK_VER-bin
export PATH=$PATH:$ZOOKEEPER_HOME/bin
```

Then reload your shell configuration. For **bash**:

```bash
source ~/.bashrc
```

For **zsh**:

```bash
source ~/.zshrc
```

> **Tip:** Alternatively, simply open a new terminal window — the variables will be loaded automatically.

### 5. Start ZooKeeper

```bash
zkServer.sh start
```

### 6. Verify Installation

```bash
zkServer.sh status
```

Expected output includes `Mode: standalone`. To stop ZooKeeper:

```bash
zkServer.sh stop
```

### Troubleshooting: `FAILED TO START`

If `zkServer.sh start` prints `Starting zookeeper ... FAILED TO START`, work through the following checks in order.

#### 1. Check the ZooKeeper log

The log file is named `zookeeper-<user>-server-<hostname>.out` and is written to the directory where you ran `zkServer.sh`. Read it for the root cause:

```bash
cat zookeeper-*-server-*.out
```

#### 2. `dataDir` does not exist (most common cause)

Open `zoo.cfg` and note the value of `dataDir`:

```bash
grep dataDir $ZOOKEEPER_HOME/conf/zoo.cfg
```

Create that directory if it is missing:

```bash
# Default dataDir used by zoo_sample.cfg:
sudo mkdir -p /tmp/zookeeper

# If you customized dataDir, replace the path below:
# sudo mkdir -p /var/lib/zookeeper
```

Then retry `zkServer.sh start`.

#### 3. Port 2181 is already in use

Check whether another process is already listening on the default client port:

```bash
sudo lsof -i :2181
# or
sudo ss -tlnp | grep 2181
```

If a process is listed, either stop it or change the `clientPort` in `zoo.cfg` to a free port (e.g. `clientPort=2182`).

#### 4. AdminServer port 8080 is already in use

ZooKeeper 3.5+ starts a built-in AdminServer (Jetty) on port **8080** by default. If port 8080 is taken you will see this in the log:

```
ERROR Unable to start AdminServer, exiting abnormally
Caused by: java.net.BindException: Address already in use
```

**Option A — change the AdminServer port** (e.g. to 9090):

```bash
echo "admin.serverPort=9090" >> $ZOOKEEPER_HOME/conf/zoo.cfg
```

**Option B — disable the AdminServer entirely**:

```bash
echo "admin.enableServer=false" >> $ZOOKEEPER_HOME/conf/zoo.cfg
```

Then retry `zkServer.sh start`.

#### 5. Java not found

ZooKeeper requires Java 8 or later. Verify it is installed and on your `PATH`:

```bash
java -version
```

If the command is not found, install Java (e.g. `sudo apt install default-jdk` on Debian/Ubuntu or `brew install openjdk` on macOS) and ensure `JAVA_HOME` is set correctly.

---

## Apache Kafka 3.4.1 Download and Install

### Prerequisites

- Java 8 or later
- ZooKeeper — either the standalone install above, or use the ZooKeeper bundled with Kafka (see step 4)

### 1. Download

Run all of the following commands in the **same terminal session** so the `KAFKA_VER` variable is available to each command:

```bash
KAFKA_VER=3.4.1
wget https://dlcdn.apache.org/kafka/$KAFKA_VER/kafka_2.13-$KAFKA_VER.tgz
```

### 2. Extract and Install

```bash
tar xzf kafka_2.13-$KAFKA_VER.tgz
sudo mv kafka_2.13-$KAFKA_VER /opt/kafka
```

### 3. Configure Environment Variables

Add the following lines to your shell configuration file:
- **bash** users: `~/.bashrc`
- **zsh** users (default on macOS): `~/.zshrc`

```bash
export KAFKA_HOME=/opt/kafka
export PATH=$PATH:$KAFKA_HOME/bin
```

Then reload your shell configuration. For **bash**:

```bash
source ~/.bashrc
```

For **zsh**:

```bash
source ~/.zshrc
```

> **Tip:** Alternatively, simply open a new terminal window — the variables will be loaded automatically.

### 4. Start ZooKeeper

**Option A — Standalone ZooKeeper** (installed in the section above):

```bash
zkServer.sh start
```

**Option B — Bundled ZooKeeper** (shipped inside the Kafka package):

```bash
zookeeper-server-start.sh $KAFKA_HOME/config/zookeeper.properties &
```

### 5. Start Kafka Broker

```bash
kafka-server-start.sh $KAFKA_HOME/config/server.properties &
```

### 6. Verify Installation

Check that the broker is running by creating a test topic:

```bash
kafka-topics.sh --create --topic test --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1
kafka-topics.sh --list --bootstrap-server localhost:9092
```

Expected output: `test`

### 7. Stop Kafka and ZooKeeper

```bash
kafka-server-stop.sh
# If using standalone ZooKeeper:
zkServer.sh stop
# If using bundled ZooKeeper:
zookeeper-server-stop.sh
```
