//   var roomName = "{{ room_name }}";
//   var username = "{{ request.user.username }}";
window.APP = window.APP || {
  chatSocket: null,
  messageQueue: [],
  activeRoom: null,
  username: null,
  otherUser: null,
  typingTimeout: null,
};
function connectSocket() {
  const data = document.getElementById("chat-data");

  if (!data) {
    console.log("chat-data not found");
    return;
  }

  const roomName = data.dataset.room;
  const username = data.dataset.username;
  const otherUser = data.dataset.other;
  APP.username = username;
  APP.otherUser = otherUser;

  if (APP.activeRoom === roomName) {
    console.log("Already connected to this room");
    return;
  }

  if (APP.chatSocket) {
    const oldSocket = APP.chatSocket;

    oldSocket.onclose = () => {
      console.log("Old socket closed");

      openNewSocket(roomName); // we'll define this below
    };

    oldSocket.close();
    return;
  }

  openNewSocket(roomName);
}

function openNewSocket(roomName) {
  const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";

  APP.chatSocket = new WebSocket(
    protocol + window.location.host + "/ws/private/" + roomName + "/",
  );

  APP.chatSocket.onopen = function () {
    APP.activeRoom = roomName;

    console.log("Private socket connected:", roomName);

    while (APP.messageQueue.length > 0) {
      APP.chatSocket.send(APP.messageQueue.shift());
    }
  };
  const input = document.getElementById("messageInput");

  if (input) {
    input.onkeydown = function (e) {
      if (e.key === "Enter") {
        sendPrivateMessage();
      }
    };

    input.addEventListener("input", function () {
      if (APP.chatSocket && APP.chatSocket.readyState === WebSocket.OPEN) {
        APP.chatSocket.send(JSON.stringify({ typing: true }));
      }

      clearTimeout(APP.typingTimeout);

      APP.typingTimeout = setTimeout(() => {
        if (APP.chatSocket && APP.chatSocket.readyState === WebSocket.OPEN) {
          APP.chatSocket.send(JSON.stringify({ typing: false }));
        }
      }, 1000);
    });
  }

  APP.chatSocket.onmessage = function (e) {
    const data = JSON.parse(e.data);

    if (data.type === "message_edited") {
      console.log("EDIT EVENT RECEIVED:", data);

      const bubble = document.getElementById("msg-" + data.message_id);
      if (!bubble) return;

      if (bubble.dataset.deleted === "true") return;

      const textDiv = bubble.querySelector(".msg-text");

      textDiv.innerHTML = `
        ${data.message}
        <span class="text-gray-400 text-xs ml-1">(edited)</span>
    `;

      return;
    }

    if (data.type === "message_deleted") {
      const messageBox = document.getElementById("msg-" + data.message_id);
      if (!messageBox) return;
      messageBox.dataset.deleted = "true";

      if (messageBox) {
        // change text
        const text = messageBox.querySelector(".msg-text");
        text.innerHTML =
          "<i class='text-gray-400'>This message was deleted</i>";

        // remove buttons
        messageBox.querySelectorAll("button").forEach((btn) => btn.remove());

        // OPTIONAL → remove ticks
        const tick = messageBox.querySelector("[id^='tick-']");
        if (tick) tick.remove();
      }

      return;
    }

    //  TYPING
    if (data.type === "typing") {
      if (data.username !== APP.username) {
        document.getElementById("typing-indicator").innerText = data.typing
          ? data.username + " is typing..."
          : "";
        console.log(data.type);
      }

      return;
    }
    // ✅ PRESENCE
    if (data.type === "presence") {
      if (data.username === APP.otherUser) {
        document.getElementById("status-text").innerHTML = data.is_online
          ? '<span class="text-green-600">● Online</span>'
          : '<span class="text-gray-400">last seen just now</span>';
      }

      return;
    }

    if (data.type !== "private_message") return;

    // MESSAGE
    const messages = document.getElementById("messages");
    const isMe = data.username === APP.username;

    const wrapper = document.createElement("div");
    wrapper.className = `flex ${isMe ? "justify-end" : "justify-start"}`;

    wrapper.innerHTML = `
    <div id="msg-${data.message_id}"
         class="px-4 py-2 rounded-xl max-w-xs
         ${isMe ? "bg-green-300" : "bg-white"}">

        <!-- MESSAGE TEXT -->
        <div class="msg-text">
            ${data.message}
        </div>

        <!-- TIME + TICK + BUTTONS -->
        <div class="text-xs text-gray-600 flex justify-end gap-1 mt-1">

            ${new Date().toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}

            ${
              isMe
                ? `
                    <span id="tick-${data.message_id}">✔</span>

                    <button 
                        class="edit-btn text-blue-500 ml-1 text-xs"
                        data-id="${data.message_id}"
                        data-text="${data.message}">
                        Edit
                    </button>

                    <button onclick="deleteMessage(${data.message_id})"
                        class="text-red-500 ml-1 text-xs">
                        Delete
                    </button>
                  `
                : ""
            }

        </div>
    </div>
`;

    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;
  };

  APP.chatSocket.onclose = function () {
    console.log("Socket closed");
    APP.activeRoom = null;
  };
}

function sendPrivateMessage() {
  const input = document.getElementById("messageInput");
  const message = input.value.trim();

  if (!message) return;

  const payload = JSON.stringify({
    type: "message",
    message: message,
  });

  if (APP.chatSocket && APP.chatSocket.readyState === WebSocket.OPEN) {
    APP.chatSocket.send(payload);
    APP.chatSocket.send(JSON.stringify({ typing: false }));
  } else {
    APP.messageQueue.push(payload);
  }

  input.value = "";
}

function deleteMessage(messageId) {
  if (!APP.chatSocket) return;

  if (!confirm("Delete this message?")) return;

  if (APP.chatSocket && APP.chatSocket.readyState === WebSocket.OPEN) {
    APP.chatSocket.send(
      JSON.stringify({
        type: "delete",
        message_id: messageId,
      }),
    );
  } else {
    console.log("Socket not connected");
  }
}

function editMessage(id) {
  console.log("FUNCTION STARTED");

  const bubble = document.getElementById("msg-" + id);
  console.log("bubble:", bubble); // ⭐ ADD
  if (!bubble) return;

  const oldText = bubble.querySelector(".msg-text").innerText;
  console.log("textDiv:", oldText);

  const newText = prompt("Edit message", oldText);

  if (!newText || !newText.trim()) return;

  console.log("SENDING EDIT:", id, newText);

  APP.chatSocket.send(
    JSON.stringify({
      type: "edit",
      message_id: id,
      message: newText.trim(),
    }),
  );
}

// if(input){

//   input.onkeydown = function(e){
//       if(e.key === "Enter"){
//           sendPrivateMessage();
//       }
//   };

//   input.addEventListener("input", function () {

//       if (APP.chatSocket && APP.chatSocket.readyState === WebSocket.OPEN) {
//           APP.chatSocket.send(JSON.stringify({ typing: true }));
//       }

//       clearTimeout(typingTimeout);

//       typingTimeout = setTimeout(() => {

//           if (APP.chatSocket && APP.chatSocket.readyState === WebSocket.OPEN) {
//               APP.chatSocket.send(JSON.stringify({ typing: false }));
//           }

//       }, 1000);
//   });
// }
// EDIT CLICK HANDLER
document.addEventListener("click", function (e) {
  const editBtn = e.target.closest(".edit-btn");
  if (!editBtn) return;

  e.preventDefault();
  e.stopPropagation();

  const id = editBtn.dataset.id;
  console.log("EDIT CLICKED:", id);

  const bubble = document.getElementById("msg-" + id);
  if (!bubble) {
    console.log("Bubble not found");
    return;
  }

  const textDiv = bubble.querySelector(".msg-text");
  const oldText = textDiv.innerText;

  console.log("OLD TEXT:", oldText);

  const newText = prompt("Edit message", oldText);
  if (newText === null) return;
  if (!newText.trim()) return;

  console.log("SENDING EDIT:", id, newText);

  APP.chatSocket.send(
    JSON.stringify({
      type: "edit",
      message_id: id,
      message: newText.trim(),
    }),
  );
});

const messagesDiv = document.getElementById("messages");
if (messagesDiv) {
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}
