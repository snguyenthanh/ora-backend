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
2. The server returns an access token and refresh token.
3. The client stores both `access_token` and `refresh_token` to its browser.
4. The client uses the `access_token` to authorize the user's requests, by adding it to the headers of the requests.
5. When the `access_token` expires, the client sends the `refresh_token` to endpoint `/refresh` to get a new `access_token`.
6. Replace the expired `access_token` with the freshly retrieved one in the browser.
6. Repeat from step 4.

## Rules

1. Only 4 HTTP methods are used

- `GET`: Retrieve a resource(s).
- `POST`: Create a resource.
- `PUT`: Replace a resource.
- `PATCH`: Update a resource.
- `DELETE`: Delete a resource.


## Query parameters

 - `GET` and `DELETE` requests will ignore the request's body.
 - `POST` requests will ignore the request's query parameters.
 - `PUT` and `PATCH` requests use the request's query parameters to retrieve the resources, and use the request's body to update them.

### 1. GET
- limit (`int`): the maximum number of rows to return(Min=0, Max=100). Default: 15.
- after_id (`int`): The returned rows will have their IDs starting from `after_id` (exclusive) (Keyset pagination). Default: 0.

## Pagination

Responses that support getting multiple rows will have a key called `links` (apart from `data`) for clients to directly call and retrieve the next page of rows of the resource.

*Example*

Note that the hostname of `127.0.0.1:8000` in the example will be automatically changed to the hostname of the actual running server.

So you don't have to worry and could use the URL directly without issues.

```
{
    "data": [
        {
            "some_field": "hello",
            "created_at": 1569140236,
            "updated_at": 1569222798
        },
        ...
    ],
    "links": {
        "next": "http://127.0.0.1:8000/resources?after_id=db4510e134b44a73afeb7e7b8da59561"
    }
}
```


## Common HTTP codes of responses
- `400`: Missing field `email` and/or `password` in the request's body, or incorrect format of `email` and/or `password`.
- `401`:
    - Login: Invalid `email` or `password`.
    - The access token has expired, invalid or missing.
- `403`: The request failed for an authenticated user, who does not have authorization to access the requested resource.
- `404`: Resource is not found.
- `405`: HTTP method is not allowed for the endpoint.
- `422`: The token is in wrong format or with wrong signature.
