# hello-world
This repository is for practicing the GitHub Flow.

## Apache Spark Download and Install

### Prerequisites

- Java 17 or later (required for Spark 4.1+)

```bash
java -version
```

### 1. Download

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

Add the following lines to your `~/.bashrc` (or `~/.zshrc`):

```bash
export SPARK_HOME=/opt/spark
export PATH=$PATH:$SPARK_HOME/bin:$SPARK_HOME/sbin
```

Then reload your shell configuration:

```bash
source ~/.bashrc
```

### 4. Verify Installation

```bash
spark-shell --version
```
