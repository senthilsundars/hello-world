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

## Apache ZooKeeper 3.6.4 Download and Install

### Prerequisites

- Java 8 or later

```bash
java -version
```

### 1. Download

Run all of the following commands in the **same terminal session** so the `ZK_VER` variable is available to each command:

```bash
ZK_VER=3.6.4
wget https://dlcdn.apache.org/zookeeper/zookeeper-$ZK_VER/apache-zookeeper-$ZK_VER-bin.tar.gz
```

### 2. Extract and Install

```bash
tar xzf apache-zookeeper-$ZK_VER-bin.tar.gz
sudo mv apache-zookeeper-$ZK_VER-bin /opt/zookeeper
```

### 3. Configure

Copy the sample configuration file and keep the defaults for a standalone setup:

```bash
cp /opt/zookeeper/conf/zoo_sample.cfg /opt/zookeeper/conf/zoo.cfg
```

### 4. Configure Environment Variables

Add the following lines to your shell configuration file:
- **bash** users: `~/.bashrc`
- **zsh** users (default on macOS): `~/.zshrc`

```bash
export ZOOKEEPER_HOME=/opt/zookeeper
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
