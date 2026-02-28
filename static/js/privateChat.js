window.APP = window.APP || {
  privateSocket: null,
  messageQueue: [],
  activeRoom: null,
  username: null,
  otherUser: null,
  typingTimeout: null,
  replyingTo: null 
};

function openCxModal(content) {
  const existing = document.getElementById("cx-modal");
  if (existing) existing.remove();

  const modal = document.createElement("div");
  modal.id = "cx-modal";
  modal.className =
    "fixed inset-0 bg-black/20 backdrop-blur-sm flex items-center justify-center z-50";
  modal.innerHTML = `
    <div class="bg-white/95 w-[92vw] max-w-sm rounded-2xl shadow-2xl border border-white/60 p-5">
      ${content}
    </div>
  `;

  modal.addEventListener("click", (e) => {
    if (e.target === modal) modal.remove();
  });

  document.body.appendChild(modal);
  return modal;
}

function openCxConfirm({ title, message, confirmText, onConfirm }) {
  const modal = openCxModal(`
    <h3 class="text-lg font-semibold text-slate-900">${title}</h3>
    <p class="mt-2 text-sm text-slate-600">${message}</p>
    <div class="mt-5 flex gap-2 justify-end">
      <button id="cx-cancel" class="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-sm">
        Cancel
      </button>
      <button id="cx-confirm" class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm">
        ${confirmText}
      </button>
    </div>
  `);

  modal.querySelector("#cx-cancel").onclick = () => modal.remove();
  modal.querySelector("#cx-confirm").onclick = () => {
    modal.remove();
    if (onConfirm) onConfirm();
  };
}

function openCxPrompt({ title, message, value, confirmText, onConfirm }) {
  const modal = openCxModal(`
    <h3 class="text-lg font-semibold text-slate-900">${title}</h3>
    <p class="mt-2 text-sm text-slate-600">${message}</p>
    <input id="cx-input" class="mt-3 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-4 focus:ring-emerald-200/60 focus:border-emerald-400" />
    <div class="mt-5 flex gap-2 justify-end">
      <button id="cx-cancel" class="px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-slate-200 text-sm">
        Cancel
      </button>
      <button id="cx-confirm" class="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white text-sm">
        ${confirmText}
      </button>
    </div>
  `);

  const input = modal.querySelector("#cx-input");
  input.value = value || "";
  input.focus();

  const submit = () => {
    const text = input.value.trim();
    if (!text) return;
    modal.remove();
    if (onConfirm) onConfirm(text);
  };

  modal.querySelector("#cx-cancel").onclick = () => modal.remove();
  modal.querySelector("#cx-confirm").onclick = submit;
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter") submit();
  });
}
function connectSocket() {
  const data = document.getElementById("chat-data");

  if (!data) {
    console.log("chat-data not found");
    return;
  }

  const roomName = data.dataset.room;
  const roomId = data.dataset.roomId;
  const username = data.dataset.username;
  const otherUser = data.dataset.other;
  APP.username = username;
  APP.otherUser = otherUser;
  APP.activeRoomId = roomId;

  if (APP.activeRoom === roomName) {
    console.log("Already connected to this room");
    return;
  }

  if (APP.privateSocket) {
    const oldSocket = APP.privateSocket;

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

  APP.privateSocket = new WebSocket(
    protocol + window.location.host + "/ws/private/" + roomName + "/",
  );

  APP.privateSocket.onopen = function () {
    APP.activeRoom = roomName;

    console.log("Private socket connected:", roomName);

    while (APP.messageQueue.length > 0) {
      APP.privateSocket.send(APP.messageQueue.shift());
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
      if (APP.privateSocket && APP.privateSocket.readyState === WebSocket.OPEN) {
        APP.privateSocket.send(JSON.stringify({ typing: true }));
      }

      clearTimeout(APP.typingTimeout);

      APP.typingTimeout = setTimeout(() => {
        if (APP.privateSocket && APP.privateSocket.readyState === WebSocket.OPEN) {
          APP.privateSocket.send(JSON.stringify({ typing: false }));
        }
      }, 1000);
    });
  }

  APP.privateSocket.onmessage = function (e) {
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

    if (data.type === "reaction_event") {
      const box = document.getElementById("reaction-" + data.message_id);
      if (!box) return;

      box.innerHTML = "";

      Object.entries(data.reactions).forEach(([emoji, users]) => {
        const span = document.createElement("span");
        span.className =
          "bg-gray-200 px-2 py-1 rounded-full text-sm mr-1 cursor-pointer";
        span.innerHTML = `
             <span class="mr-1">${emoji}</span>
             <span class="text-xs">${users.length}</span>`;

        span.onclick = () => {
          console.log("Popup clicked", emoji, users);
          showReactionPopup(emoji, users);
        };

        box.appendChild(span);
      });
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
         class="px-4 py-3 rounded-2xl max-w-[75%] sm:max-w-[65%] shadow-sm
         ${isMe ? "bg-emerald-600 text-white" : "bg-white border border-slate-200/70 text-slate-900"}">

           ${data.reply_to ? `
            <div class="reply-preview bg-emerald-50 border-l-4 border-emerald-500 
                        px-2 py-1 mb-2 text-xs cursor-pointer text-slate-700"
                 data-reply-id="${data.reply_to.id}">

                <div class="font-semibold text-slate-700">
                    ${data.reply_to.username === APP.username ? "You" : data.reply_to.username}
                </div>

                <div class="text-slate-600 truncate">
                    ${data.reply_to.content}
                </div>
            </div>
        ` : ""}

        <!-- MESSAGE TEXT -->
        <div class="msg-text text-[15px] leading-6">
            ${data.message}
        </div>

        <!-- TIME + TICK + BUTTONS -->
        <div class="text-[11px] text-slate-500 flex justify-end gap-1 mt-2">

            ${new Date().toLocaleTimeString([], {
              hour: "2-digit",
              minute: "2-digit",
            })}

            ${
              isMe
                ? `
                    <span id="tick-${data.message_id}">✔</span>
                  `
                : ""
            }

            <button 
                class="reply-btn ml-1 text-[11px] ${isMe ? "text-emerald-100/90" : "text-slate-500"}"
                data-id="${data.message_id}"
                data-text="${data.message.replace(/\"/g, "&quot;")}"
                data-user="${isMe ? "You" : data.username}">
                Reply
            </button>

            ${
              isMe
                ? `
                    <button 
                        class="edit-btn text-blue-200 ml-1 text-[11px]"
                        data-id="${data.message_id}"
                        data-text="${data.message}">
                        Edit
                    </button>

                    <button onclick="deleteMessage(${data.message_id})"
                        class="text-red-200 ml-1 text-[11px]">
                        Delete
                    </button>
                  `
                : ""
            }

        </div>
    </div>
`;
console.log("PRIVATE MESSAGE EVENT:", data);


    messages.appendChild(wrapper);
    messages.scrollTop = messages.scrollHeight;

    if (window.bumpRoom && APP.activeRoomId) {
      window.bumpRoom(APP.activeRoomId);
    }
  };

  APP.privateSocket.onclose = function () {
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
    reply_to: APP.replyingTo
  });

  if (APP.privateSocket && APP.privateSocket.readyState === WebSocket.OPEN) {
    APP.privateSocket.send(payload);
    APP.privateSocket.send(JSON.stringify({ typing: false }));
  } else {
    APP.messageQueue.push(payload);
  }

  if (window.bumpRoom && APP.activeRoomId) {
    window.bumpRoom(APP.activeRoomId);
  }

  input.value = "";
}

function deleteMessage(messageId) {
  if (!APP.privateSocket) return;
  openCxConfirm({
    title: "Delete message?",
    message: "This will delete it for everyone.",
    confirmText: "Delete",
    onConfirm: () => {
      if (APP.privateSocket && APP.privateSocket.readyState === WebSocket.OPEN) {
        APP.privateSocket.send(
          JSON.stringify({
            type: "delete",
            message_id: messageId,
          }),
        );
      } else {
        console.log("Socket not connected");
      }
    }
  });
}

function editMessage(id) {
  console.log("FUNCTION STARTED");

  const bubble = document.getElementById("msg-" + id);
  console.log("bubble:", bubble); // ⭐ ADD
  if (!bubble) return;

  const oldText = bubble.querySelector(".msg-text").innerText;
  console.log("textDiv:", oldText);

  openCxPrompt({
    title: "Edit message",
    message: "Update your message below.",
    value: oldText,
    confirmText: "Save",
    onConfirm: (newText) => {
      console.log("SENDING EDIT:", id, newText);
      APP.privateSocket.send(
        JSON.stringify({
          type: "edit",
          message_id: id,
          message: newText.trim(),
        }),
      );
    }
  });
}

function sendReaction(messageId, emoji) {
  if (!APP.privateSocket) return;
  APP.privateSocket.send(
    JSON.stringify({
      type: "reaction",
      message_id: messageId,
      emoji: emoji,
    }),
  );
  const menu = document.getElementById("menu-" + messageId);
  if (menu) {
    menu.classList.add("hidden");
  }
}

function showReactionPopup(emoji, users) {
  let sheet = document.getElementById("reaction-sheet");

  if (sheet) sheet.remove();

  sheet = document.createElement("div");
  sheet.id = "reaction-sheet";
  sheet.className =
    "fixed inset-0 flex items-end bg-black bg-opacity-30 backdrop-blur-sm z-50";

  sheet.innerHTML = `
    <div class="bg-white w-full rounded-t-3xl p-4 animate-slideUp max-h-[60vh] overflow-y-auto">
      
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-2 text-lg font-semibold">
          <span class="text-2xl">${emoji}</span>
          <span>Reactions</span>
        </div>
        <button onclick="document.getElementById('reaction-sheet').remove()" 
                class="text-slate-500 text-sm">
          Close
        </button>
      </div>

      <div class="space-y-3">
       ${users.map((user) => `
            <div class="flex items-center gap-3">

              <img src="${user.avatar}" 
                class="w-10 h-10 rounded-full object-cover" />
  
              <span class="text-slate-800">
                ${user.username === APP.username ? "You" : user.username}
              </span>

            </div>
        `).join("")}
      </div>

    </div>
  `;
    console.log("Users:", users);


  sheet.addEventListener("click", function (e) {
    if (e.target === sheet) {
      sheet.remove();
    }
  });

  document.body.appendChild(sheet);
}

function clearReply() {
  APP.replyingTo = null;
  document.getElementById("reply-preview").classList.add("hidden");
}
function scrollToMessage(id) {
  const target = document.getElementById("msg-" + id);
  if (!target) return;

  target.scrollIntoView({
    behavior: "smooth",
    block: "center"
  });

  target.classList.add("ring-2", "ring-green-400");

  setTimeout(() => {
    target.classList.remove("ring-2", "ring-green-400");
  }, 1500);
}

function showBlockedBanner(show){
  const banner = document.getElementById("blocked-banner");
  const input = document.getElementById("messageInput");

  if(show){
    banner.classList.remove("hidden");
    input.disabled = true;
  } else {
    banner.classList.add("hidden");
    input.disabled = false;
  }
}

function getCSRFToken() {
  return document.cookie
    .split("; ")
    .find(row => row.startsWith("csrftoken"))
    ?.split("=")[1];
}

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

  openCxPrompt({
    title: "Edit message",
    message: "Update your message below.",
    value: oldText,
    confirmText: "Save",
    onConfirm: (newText) => {
      console.log("SENDING EDIT:", id, newText);
      APP.privateSocket.send(
        JSON.stringify({
          type: "edit",
          message_id: id,
          message: newText.trim(),
        }),
      );
    }
  });
});

let pressTimer;

document.addEventListener("mousedown", function (e) {
  const bubble = e.target.closest("[id^='msg-']");
  if (!bubble) return;

  pressTimer = setTimeout(() => {
    const id = bubble.id.split("-")[1];
    const menu = document.getElementById("menu-" + id);

    if (!menu) return;

    document.querySelectorAll(".reaction-menu").forEach((m) => {
      if (m !== menu) m.classList.add("hidden");
    });

    menu.classList.remove("hidden");
  }, 500); // 500ms hold
});

document.addEventListener("mouseup", function () {
  clearTimeout(pressTimer);
});

document.addEventListener("click", function (e) {
  const replyBtn = e.target.closest(".reply-btn");
  if (!replyBtn) return;

  const id = replyBtn.dataset.id;
  const text = replyBtn.dataset.text;
  const user = replyBtn.dataset.user;

  APP.replyingTo = id;

  document.getElementById("reply-user").innerText = user;
  document.getElementById("reply-text").innerText = text;
  document.getElementById("reply-preview").classList.remove("hidden");
});

document.addEventListener("click", function (e) {

  const replyBlock = e.target.closest(".reply-preview");
  if (!replyBlock) return;

  const replyId = replyBlock.dataset.replyId;
  if (!replyId) return;

  scrollToMessage(replyId);

});

document.addEventListener("click", async function (e) {
  const btn = e.target.closest("#block-btn");
  if (!btn) return;

  const username = APP.otherUser;

  try {
    const res = await fetch(`/accounts/block/${username}/`, {
      method: "POST",
      headers: {
        "X-CSRFToken": getCSRFToken(),
      },
    });

    if (!res.ok) throw new Error("Request failed");

    const result = await res.json();
    console.log("BLOCK RESPONSE:", result);

    if (result.status === "blocked") {
      btn.innerText = "Unblock";
      showBlockedBanner(true);
    } else {
      btn.innerText = "Block";
      showBlockedBanner(false);
    }

  } catch (err) {
    console.error("Block error:", err);
  }
});


document.addEventListener("DOMContentLoaded", function(){
    if(window.IS_BLOCKED){
        showBlockedBanner(true);
        document.getElementById("block-btn").innerText = "Unblock";
    }
});



const messagesDiv = document.getElementById("messages");
if (messagesDiv) {
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}
