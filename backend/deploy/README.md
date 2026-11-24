## Database Installation 

#### Requirements

 * Docker and docker compose for Windows/Linux

 * Create an .env file in the deploy directory by copying the following:

```
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=phawmdb

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_TLS=True
EMAILS_FROM_EMAIL=noreply@phawm.org
EMAILS_FROM_NAME=PHAWM Workbench
FRONTEND_URL=http://localhost:3000
```

Add a user and password of your liking (without quotes).


__The .gitignore file that's used in the repository will ignore the .env file but be careful to not upload or commit the username and password you setup to github.__

#### PostgreSQL with dbeaver

A docker-compose file that defines the postgres database and its schema with a dbeaver interface is provided in the `deploy` folder.
Docker automatically builds a database and adds the tables defined in init.sql 

To bring up both services, bring up the command line/Windows Powershell and type:

```
cd deploy

docker-compose up -d
```

To verify that the services are running, type:

```
docker ps
```

We should see what is currently running:

```
CONTAINER ID   IMAGE                                COMMAND                  CREATED          STATUS                 PORTS
                                                                 NAMES
feece5567644   dbeaver/cloudbeaver:25               "./launch-product.sh"    21 minutes ago   Up 21 minutes          0.0.0.0:8978->8978/tcp
, :::8978->8978/tcp                                              db-gui
5797b336f913   postgres:15                          "docker-entrypoint.s…"   21 minutes ago   Up 21 minutes          0.0.0.0:5432->5432/tcp
, :::5432->5432/tcp 
```


## Dbeaver interface

The dbeaver interface provides a way to visually inspect the database and run queries against it.

In order to access it, visit http://localhost:8978

When we login for the first time, it requires a user to be created. Make sure you save the password and username. This is a separate login from the database username/password and it's used for dbeaver.

After logging in, the database, schema and any tables should be visible on the drop down menu on the left side of the dbeaver page.

## PGAdmin interface

The pgAdmin interface provides a way to visually inspect the database and run queries against it.

In order to access it, visit http://localhost:5050

The pgadmin login screen should appear. Provide the username and password that you supplied in the docker-compose.yml for
the pgadmin service.

Now we have to make a connection to the database so that pgadmin can connect to it. Create a connection:

Top left corner click, Object --> Create --> Server

Give a name to the connection in the General tab.
Go to the "Connection" tab and add the following:

Host name: phawmdb (or the database name you provided)
Port: 5432

Username: the database username for postgresql

Click save

Connect to the database by providing the password you've set either in the docker-compose.yml or in the .env file for postgresql.

The tables should be visible inside the database, then go to Schemas and then Tables to view them.
