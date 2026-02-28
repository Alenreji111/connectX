# Chat Index Template (ConnectX)

File: `chat/templates/chat/index.html`

## Purpose
This template renders the main chat UI shell for ConnectX. It provides the left sidebar with rooms, search, and group creation, and a right-side chat panel that loads conversations dynamically. It also wires up notification updates, profile viewing, and group creation modals.

## Key Dependencies
- Django template tags: `{% load static %}` and `{% url %}`.
- Tailwind CSS via CDN: `https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4`.
- Static JavaScript:
  - `{% static 'js/privateChat.js' %}`
  - `{% static 'js/groupChat.js' %}`

## Expected Context
The template expects these variables to be available:

- `rooms`: iterable of room objects.
  - `room.id`: numeric or string identifier.
  - `room.is_group`: boolean.
  - `room.name`: group name (when `is_group` is true).
  - `room.avatar` with `room.avatar.url` (group avatar; optional).
  - `room.other_user`: user object for private chats.
    - `room.other_user.id`
    - `room.other_user.username`
    - `room.other_user.profile.avatar` with `name` and `url`.
  - `room.last_message`: preview text (optional; defaults to `Start chatting...`).
- `request.user.contacts.all`: iterable of relations for group creation.
  - `relation.contact.id`
  - `relation.contact.username`

## URL Hooks
The template references these URL names or routes:

- `accounts:profile` (Profile button in header).
- `search_users` (GET search form action).
- `group_chat` (group room view; expects `room.id`).
- `private_chat` (private room view; expects `room.other_user.id`).
- `create_group` (POST create group).
- `/accounts/profile/<id>/` (profile modal JSON fetch; returns `username`, `bio`, `avatar`).
- WebSocket endpoint: `/ws/notify/`.

## UI Structure
- **Sidebar** (left):
  - Header with app name and Profile link.
  - Search form.
  - Rooms list with avatar fallback behavior.
  - Floating “Create Group” button.
- **Chat Panel** (right):
  - Placeholder welcome state.
- **Modals**:
  - Group creation modal.
  - Profile view modal.

## Client-Side Behavior
### Room Selection
- `openChat(url)` closes any existing sockets tracked on `window.APP` (`privateSocket` and `groupSocket`).
- It resets `APP.activeRoom` and calls `loadChat(url)`.
- `loadChat(url)` fetches HTML and injects it into `#chat-container`, then calls `connectSocket()` and `connectGroupSocket()` if present.

### Notification WebSocket
- Connects to `ws(s)://<host>/ws/notify/`.
- Handles messages of type:
  - `unread_update`: moves room to top and updates unread badge.
  - `delivered`: updates message tick to `✔✔`.
  - `read`: updates tick to `✔✔` and colors it blue.

### Profile Modal
- Clicking elements with `chat-avatar` or `chat-username` triggers `openProfile(userId)`.
- Fetches `/accounts/profile/<id>/` and displays username, bio, and avatar in the modal.

### Group Modal
- `openGroupModal()`/`closeGroupModal()` toggle visibility.
- Form submits `group_name` and selected `members` (checkbox values are contact IDs).

## Notes and Assumptions
- The room list’s click handler uses inline `onclick` with `{% url %}` to determine group vs private routes.
- `window.APP` is assumed to exist and be managed by the chat JS modules.
- The template uses Tailwind classes directly; no local CSS files are referenced here.
