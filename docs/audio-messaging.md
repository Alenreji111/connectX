# Audio Messaging (ConnectX)

This document explains how audio messaging was added for both private and group chats, including storage, security, and real‑time delivery.

## Overview
Audio messages are stored as files on the server (local filesystem) using Django’s `FileField`. Messages are delivered in real time over WebSockets, and the audio is streamed only to users who are members of the room.

## Data Model
- `chat.models.Message` now includes:
  - `audio`: `FileField(upload_to="chat_audio/", null=True, blank=True)`
- Text messages use `content`. Audio messages set `content` to a placeholder (currently `"🎤 Audio"`) and attach the file in `audio`.

Migration:
- `chat/migrations/0002_message_audio.py`

## Storage Choice
- **Local file storage** is used (no external buckets), which is suitable for a college project.
- Files are saved under `media/chat_audio/`.

## Security Model
Audio access is restricted to room members.

- The audio file is served through a secured view:
  - `GET /message-audio/<message_id>/`
- The view checks:
  - The message exists and has an audio file.
  - The requesting user is in the message’s room.
  - Otherwise returns `403` or `404`.

This ensures only intended users can access the audio.

## Server Endpoints
**Private chat upload**
- `POST /private-audio/<user_id>/`
- Validates:
  - Method is POST
  - Audio file present
  - Room exists
  - Sender is not blocked by receiver
- Creates a `Message` with `audio` and broadcasts via WebSocket.

**Group chat upload**
- `POST /group/<room_id>/audio/`
- Validates:
  - Method is POST
  - Audio file present
  - User is a member of the room
- Creates a `Message` with `audio` and broadcasts via WebSocket.

**Audio streaming**
- `GET /message-audio/<message_id>/`
- Streams the file to authorized members.

## Real‑Time Delivery
WebSocket events now include `audio_url` for audio messages:

- **Private:** broadcast on `room_<room_id>`
- **Group:** broadcast on `group_<room_id>`

Clients render an `<audio controls>` element when `audio_url` is present.

## UI Changes
### Private Chat
- A mic button (`🎤`) was added to the input bar.
- Recording indicator appears while recording (red dot + “Recording”).
- Audio messages render a player instead of text.
- Edit button is hidden for audio messages.

### Group Chat
- Same mic button and indicator in group input bar.
- Audio messages render a player.
- Edit button hidden for audio messages.

## Client Recording Flow
Implemented with the browser’s `MediaRecorder`:

1. User taps mic → start recording.
2. Recorder collects chunks.
3. On stop, a blob is created and uploaded via `fetch` + `FormData`.
4. Server creates a message and broadcasts the audio URL.

## Real‑Time Last Message Updates
When an audio message is sent, the chat list last‑message preview is updated in real time by broadcasting a `last_message` event to all room members.

## Files Changed
Key files involved:

- `chat/models.py` (audio field)
- `chat/migrations/0002_message_audio.py`
- `chat/views.py` (upload + stream endpoints)
- `chat/urls.py` (audio routes)
- `chat/consumers.py` (audio URL in websocket payload)
- `static/js/privateChat.js` (record/send audio, render player)
- `static/js/groupChat.js` (record/send audio, render player)
- `chat/templates/chat/private_chat.html`
- `chat/templates/chat/group_chat.html`

## Limitations / Notes
- Files are stored locally; not suitable for large scale or multi‑server deployment.
- No length or size limits enforced yet (can be added).
- Audio editing is intentionally disabled.

## How To Migrate
After pulling the changes, run:

```bash
python manage.py migrate
```

## Testing Checklist
- Record and send audio in private chat.
- Record and send audio in group chat.
- Confirm non‑members cannot access audio URL.
- Confirm audio message shows in chat list preview.
