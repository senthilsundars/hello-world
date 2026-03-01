# hello-world
This repository is for practicing the GitHub Flow.

---

## How to Install MySQL

### On Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y mysql-server
sudo systemctl start mysql
sudo systemctl enable mysql
sudo mysql_secure_installation
```

### On CentOS/RHEL
```bash
sudo yum install -y mysql-server
sudo systemctl start mysqld
sudo systemctl enable mysqld
sudo mysql_secure_installation
```

### On macOS (using Homebrew)
```bash
brew update
brew install mysql
brew services start mysql
mysql_secure_installation
```

### Verify Installation
```bash
mysql --version
mysql -u root -p
```

---

## How to Connect Apache Hive with HDFS

### Prerequisites
- Apache Hadoop (HDFS) installed and running
- Apache Hive installed
- Java 8 or higher

### Step 1: Configure HDFS Directories for Hive
```bash
# Create required HDFS directories
hdfs dfs -mkdir -p /user/hive/warehouse
hdfs dfs -chmod g+w /tmp
hdfs dfs -chmod g+w /user/hive/warehouse
```

### Step 2: Configure hive-site.xml
Edit `$HIVE_HOME/conf/hive-site.xml` and set the following properties:

```xml
<configuration>
  <property>
    <name>hive.metastore.warehouse.dir</name>
    <value>/user/hive/warehouse</value>
  </property>
  <property>
    <name>fs.defaultFS</name>
    <value>hdfs://localhost:9000</value>
  </property>
</configuration>
```

### Step 3: Initialize the Hive Metastore
```bash
# Using Derby (default, for testing)
schematool -initSchema -dbType derby

# Using MySQL as the Hive Metastore
schematool -initSchema -dbType mysql
```

### Step 4: Use MySQL as the Hive Metastore Backend (Optional)
1. Create a MySQL database and user for Hive:
   ```sql
   CREATE DATABASE metastore;
   CREATE USER 'hive'@'localhost' IDENTIFIED BY 'your_secure_password';
   GRANT ALL PRIVILEGES ON metastore.* TO 'hive'@'localhost';
   FLUSH PRIVILEGES;
   ```

2. Add the MySQL JDBC driver to Hive's lib directory:
   ```bash
   cp mysql-connector-java-*.jar $HIVE_HOME/lib/
   ```

3. Update `hive-site.xml` with MySQL connection details (replace `your_secure_password` with a strong password, or use a secrets manager / environment variable to avoid storing credentials in plaintext):
   ```xml
   <property>
     <name>javax.jdo.option.ConnectionURL</name>
     <value>jdbc:mysql://localhost/metastore?createDatabaseIfNotExist=true</value>
   </property>
   <property>
     <name>javax.jdo.option.ConnectionDriverName</name>
     <value>com.mysql.cj.jdbc.Driver</value>
   </property>
   <property>
     <name>javax.jdo.option.ConnectionUserName</name>
     <value>hive</value>
   </property>
   <property>
     <name>javax.jdo.option.ConnectionPassword</name>
     <value>your_secure_password</value>
   </property>
   ```

4. Initialize the schema:
   ```bash
   schematool -initSchema -dbType mysql
   ```

### Step 5: Start Hive
```bash
# Start Hive CLI
hive

# Start HiveServer2
hiveserver2
```

### Step 6: Verify Connectivity
```bash
# In the Hive CLI, create a test table and verify HDFS storage
hive> CREATE TABLE test (id INT, name STRING);
hive> SHOW TABLES;

# Verify data is stored in HDFS
hdfs dfs -ls /user/hive/warehouse/
```
