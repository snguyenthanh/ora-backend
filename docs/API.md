# API

## Rules

1. Only 4 HTTP methods are used

- `GET`: Retrieve a resource(s).
- `POST`: Create a resource.
- `PUT`: Replace a resource.
- `PATCH`: Update a resource.

For now, both `PUT` and `PATCH` does exactly the same thing, but preferably use `PATCH`.


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
- `405`: The HTTP method in the request is not allowed for the endpoint.
- `422`: The token is in wrong format or with wrong signature.

## API References

All the `protected` labelled requests require the auth cookie to access.

### 1. Authentication

The requirements for passwords are:
- Minimum length: 8 characters.
- Must have at least 1 number.

#### 1.1. Staff

Request:

```
POST /login
body={
  "email": <str>,
  "password": <str>,
}
```

Response:
```
{
    "user": {
        "full_name": "Admin 1",
        "id": "cf6e9a7bdf434d71a0c12ae91ce95c3d",
        "organisation_id": "6e759fb3eaf6462e8c42cd8ae294d414",
        "email": "admin1",
        "display_name": null,
        "role_id": 3
    },
    "access_token": <str>,
}
```

#### 1.2. Visitor

Request:

```
POST /visitor/login
body={
  "email": <str>,
  "password": <str>,
}
```

Response:

```
{
    "user": {
        "name": "Visitor 1",
        "email": "visitor1",
        "id": "cfd7f4553c9a45b1a81a2384bfcb13a5"
    },
    "access_token": <str>,
}
```

### 2. Visitors

#### 2.1. Create

Request:

```
POST /visitors
body={
  "name": <str>,
  "email": <str>,
  "password": <str>,
}
```

Response:

```
{
    "data": {
        "created_at": 1572027886,
        "email": "visitor1",
        "name": "Visitor 1",
        "disabled": false,
        "updated_at": null,
        "id": "cfd7f4553c9a45b1a81a2384bfcb13a5"
    }
}
```

#### 2.2. Retrieve

> Protected

Request:

```
GET /visitors/<visitor_id>
```

Response:

```
{
    "data": {
        "created_at": 1572027886,
        "email": "visitor1",
        "name": "Visitor 1",
        "disabled": false,
        "updated_at": null,
        "id": "cfd7f4553c9a45b1a81a2384bfcb13a5"
    }
}
```

#### 2.3. Update

> Protected

Only the visitor himself could update.

Request:

```
PATCH /visitors/<visitor_id>
body={
  "name": <new_name>,
}
```

Response:

```
{
    "data": {
        "created_at": 1572027886,
        "email": "visitor1",
        "name": <new_name>,
        "disabled": false,
        "updated_at": null,
        "id": "cfd7f4553c9a45b1a81a2384bfcb13a5"
    }
}
```


### 3. Users (or called `Staffs`)

User roles (Staff) are
- 1. Admin
- 2. Supervisor
- 3. Agent

The users can only be created by someone with a higher role than them. For example:
- `Supervisor` accounts can only be created by `Admin`.
- `Agent` accounts can only be created by either `Supervisor` or `Admin`.

However, for modification, on top of the above rule, an user can also modify himself.

#### 3.1. Create

> Protected

The `organisation_id` of the created accounts will be the same as the requester (handled by server).

Request:

```
POST /users
body={
  "full_name": <str>,
  "email": <str>,
  "password": <str>,
}
```

Response:

```
{
    "data": {
        "created_at": 1572027886,
        "organisation_id": "829146cc86184dd18b207347a52882d7",
        "full_name": "Sydney Alexander",
        "role_id": 3,
        "display_name": null,
        "email": "richardmiller@hotmail.com",
        "disabled": false,
        "updated_at": null,
        "id": "4b0efb2471ea43d3bbd78b9b4061a7ab"
    }
}
```

#### 3.2. Retrieve

> Protected

Request:

```
GET /users/<user_id>
```

Response:

```
{
    "data": {
        "created_at": 1572027886,
        "organisation_id": "829146cc86184dd18b207347a52882d7",
        "full_name": "Sydney Alexander",
        "role_id": 3,
        "display_name": null,
        "email": "richardmiller@hotmail.com",
        "disabled": false,
        "updated_at": null,
        "id": "4b0efb2471ea43d3bbd78b9b4061a7ab"
    }
}
```

#### 3.3. Update

Request:

```
PATCH /users/<user_id>
body={
  "full_name": <new_full_name>,
  "email": <new_email>,
}
```

Response:

```
{
    "data": {
        "created_at": 1572027886,
        "organisation_id": "829146cc86184dd18b207347a52882d7",
        "full_name": <new_full_name>,
        "role_id": 3,
        "display_name": null,
        "email": <new_email>,
        "disabled": false,
        "updated_at": null,
        "id": "4b0efb2471ea43d3bbd78b9b4061a7ab"
    }
}
```

### 4. ChatMessage

Each `ChatMessage` will have the following fields:

- `id` (str): the ID of the chat message.
- `chat_id` (str): a unique ID for each chat room, persists to each visitor.
- `content` (dict): the `content` passed by front-end in SocketIO chat.
- `sender` (str): the ID of the staff who sends the message. If it is the `visitor` who sends it, `sender` is `None`.
- `sequence_num` (int): It determines the exact ordering of messages for *EACH* visitor.
- `type_id` (int): There are 2 types of chat messages:
  + 0: System (for joining and leaving messages)
  + 1: User/Visitor
- `created_at`/`updated_at` (int): Unix timestamps.

#### 4.1. Retrieve

Request:

```
GET /visitors/<visitor_id>/messages
```

Response:

Return the most recent chat messages of the visitor.

*Notes*  
>  The `data` field will be empty if:  
    - The visitor doesn't exist.  
    - The visitor has no messages yet.  
    - There are no messages left to shown.

> The `links.next` will has a link to retrieve to previously sent messages, on top of the ones in the response.  
  `next` is not in `links` if the `data` is empty.

```
{'data': [
    {'chat_id': '67986ad411ff4072947b5a2f0bf9c730',
     'content': <content>,
     'created_at': 1572074948,
     'id': '1e9a98d81ea54a0b808aebf1b54b612a',
     'sender': None,
     'sequence_num': 1,
     'type_id': 1,
     'updated_at': None},
    {'chat_id': '67986ad411ff4072947b5a2f0bf9c730',
     'content': <content>,
     'created_at': 1572074948,
     'id': '721931f8ee084597b09f891d88010bff',
     'sender': 'fabd2da7215a4ed3ba16ad9c98941ce4',
     'sequence_num': 2,
     'type_id': 1,
     'updated_at': None}
  ],
 'links': {'next': 'http://127.0.0.1:60013/visitors/b9d1dccb1aa24ed7b2c306db437f1363/messages?before_id=6010d9d8ef7f407bb6cadb12144576f0'}}
```
