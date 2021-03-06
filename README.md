# Back-end

> Written in Python 3.7

## Installation

### 1. Install Python 3.6+ (and pip)

### 2. Install the dependencies for Python

```
# Install pipenv
pip install pipenv

# Install the dependencies
pipenv install
```

### 3. Install Docker
https://docs.docker.com/install/

> You will need to register a Docker account, to download Docker.


## Usage

### 1. Ensure `Docker` is running

### 2. Run the server locally for development:

```
./scripts/dev.sh
```

### 3. Run the tests locally:

On the first run, it will be a bit slow, as the script creates a `Docker` container for a testing `PostgreSQL` database.

```
./scripts/test_dev.sh
```

#### Run a specific test

Edit the `pipenv run pytest` line inside `./scripts/test_dev.sh` to run the test you want. An example is commented out in the file.

### 4. Setup dev DB + Update dev database schema:

> Requires the `dev` instance from part 1 to be running

```
./scripts/setup_dev_db.sh
```

### 5. Pipenv to requirements.txt

In case you would like to get `requirements.txt`, run:
```
./scripts/lock_pipenv.sh
```

And the 2 `requirements.txt` for `test` and `main` will be created in folder `requirements`.

### 6. Code style

Before committing your changes, it is recommended to run:
```
black .
```

which will format the code styles all Python files

## Login flow (for front-end)

```
An access token is a short-life token used for sending authorized requests.
A refresh token is a long-life token used to generate new access tokens. In this application, refresh tokens don't expire.
```

1. The client sends a request with fields `email` and  `password` in the request's body.
2. The server returns a response, with `user` and `access_token` in the body and a cookie.
3. The client stores both `access_token` to its browser.
4. The client uses the cookie to authorize the user's requests.
5. When the cookie expires, the client sends the cookie to endpoint `/refresh` to get a new cookie.
6. Replace the expired `access_token` with the freshly retrieved one in the browser.
6. Repeat from step 4.

## Documentation

- [API References and how to use](docs/API.md)
- [Chat (using SocketIO)](docs/Chat_using_SocketIO.md)

## Deployment

Both `app.py` and `app_socketio.py` need to be run to fully achieve all functionalities.

The commands to run them are located in variable `ExecStart` in [deployment/ora.service](deployment/ora.service) and [deployment/ora_socketio.service](deployment/ora_socketio.service)

`.nginx.conf` is the `NginX` configuration used in the `DigitalOcean` server.

`*.service` files are the `systemctl` services to auto-run the application.

## Tech stack

1. Database: [PostgreSQL](https://www.postgresql.org)
1. Database ORM: [Gino](https://github.com/python-gino/gino)
1. Database Schema Migration: [Alembic](https://alembic.sqlalchemy.org/en/latest)
1. Chat: [python-socketio](https://github.com/miguelgrinberg/python-socketio) is used for chat events (such as sending/receiving chat messages, updating online statuses, etc.)
1. Monitoring: [Prometheus](https://prometheus.io) for storing metrics of requests, which could be used by other visualization tools to see requests count, latency, error rates, etc.
1. Error logging: [Sentry](https://sentry.io)
1. Sending emails (for new incoming chats, visitors replying a message, etc.): [SendGrid](https://sendgrid.com)
1. Metadata of chat rooms and online users are stored in [Redis](https://redis.io)
1. [Redis](https://redis.io) is also used as a message queue for email sending tasks.
1. [Celery](http://www.celeryproject.org): manage workers and allow workers to take tasks from `Redis` and execute them.
1. [Flower](https://flower.readthedocs.io/en/latest): A monitoring tool for `Celery`, to track and manage running tasks and failures.

## Risks of usage

### 1. Chat - [ora_backend/views/chat_socketio.py](ora_backend/views/chat_socketio.py)
- For each connection, the user's information is stored in the SocketIO's session. It should be changed so that the user's information is stored in a centralized `Redis` instance, as the session is only available separatedly to each machine.
  - Be noted that, for `app_socketio.py`, as each `gunicorn` worker actually doesn't share memory, they won't be able to access others' sessions. [Link to discussion](https://github.com/miguelgrinberg/python-socketio/issues/371)
- Some chat events may not work properly (such as events for changing chat priority, transfering ownership of the chat room, etc.) as this project was done without being properly tested.

### 2. Auto-assign volunteers on new chats - [ora_backend/utils/assign.py](ora_backend/utils/assign.py)
- Sometimes, the auto-assign functionality doesn't seem to email/assign the correct volunteers


## Project Structure

### 1. `app.py` and `app_socketio.py`

- `app.py` is the REST API server used mostly for authentication, bookmarking visitors, fetching chat history, etc.

- `app_socketio.py` is the SocketIO server to send/receive SocketIO events with front-end for chat functionalities.

### 2. `Pipfile`

It is similar to `package.json`, which includes the dependencies of the project.

### 3. Folder `deployment/`

The config files (including for `NginX` and `systemctl`) used in the `DigitalOcean` server.

### 4. Folder `requirements/`

The `requirements.txt` files generated by `Pipenv`
from running `./scripts/lock_pipenv.sh`

### 5. Folder `ora_backend/`

It is the main source code of the project.

- [ora_backend/\_\_init\_\_.py](ora_backend/__init__.py): Setting up the application
- [ora_backend/models.py](ora_backend/models.py): The Database models of the application.
- [ora_backend/schemas.py](ora_backend/schemas.py): The schemas used for input serialization and de-serialization on requests.

### 6. Folder `ora_backend/config/`

The configurations of the application and connection to Database.

### 7. Folder `ora_backend/tasks/`

The background running tasks of the application.

### 8. Folder `ora_backend/templates/`

The HTML templates used to send emails.

### 9. Folder `ora_backend/views/`

The logic/execution of all the REST endpoints and SocketIO events.

### 10. Folder `ora_backend/worker/`

Declaration of the tasks that will be ran by `Celery`.
