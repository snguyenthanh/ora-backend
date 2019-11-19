# Chat

SocketIO is event-based and most of the logic will be handled by back-end.

All emitted events will return 2 variables:
  - result (`boolean`): if the event succeeds.
  - error_message (`str`): why it fails.

## Data formats

### `ChatMessage.content`

The `content` is decided to be in `JSON format`.

However, there are no rules to enforce the structure and it will be stored as is when passed from front-end.

### Room

All the `room` in the responses' data sent from server will be in `Dict` format, while clients only need to send the `room.id` to server.

## 1. Connect

Both visitors and staffs connect to the server by putting the `access_token` in `Authorization` header in the request ("Bearer " keyword is not necessary).

```
socketio.connect(
      <host>, headers={"Authorization": <access_token>}
  )
```

This event will return a `401` response if the token is missing/invalid.

## 2. Disconnect

### 2.1. Visitors

A visitor can either disconnect or emit an event `visitor_leave_room` (with no `data`) to close the chat room.

When a visitor disconnects, the server will:
- Emit an event `visitor_leave` to other connected client (the staff).
- Close all the connections to the room (the staff's connection).
- Close the room.

### 2.2. Staffs

To leave a chat, a staff emits an event `staff_leave_room`, with `data={"room": <room_id>}`.

On receiving the event `staff_leave_room`, the server will:
- Emit an event `staff_leave` to the connected visitor.
- Close all the connections to the room (the visitor's connection).
- Close the room.

In the case of disconnection, *ALL* the chat rooms will be closed, and each visitor will receive a corresponding `staff_leave` event.

## 3. Events

> All the events that the client can send / receive.

### 3.1. Send

All emitted events will return 2 variables:
  - result (`boolean`): if the event succeeds.
  - error_message (`str`): why it fails.

#### staff_join

For staff to join a room.

Args:

`data` (dict)

```
data={
	"visitor": <str>,	# The visitor's id
}
```

#### visitor_first_msg

For visitor to send the first message to start a new chat session.

Args:

`content` (dict): the message content.

```
content=<content>
```

#### visitor_msg_unclaimed

For visitor to send more messages after the first one, while the chat is *NOT* claimed.

Args:

`content` (dict): the message content.

```
content=<content>
```

#### visitor_msg

For visitor to send a message to the staff in the chat room.

Args:

`content` (dict): the message content.

```
content=<content>
```

#### staff_msg

For staff to send a message to the visitor.

Args:

`data` (dict):

```
data={
	"visitor": <str>,  # The visitor's id
	"content": <content>,	# dict
}
```

#### staff_leave_room

For a staff to leave a chat room.

Args:

`data` (dict):

```
data={
	"visitor": <str> # The visitor id
}
```

#### visitor_leave_room

For a visitor to leave the chat room.

The event `visitor_first_msg` must be sent to create a new chat sesssion.

Args: `None`

#### take_over_chat

For a supervisor / admin to take over a chat from a low-level staff (agent).

Args:

`data` (dict):

```
data={
	"visitor": <visitor_id> # The visitor for the supervisor/admin to take over
}
```

#### add_staff_to_chat

For a supervisor / admin to add new staffs to a chat.

Args:

`data` (dict):

```
data={
	"visitor": <visitor_id>, # The visitor's ID
  "staff": <staff_id> # The staff's ID
}
```

#### remove_staff_from_chat

For a supervisor / admin to remove a staff from a chat.

Args:

`data` (dict):

```
data={
	"visitor": <visitor_id>, # The visitor's ID
  "staff": <staff_id> # The staff's ID
}
```

#### change_chat_priority

For any staffs to change a chat's priority (flag/unflag).

Args:

`data` (dict):

```
data={
  "severity_level": <int>, # Default: 0
	"visitor": <str> # The visitor id
}
```

### 3.2. Receive

#### 3.2.1. All staffs

##### staff_already_online

The back-end will emit this event on staff opening a session when he has another opened session.

Args:

`data` (dict)

```
data={
  "staff": {
    "full_name": "Admin 1",
    "id": "cf6e9a7bdf434d71a0c12ae91ce95c3d",
    "organisation_id": "6e759fb3eaf6462e8c42cd8ae294d414",
    "email": "admin1",
    "display_name": null,
    "role_id": 3
  }
```

##### staff_init

The staff will receive a list of all unclaimed chats
right after connecting to the server.

Args:

`data` (dict): A list of unclaimed chats and a list of currently online staffs to show on front-end.

```
data={
  "online_users": [
    {
      email: "agent1@gmail.com",
      created_at: 1572522995,
      full_name: "Agent 1",
      updated_at: null,
      id: "06274871777d40f387ab430da6b3aa08",
      display_name: null,
      organisation_id: "bd9c4046763440769e3af30197a2482e",
      disabled: false,
      role_id: 3,
    },
    ...
  ],
  "online_visitors": [
    {
      email: "visitor2@gmail.com",
      is_anonymous: false,
      created_at: 1572522995,
      updated_at: null,
      name: "Visitor 2",
      id: "b25162f797fb4182b69d8b2141274525",
      disabled: false,
    },
    ...
  ],
  "unclaimed_chats": [
    {
        "visitor": { # The visitor
          "id": "cfd7f4553c9a45b1a81a2384bfcb13a5", # Visitor ID
          "name": "Visitor 1",
          "email": "visitor1",
          "visitor_id": "cfd7f4553c9a45b1a81a2384bfcb13a5",
          "tags": [],
          "severity_level": 0,
        },
        "contents": [content] # A list of `ChatMessage.content`, format decided by front-end
    },
    ...
  ],
  "offline_unclaimed_chats": [
    { # The visitor info
      "id": "cfd7f4553c9a45b1a81a2384bfcb13a5", # Visitor ID
      "name": "Visitor 1",
      "email": "visitor1",
      "visitor_id": "cfd7f4553c9a45b1a81a2384bfcb13a5",
      "tags": [],
      "severity_level": 0,
    }
  ],
  "flagged_chats": [ # Top-15 recently flagged chats
    {
      'severity_level': 1,
      'tags': [],
      'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
      'created_at': 1572777087693,
      'disabled': False,
      'email': 'duaneferguson@hotmail.com',
      'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
      'is_anonymous': False,
      'name': 'Sarah Wood',
      'updated_at': None
    },
    ...
  ],
}
```

##### visitor_goes_online

Emitted to all staffs, whenever a visitor is connected.

Args:

`data` (Dict)

```
data={
  "visitor": { # The visitor who goes online
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  },
```

##### visitor_goes_offline

Emitted to all staffs, whenever a visitor is disconnected.

Args:

`data` (Dict)

```
data={
  "visitor": { # The visitor who goes online
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  },
```

##### remove_visitor_offline_chat

Emitted only when a visitor sends new messages, while his last chat is in offline unclaimed chats.

This is to avoid a chat existing on both offline and online unclaimed chats.

Args:

`data` (Dict)

```
data={
  "visitor": { # Visitor
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  }
}
```

##### unclaimed_chat_to_offline

Emitted when a visitor having an unclaimed chat goes offline.

This is to notify the front-end to put the chat in offline unclaimed chats.

Args:

`data` (Dict)

```
data={
  "visitor": { # Visitor
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  }
}
```

##### staff_claim_chat

Broadcast to queue room, to remove the unclaimed chat from others' clients.

> **Notes**  
Key `next_offline_unclaimed_visitor` will be None if:  
- There are no more offline unclaimed visitors.  
- The claimed chat belongs to an *ONLINE* visitor.

Args:

`data` (Dict)

```
data={
  "staff": { # The staff who claims the chat
    "full_name": "Admin 1",
    "id": "cf6e9a7bdf434d71a0c12ae91ce95c3d",
    "organisation_id": "6e759fb3eaf6462e8c42cd8ae294d414",
    "email": "admin1",
    "display_name": null,
    "role_id": 3
  },
  "visitor": { # Chat + Visitor
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  },
  "next_offline_unclaimed_visitor": { # Or None
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  }
}
```

##### staff_join_room

Emit to the visitor's room, to let him know a staff has joined.

Args:

`data` (dict)

```
{
  "staff": {  # The staff's info - models.User
    "full_name": "Admin 1",
    "id": "cf6e9a7bdf434d71a0c12ae91ce95c3d",
    "organisation_id": "6e759fb3eaf6462e8c42cd8ae294d414",
    "email": "admin1",
    "display_name": null,
    "role_id": 3
  }
}
```

##### append_unclaimed_chats

When a visitor just opens the app and sends the first message, this event will be sent to *ALL* staffs, to append the chat to the `queue room` on their browsers.

Args:

`data` (dict)

```
data={
  "visitor": { # The visitor
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  },
  "contents": [<content>],  # `content` is a Dict
}
```

##### visitor_leave_queue

Emitted to all staffs to inform that the visitor has manually left the chat.

Args:

`data` (dict)

```
data={
  "user": { # The visitor
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  }
}
```

##### visitor_unclaimed_msg

This event is emitted to staffs if the visitor sends other messages after the first init one, while the chat is *NOT* yet claimed.

This is to update all the staffs of new incoming messages from the visitor.

Args:

`data` (dict)

```
data={
  "visitor": { # The visitor
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  },
  "content": <content>  # dict
}
```

##### visitor_send

For the staff serving the visitor to receive the visitor's messages.

Args:

`data` (dict):

```
data={
  "visitor": { # The visitor
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  },
  "content": content
}
```

##### visitor_leave

> This event is no longer sent  
as `visitor_leave_queue` is emitted to all staffs.



##### staff_goes_online

All staffs receive this event to be notified who has gone online.

Args:

`data` (dict)

```
data={
  "staff": {
    email: "agent1@gmail.com",
    created_at: 1572522995,
    full_name: "Agent 1",
    updated_at: null,
    id: "06274871777d40f387ab430da6b3aa08",
    display_name: null,
    organisation_id: "bd9c4046763440769e3af30197a2482e",
    disabled: false,
    role_id: 3,
  }
}
```

##### staff_goes_offline

All staffs receive this event to be notified who has gone online.

Args:

`data` (dict)

```
data={
  "staff": {
    email: "agent1@gmail.com",
    created_at: 1572522995,
    full_name: "Agent 1",
    updated_at: null,
    id: "06274871777d40f387ab430da6b3aa08",
    display_name: null,
    organisation_id: "bd9c4046763440769e3af30197a2482e",
    disabled: false,
    role_id: 3,
  }
}
```

##### staff_being_taken_over_chat

Let the staff (agent) and the visitor know that the staff has been kicked out, and a higher-level staff is taking over the chat.

Args:

`data` (dict)

```
data={
  "staff": {   # The supervisor / admin that takes over the chat
    email: "agent1@gmail.com",
    created_at: 1572522995,
    full_name: "Agent 1",
    updated_at: null,
    id: "06274871777d40f387ab430da6b3aa08",
    display_name: null,
    organisation_id: "bd9c4046763440769e3af30197a2482e",
    disabled: false,
    role_id: 3,
  },
  "visitor": { # The chat room
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  }
}
```

##### staff_being_added_to_chat

This event is sent to the chat room. So all the staffs and the visitor in the room will receive this event.

Args:

`data` (dict)

```
data={
  "staff": {   # The supervisor / admin that takes over the chat
    email: "agent1@gmail.com",
    created_at: 1572522995,
    full_name: "Agent 1",
    updated_at: null,
    id: "06274871777d40f387ab430da6b3aa08",
    display_name: null,
    organisation_id: "bd9c4046763440769e3af30197a2482e",
    disabled: false,
    role_id: 3,
  },
}
```

##### staff_being_removed_from_chat

This event is sent to the chat room. So all the staffs and the visitor in the room will receive this event.

Args:

`data` (dict)

```
data={
  "staff": {   # The supervisor / admin that takes over the chat
    email: "agent1@gmail.com",
    created_at: 1572522995,
    full_name: "Agent 1",
    updated_at: null,
    id: "06274871777d40f387ab430da6b3aa08",
    display_name: null,
    organisation_id: "bd9c4046763440769e3af30197a2482e",
    disabled: false,
    role_id: 3,
  },
}
```


#### 3.2.2. Supervisors + Admins

These events are for supervisors and admins to monitor the chats of agents.

##### staff_take_over_chat

Emitted to all supervisors/admins that the chat has been taken over.

Args:

`data` (dict)

```
data={
  "staff": {   # The supervisor / admin that takes over the chat
    email: "agent1@gmail.com",
    created_at: 1572522995,
    full_name: "Agent 1",
    updated_at: null,
    id: "06274871777d40f387ab430da6b3aa08",
    display_name: null,
    organisation_id: "bd9c4046763440769e3af30197a2482e",
    disabled: false,
    role_id: 3,
  },
  "visitor": {
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  }
}
```

##### agent_new_chat

This event is emitted to inform supervisors/admins that an agent has claimed a chat (a `staff_claim_chat` event of an agent has been emitted).

Args:

`data` (dict)

```
data={
  "staff": {
    email: "agent1@gmail.com",
    created_at: 1572522995,
    full_name: "Agent 1",
    updated_at: null,
    id: "06274871777d40f387ab430da6b3aa08",
    display_name: null,
    organisation_id: "bd9c4046763440769e3af30197a2482e",
    disabled: false,
    role_id: 3,
  },
  "visitor": {
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  },
  "contents": [
    {
      sender: null,
      updated_at: null,
      id: "37700da96bbc42258fae9c9bea28f277",
      content: {
        content: "Hello"
        timestamp: 1572526821849
      },
      chat_id: "9ef0178dce9e4b95aa01f48b6a447154",
      created_at: 1572526821,
      type_id: 1,
      sequence_num: 1,
    }
  ]
}
```

##### new_staff_msg_for_supervisor

Emitted when there is a new message sent by a **staff** in any chats.

Args:

`data` (dict)

```
data={
  "staff": {
    email: "agent1@gmail.com",
    created_at: 1572522995,
    full_name: "Agent 1",
    updated_at: null,
    id: "06274871777d40f387ab430da6b3aa08",
    display_name: null,
    organisation_id: "bd9c4046763440769e3af30197a2482e",
    disabled: false,
    role_id: 3,
  },
  "content": {
    content: "Yes ?",
    timestamp: 1572526840074,
  },
  "visitor": {
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  }
}
```

##### new_visitor_msg_for_supervisor

Emitted when there is a new message sent by a **visitor** in any chats.

Args:

`data` (dict)

```
data={
  "visitor": {
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  },
  "content": {
    content: "Good",
    timestamp: 1572526845416,
  }
}
```

##### staff_leave_chat_for_supervisor

Emitted when an **staff** has left a chat.

Args:

`data` (dict)

```
data={
  "staff": {
    email: "agent1@gmail.com",
    created_at: 1572522995,
    full_name: "Agent 1",
    updated_at: null,
    id: "06274871777d40f387ab430da6b3aa08",
    display_name: null,
    organisation_id: "bd9c4046763440769e3af30197a2482e",
    disabled: false,
    role_id: 3,
  },
  "visitor": {
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  }
}
```

##### visitor_leave_chat_for_supervisor

Emitted when a visitor has left a chat.

Args:

`data` (dict)

```
data={
  "visitor": {
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  }
}
```

##### chat_has_changed_priority_for_supervisor

Emitted to supervisors/admins when a staff has changed a chat's priority.

Args:

`data` (dict)

```
data={
  "staff": {
    email: "agent1@gmail.com",
    created_at: 1572522995,
    full_name: "Agent 1",
    updated_at: null,
    id: "06274871777d40f387ab430da6b3aa08",
    display_name: null,
    organisation_id: "bd9c4046763440769e3af30197a2482e",
    disabled: false,
    role_id: 3,
  },
  "visitor": { # The visitor whose priority has been changed
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68'},
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
  },
}
```

#### 3.2.3. Visitor

##### visitor_init

For the visitor on startup knows who the staff he is chatting with, in case a staff is chatting and the visitor goes online.

If no staffs is chatting, `staff` is `None`.

Args:

`data` (dict)

```
data={
  "staff": {  # or None
    "full_name": "Admin 1",
    "id": "cf6e9a7bdf434d71a0c12ae91ce95c3d",
    "organisation_id": "6e759fb3eaf6462e8c42cd8ae294d414",
    "email": "admin1",
    "display_name": null,
    "role_id": 3
  },
  "content": <content>,  # dict
}
```


##### staff_send

For the visitor to receive the messages from the serving staff in the room.

Args:

`data` (dict)

```
data={
  "staff": {  # The staff's info - models.User
    "full_name": "Admin 1",
    "id": "cf6e9a7bdf434d71a0c12ae91ce95c3d",
    "organisation_id": "6e759fb3eaf6462e8c42cd8ae294d414",
    "email": "admin1",
    "display_name": null,
    "role_id": 3
  },
  "content": <content>,  # dict
}
```

##### staff_leave

For the visitor to be notified about the staff having left the chat.

Args:

`data` (dict)

```
data={
  "staff": {  # The staff who left
    "full_name": "Admin 1",
    "id": "cf6e9a7bdf434d71a0c12ae91ce95c3d",
    "organisation_id": "6e759fb3eaf6462e8c42cd8ae294d414",
    "email": "admin1",
    "display_name": null,
    "role_id": 3
  },
}
```

##### visitor_room_exists

For the visitor on `connect`, to be notified that there is an ongoing session, and extra sessions are not allowed.

Args:

`data` (dict)

```
data={
  "visitor": {
    'severity_level': 1,
    'tags': [],
    'visitor_id': 'ac2d4a7d56af4a1eb3718327ade0be68',
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None
    "staff": {  # The chatting staff. This will be `0` if no staffs have claimed the chat
      "full_name": "Admin 1",
      "id": "cf6e9a7bdf434d71a0c12ae91ce95c3d",
      "organisation_id": "6e759fb3eaf6462e8c42cd8ae294d414",
      "email": "admin1",
      "display_name": null,
      "role_id": 3
    },
  },
}
```


### 4. Typing

#### user_typing_send

An user emits this event to back-end to inform the other person in the chat room that he is typing.

Args:

`data` (dict)

```
data={
  "visitor": <str>  # The visitor's ID
}
```

#### user_typing_receive

The person in the chat room will receive this event when the other person is typing.

Args:

`data` (dict)

```
data={
  "visitor": {  # The visitor of the chat room
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None,
  }
}
```

#### user_stop_typing_send

An user emits this event to back-end to inform the other person in the chat room that he has stopped typing.

Args:

`data` (dict)

```
data={
  "visitor": <str>  # The visitor's ID
}
```

#### user_stop_typing_receive

The person in the chat room will receive this event when the other person has stopped typing.

Args:

`data` (dict)

```
data={
  "visitor": {  # The visitor of the chat room
    'created_at': 1572777087693,
    'disabled': False,
    'email': 'duaneferguson@hotmail.com',
    'id': 'ac2d4a7d56af4a1eb3718327ade0be68', # Visitor ID
    'is_anonymous': False,
    'name': 'Sarah Wood',
    'updated_at': None,
  }
}
```
