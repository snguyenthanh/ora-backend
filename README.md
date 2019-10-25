# Back-end

> Written in Python 3.7

## Installation

### 1. Install Python 3.7 (and pip)
Install Python 3.7 from `Anaconda` is recommended: https://www.anaconda.com/distribution/

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

### 1. Run the server locally for development:

```
./scripts/dev.sh
```

### 2. Run the tests locally:

On the first run, it will be a bit slow, as the script creates a `Docker` container for a testing `PostgreSQL` database.

```
./scripts/test_dev.sh
```

#### Run a specific test

Edit the `pipenv run pytest` line inside `./scripts/test_dev.sh` to run the test you want. An example is commented out in the file.

### 3. Setup fake DB content + Update dev database schema:

> Requires the `dev` instance from part 1 to be running

```
./scripts/setup_dev_db.sh
```

### 4. Pipenv to requirements.txt

In case you would like to get `requirements.txt`, run:
```
./scripts/lock_pipenv.sh
```

And the 2 `requirements.txt` for `test` and `main` will be created in folder `requirements`.

### 5. Code style

Before committing your changes, it is recommended to run:
```
black .
```

which will format the code styles all Python files

## Workflow (for front-end)

### Login
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
