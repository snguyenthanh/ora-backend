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
        "role_id": 3,
        "disabled": False,
        "is_anonymous": False,
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
        "id": "cfd7f4553c9a45b1a81a2384bfcb13a5",
        "is_anonymous": False,
        "disabled": False,
    },
    "access_token": <str>,
}
```

#### 1.3. Anonymous (Guest)

An anonymous account will be created upon login.

Request:

```
POST /anonymous/login
body={
  "name": "John"
}
```

Response:

```
{
    "user": {
        "name": "Visitor 1",
        "is_anonymous": true,
        "disabled": false,
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
        "is_anonymous": false,
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

#### 2.3. Retrieve bookmarked visitors of the staff

> Protected

Request:

```
GET /visitors
```

Response:

```
{
  "data": [
    {
      'created_at': 1572708622,
      'disabled': False,
      'email': 'kathysampson@yahoo.com',
      'id': '92c04d72a8af4d9fad34f1059ec384d6',
      'is_anonymous': False,
      'name': 'Bradley Owens',
      'updated_at': None
    },
    {
      'created_at': 1572708622,
      'disabled': False,
      'email': 'shellydavis@hotmail.com',
      'id': 'fc027745297b4ce3b1cd77e618daf484',
      'is_anonymous': False,
      'name': 'Michael Harmon',
      'updated_at': None
    }
  ],
  'links': {
    'next': 'http://127.0.0.1:58048/visitors?after_id=fc027745297b4ce3b1cd77e618daf484'
  }
}
```

#### 2.4. Update

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

Query parameters:
- `starts_from_unread` (bool): If this param is presented in the query, returns the chat messages that the staff has seen until the last read message.

> *Note*  
Either `starts_from_unread`, `before_id` or `after_id` should be presented in the url.

```
GET /visitors/<visitor_id>/messages?starts_from_unread=true
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
     'sender': {
       'created_at': 1572086368,
       'disabled': False,
       'email': 'agent1@gmail.com',
       'full_name': 'Agent 1',
       'id': '581f09322163438da5b888dff84b4e44',
       'organisation_id': 'ee2b74f3294347578063eb4e2c9fa949',
       'role_id': 3,
       'updated_at': None
      },
     'sequence_num': 2,
     'type_id': 1,
     'updated_at': None},
     ...
  ],
 'links': {
   'prev': 'http://127.0.0.1:60013/visitors/b9d1dccb1aa24ed7b2c306db437f1363/messages?before_id=6010d9d8ef7f407bb6cadb12144576f0',
   'next': 'http://127.0.0.1:60013/visitors/b9d1dccb1aa24ed7b2c306db437f1363/messages?after_id=721931f8ee084597b09f891d88010bff',
  }
}
```


### 5. Chat

#### 5.1. Last read message

##### 5.1.1. Retrieve last read message id

Return the information of the last read message indication.

Request:

```
GET /chats/<chat_id>/last_seen
```

Response:

```
{
  "data": {
      id: <str>,
      staff_id: <str>, # Same as the requester's auth token
      chat_id: <str>,
      last_seen_msg_id: <str>, # The ID of the last seen ChatMessage
      created_at: <int>,
      updated_at: <int>,
  }
}
```

##### 5.1.2. Update last read message id

Update the information of the last read message indication.

Request:

```
PATCH /chats/<chat_id>/last_seen

data={
  "last_seen_msg_id": <str>,  # ID of the ChatMessage to be marked as last read
}
```

Response:

```
{
  "data": {
      id: <str>,
      staff_id: <str>, # Same as the requester's auth token
      chat_id: <str>,
      last_seen_msg_id: <str>, # The ID of the last seen ChatMessage
      created_at: <int>,
      updated_at: <int>,
  }
}
```
