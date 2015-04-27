Qiita installation
==================

Qiita is pip installable, but depends on some non-python packages that must be installed first.

Install the non-python dependencies
-----------------------------------

* [PostgreSQL](http://www.postgresql.org/download/) (we have tested most extensively with 9.3)
* [redis-server](http://redis.io) (we have tested most extensively with 2.8.17)

Install both of these packages according to the instructions on their websites. You'll then need to ensure that the postgres binaries (for example, ``psql``) are in your executable search path (``$PATH`` environment variable).

Install Qiita and its python dependencies
-----------------------------------------

Then, you can use pip to install Qiita, which will also install its python dependencies.

```bash
pip install numpy
pip install https://github.com/biocore/mustached-octo-ironman/archive/master.zip --no-deps
pip install qiita-spots
```

Qiita configuration
===================
After these commands are executed, you will need to:
1. Download a [sample Qiita configuration file](https://github.com/biocore/qiita/blob/master/qiita_core/support_files/config_test.txt).

  ```bash
  cd
  curl -O https://raw.githubusercontent.com/biocore/qiita/master/qiita_core/support_files/config_test.txt > config_test.txt
  ```

2. Set your `QIITA_CONFIG_FP` environment variable to point to that file:

  ```bash
  echo "export QIITA_CONFIG_FP=$HOME/config_test.txt" >> ~/.bashrc
  echo "export MOI_CONFIG_FP=$QIITA_CONFIG_FP" >> ~/.bashrc
  source ~/.bashrc
  ```

3. Start a test environment:

  ```bash
  qiita_env make --no-load-ontologies
  ```

4. Finally you can start the server:

  ```bash
  qiita_env start_cluster demo test reserved && sleep 30
  qiita webserver start
  ```

If all the above commands executed correctly, you should be able to go to http://localhost:21174 in your browser, to login use `demo@microbio.me` and `password` as the credentials. (In the future, we will have a *single user mode* that will allow you to use a local Qiita server without logging in. You can track progress on this on issue [#920](https://github.com/biocore/qiita/issues/920).)

## Installation issues on Ubuntu 14.04

### `fe_sendauth: no password supplied`

If you get a traceback similar to this one when starting up Qiita
```python
File "/home/jorge/code/qiita/scripts/qiita_env", line 71, in make
  make_environment(load_ontologies, download_reference, add_demo_user)
File "/home/jorge/code/qiita/qiita_db/environment_manager.py", line 180, in make_environment
  admin_conn = SQLConnectionHandler(admin='admin_without_database')
File "/home/jorge/code/qiita/qiita_db/sql_connection.py", line 120, in __init__
  self._open_connection()
File "/home/jorge/code/qiita/qiita_db/sql_connection.py", line 155, in _open_connection
  raise RuntimeError("Cannot connect to database: %s" % str(e))
RuntimeError: Cannot connect to database: fe_sendauth: no password supplied
```
it can be solved by setting a password for the database (replace `postgres` with the actual name of the database qiita is configured to use):
```
$ psql postgres
ALTER USER postgres PASSWORD 'supersecurepassword';
\q
```

It might be necessary to restart postgresql: `sudo service postgresql restart`.

Furthermore, the `pg_hba.conf` file can be modified to change authentication type for local users to trust (rather than, e.g., md5) but we haven't tested this solution.

Installing optional qiita dependencies
--------------------------------------

For large scale systems, pgbouncer is preferable to a straight postgres connection as it removes postgresql connection overhead. To install pgbouncer, you will need libevent. Installation instructions for OSX are available [here](http://mac-dev-env.patrickbougie.com/libevent/).

Once libevent is installed, you can install pgbouncer. Source code is available [here](https://pgbouncer.github.io/downloads/). If libevent was installed using the instructions above, run config using 
```
./configure --prefix=/usr/local --with-libevent=/usr/local/libevent
```
Then make and make install as usual. Configuration and usage instructions are at [pgbouncer's homepage](https://pgbouncer.github.io/).

## Troubleshooting installation on non-Ubuntu operating systems

### xcode

If running on OS X you should make sure that the Xcode and the Xcode command line tools are installed.

### postgres

If you are using Postgres.app on OSX, a database user will be created with your system username. If you want to use this user account, change the `USER` and `ADMIN_USER` settings to your username under the `[postgres]` section of your Qiita config file.
