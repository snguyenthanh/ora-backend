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

### 3.2. Receive

#### staff_init

The staff will receive a list of all unclaimed chats
right after connecting to the server.

Args:

`data` (List[Dict]): The data of the event is a list of unclaimed chats to show on front-end.

Each chat in unclaimed_chats has the format:
```
{
		"user": { # The visitor
				"id": "cfd7f4553c9a45b1a81a2384bfcb13a5"
        "name": "Visitor 1",
        "email": "visitor1"
    },
		"room": { # A Chat object. Refers to models.Chat
				"id": "qwkelqwkleqwlken123123b12312l3kn",
				"visitor_id": "cfd7f4553c9a45b1a81a2384bfcb13a5",
				"tags": [],
				"severity_level": 0,
		},
		"contents": [content] # A list of `ChatMessage.content`, format decided by front-end
}
```

#### staff_claim_chat

Broadcast to queue room, to remove the unclaimed chat from others' clients.

Args:

`data` (Dict)

```
data={
	"user": { # The visitor
		"id": "cfd7f4553c9a45b1a81a2384bfcb13a5"
		"name": "Visitor 1",
		"email": "visitor1"
	},
	"room": { # A Chat object. Refers to models.Chat
			"id": "qwkelqwkleqwlken123123b12312l3kn",
			"visitor_id": "cfd7f4553c9a45b1a81a2384bfcb13a5",
			"tags": [],
			"severity_level": 0,
	},
}
```

#### staff_join_room

Emit to the visitor's room, to let him know a staff has joined.

Args:

`data` (dict)

```
{
	"user": {  # The staff's info - models.User
		"full_name": "Admin 1",
		"id": "cf6e9a7bdf434d71a0c12ae91ce95c3d",
		"organisation_id": "6e759fb3eaf6462e8c42cd8ae294d414",
		"email": "admin1",
		"display_name": null,
		"role_id": 3
	}
}
```

#### append_unclaimed_chats

When a visitor just opens the app and sends the first message, this event will be sent to *ALL* staffs, to append the chat to the `queue room` on their browsers.

Args:

`data` (dict)

```
data={
	"user": { # The visitor
		"id": "cfd7f4553c9a45b1a81a2384bfcb13a5"
		"name": "Visitor 1",
		"email": "visitor1"
	},
	"room": { # A Chat object. Refers to models.Chat
			"id": "qwkelqwkleqwlken123123b12312l3kn",
			"visitor_id": "cfd7f4553c9a45b1a81a2384bfcb13a5",
			"tags": [],
			"severity_level": 0,
	},
	"contents": [<content>],	# `content` is a Dict
}
```

#### visitor_unclaimed_msg

This event is emitted to staffs if the visitor sends other messages after the first init one, while the chat is *NOT* yet claimed.

This is to update all the staffs of new incoming messages from the visitor.

Args:
`data` (dict)

```
data={
	"user": { # The visitor
		"id": "cfd7f4553c9a45b1a81a2384bfcb13a5"
		"name": "Visitor 1",
		"email": "visitor1"
	},
	"content": <content>	# dict
}
```

#### visitor_send

For the staff serving the visitor to receive the visitor's messages.

Args:

`data` (dict):

```
data={
	"user": { # The visitor
		"id": "cfd7f4553c9a45b1a81a2384bfcb13a5"
		"name": "Visitor 1",
		"email": "visitor1"
	},
	"content": content
}
```

#### staff_send

For the visitor to receive the messages from the serving staff in the room.

Args:

`data` (dict)

```
data={
	"user": {  # The staff's info - models.User
		"full_name": "Admin 1",
		"id": "cf6e9a7bdf434d71a0c12ae91ce95c3d",
		"organisation_id": "6e759fb3eaf6462e8c42cd8ae294d414",
		"email": "admin1",
		"display_name": null,
		"role_id": 3
	},
	"content": <content>,	# dict
}
```

#### staff_leave

For the visitor to be notified about the staff having left the chat.

Args:

`data` (dict)

```
data={
	"user": {	# The staff who left
		"full_name": "Admin 1",
		"id": "cf6e9a7bdf434d71a0c12ae91ce95c3d",
		"organisation_id": "6e759fb3eaf6462e8c42cd8ae294d414",
		"email": "admin1",
		"display_name": null,
		"role_id": 3
	},
}
```

#### visitor_leave

For staff to be notified which visitor has left the chat.

Args:

`data` (dict)

```
data={
	"user": { # The visitor who left
		"id": "cfd7f4553c9a45b1a81a2384bfcb13a5"
		"name": "Visitor 1",
		"email": "visitor1"
	},
}
```
