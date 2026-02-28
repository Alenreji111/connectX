window.APP = window.APP || {
    groupSocket: null,
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

function connectGroupSocket(){

    const data = document.getElementById("group-chat-data");
    if(!data) return;

    const roomId = data.dataset.roomId;
    const currentUserId = data.dataset.userId;
    APP.activeRoomId = roomId;
    APP.groupRoomId = roomId;

    const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";

    APP.groupSocket = new WebSocket(
        protocol + window.location.host + "/ws/group/" + roomId + "/"
    );

    APP.groupSocket.onopen = function(){

        console.log("✅ Group socket connected");

        const box = document.getElementById("messages");
        if(box){
            box.scrollTop = box.scrollHeight;
        }

        // ✅ attach listener AFTER DOM exists
        const input = document.getElementById("messageInput");

        if(input){
            input.addEventListener("keydown", function(e){
                if(e.key === "Enter"){
                    sendGroupMessage();
                }
            });
        }
    };

    APP.groupSocket.onmessage = function(e){

        const data = JSON.parse(e.data);

        // DELETE
        if(data.type === "deleted"){

            const bubble = document.getElementById("msg-" + data.message_id);
            if(!bubble) return;
        
            bubble.classList.add("opacity-50", "transition", "duration-300");

            setTimeout(() => {
                bubble.querySelector(".msg-text").innerHTML =
                    "<i class='text-gray-400'>This message was deleted</i>";
            }, 200);

        
            const controls = bubble.querySelector(".controls");
            if(controls){
                controls.innerHTML = "";
            }
        
            return;
        }
        
        if(data.type === "deleted_for_me"){

            const bubble = document.getElementById("msg-" + data.message_id);
            if(!bubble) return;
        
            bubble.classList.add("opacity-0", "transition", "duration-300");
        
            setTimeout(() => {
                bubble.remove();
            }, 300);
        
            return;
        }        

        // EDIT
        if(data.type === "edited"){
            const bubble = document.getElementById("msg-" + data.message_id);
            if(!bubble) return;
            const textDiv = bubble.querySelector(".msg-text");

            textDiv.innerHTML = `
                ${data.message}
                <span class="text-gray-400 text-xs ml-1">(edited)</span>
            `;
            return;
        }
        
        if(data.type === "role_updated"){
            location.reload();
            return;
        }
        
        if(data.type === "member_added"){
            location.reload();   // simple refresh for now
            return;
        }

        // ONLY HANDLE GROUP MESSAGE
        if(data.type !== "group_message") return;

        const box = document.getElementById("messages");
        if(!box) return;

        const isMe = data.sender_id == currentUserId;

        const messageHTML = `
            <div class="flex ${isMe ? "justify-end" : "justify-start"}">
                <div id="msg-${data.message_id}" 
                     data-audio="${data.audio_url ? "true" : "false"}"
                     class="relative px-4 py-3 rounded-2xl max-w-[75%] sm:max-w-[65%] shadow-sm ${
                        isMe ? "bg-emerald-600 text-white" : "bg-white border border-slate-200/70 text-slate-900"
                     }">

                    ${!isMe ? `
                        <div class="text-xs font-semibold text-emerald-700 flex items-center gap-2">
                            <span class="chat-username cursor-pointer" data-user-id="${data.sender_id}">
                                ${data.sender_display || data.username}
                            </span>
                    
                            ${data.role === "creator" ? 
                                "<span class='text-[10px] bg-purple-500 text-white px-2 py-0.5 rounded-full'>Creator</span>" 
                            : data.role === "admin" ? 
                                "<span class='text-[10px] bg-blue-500 text-white px-2 py-0.5 rounded-full'>Admin</span>" 
                            : ""}
                        </div>
                    ` : ""}

                    ${data.reply_to ? `
                        <div class="reply-preview bg-emerald-50 text-xs p-2 rounded-lg mb-1 border-l-4 border-emerald-500 cursor-pointer text-slate-700"
                             data-reply-id="${data.reply_to.id}">
                            <strong>
                                ${data.reply_to.username === APP.username ? "You" : data.reply_to.username}
                            </strong>
                            <div class="truncate">
                                ${data.reply_to.content}
                            </div>
                        </div>
                    ` : ""}

                    <div class="msg-text text-[15px] leading-6">
                        ${data.audio_url ? `
                          <audio controls class="w-56">
                            <source src="${data.audio_url}">
                          </audio>
                        ` : data.message}
                    </div>

                    <div class="text-[11px] text-slate-500 mt-2">now</div>

                    <button class="reply-btn text-[11px] mt-1 ${isMe ? "text-emerald-100/90" : "text-slate-500"}"
                        data-id="${data.message_id}"
                        data-text="${data.message.replace(/\"/g, "&quot;")}"
                        data-user="${data.sender_display || data.username}">
                        Reply
                    </button>

                    ${isMe ? `
                    ${data.audio_url ? "" : `
                    <button onclick="groupEditMessage(${data.message_id}, '${data.message.replace(/'/g, "\\'")}')"
                            class="text-blue-200 text-[11px] ml-2">
                      Edit
                    </button>
                    `}
            
                    <button onclick="groupDeleteMessage(${data.message_id})"
                            class="text-red-200 text-[11px] ml-2">
                      Delete
                    </button>
                      ` : ""}

                </div>
            </div>
        `;

        box.insertAdjacentHTML("beforeend", messageHTML);
        box.scrollTop = box.scrollHeight;

        if (window.bumpRoom && APP.activeRoomId) {
            window.bumpRoom(APP.activeRoomId);
        }
    };
}

let groupRecorder = null;
let groupChunks = [];
let isGroupRecording = false;

function getCSRFToken() {
    return document.cookie
        .split("; ")
        .find(row => row.startsWith("csrftoken"))
        ?.split("=")[1];
}

window.toggleGroupRecording = async function () {
    const btn = document.getElementById("record-btn");
    const indicator = document.getElementById("record-indicator");
    if (!btn) return;

    if (!isGroupRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            groupRecorder = new MediaRecorder(stream);
            groupChunks = [];

            groupRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) groupChunks.push(e.data);
            };

            groupRecorder.onstop = () => {
                const blob = new Blob(groupChunks, { type: groupRecorder.mimeType || "audio/webm" });
                stream.getTracks().forEach((t) => t.stop());
                sendGroupAudio(blob);
            };

            groupRecorder.start();
            isGroupRecording = true;
            btn.classList.add("bg-emerald-600", "text-white");
            if (indicator) indicator.classList.remove("hidden");
        } catch (err) {
            console.error("Mic permission error:", err);
        }
    } else {
        if (groupRecorder && groupRecorder.state !== "inactive") {
            groupRecorder.stop();
        }
        isGroupRecording = false;
        btn.classList.remove("bg-emerald-600", "text-white");
        if (indicator) indicator.classList.add("hidden");
    }
};

function sendGroupAudio(blob) {
    if (!APP.groupRoomId) return;
    const formData = new FormData();
    formData.append("audio", blob, "audio.webm");

    fetch(`/group/${APP.groupRoomId}/audio/`, {
        method: "POST",
        headers: {
            "X-CSRFToken": getCSRFToken(),
        },
        body: formData,
    }).catch((err) => {
        console.error("Audio upload error:", err);
    });
}


window.sendGroupMessage = function(){

    const input = document.getElementById("messageInput");
    if(!input) return;

    const message = input.value.trim();
    if(!message) return;

    if(APP.groupSocket && APP.groupSocket.readyState === WebSocket.OPEN){
        APP.groupSocket.send(JSON.stringify({
            message: message,
            reply_to: APP.replyingTo
        }));
    }

    if (window.bumpRoom && APP.activeRoomId) {
        window.bumpRoom(APP.activeRoomId);
    }

    input.value = "";
    clearReply();
};
window.groupDeleteMessage = function(messageId){

  let modal = document.getElementById("delete-modal");
  if(modal) modal.remove();

  modal = document.createElement("div");
  modal.id = "delete-modal";
  modal.className =
    "fixed inset-0 bg-black/20 backdrop-blur-sm flex items-center justify-center z-50";

  modal.innerHTML = `
    <div class="bg-white/95 p-5 rounded-2xl w-72 text-center space-y-4 border border-white/60 shadow-2xl">
      <h3 class="font-semibold text-lg">Delete message?</h3>

      <button id="delete-me"
        class="w-full bg-slate-100 hover:bg-slate-200 py-2 rounded-lg">
        Delete for me
      </button>

      <button id="delete-everyone"
        class="w-full bg-red-500 hover:bg-red-600 text-white py-2 rounded-lg">
        Delete for everyone
      </button>

      <button id="cancel-delete"
        class="w-full text-slate-500 text-sm">
        Cancel
      </button>
    </div>
  `;

  document.body.appendChild(modal);

  document.getElementById("delete-me").onclick = function(){
    sendDelete(messageId, "me");
    modal.remove();
  };

  document.getElementById("delete-everyone").onclick = function(){
    sendDelete(messageId, "everyone");
    modal.remove();
  };

  document.getElementById("cancel-delete").onclick = function(){
    modal.remove();
  };
};

function sendDelete(id, mode){
  if(APP.groupSocket && APP.groupSocket.readyState === WebSocket.OPEN){
    APP.groupSocket.send(JSON.stringify({
      type: "delete",
      mode: mode,
      message_id: id
    }));
  }
}


window.groupEditMessage =function(id, oldText){
    openCxPrompt({
        title: "Edit message",
        message: "Update your message below.",
        value: oldText,
        confirmText: "Save",
        onConfirm: (newText) => {
            APP.groupSocket.send(JSON.stringify({
                action: "edit",
                message_id: id,
                message: newText
            }));
        }
    });
 };

window.clearReply = function(){
    APP.replyingTo = null;
    const preview = document.getElementById("reply-preview");
    if(preview) preview.classList.add("hidden");
};

window.scrollToMessage = function(id){

    const target = document.getElementById("msg-" + id);
    if(!target) return;

    target.scrollIntoView({
        behavior: "smooth",
        block: "center"
    });

    target.classList.add("ring-2", "ring-green-400");

    setTimeout(()=>{
        target.classList.remove("ring-2", "ring-green-400");
    },1500);
};

window.openGroupInfo = function(){
    const modal = document.getElementById("groupInfoModal");
    if(!modal) return;

    modal.classList.remove("hidden");
    modal.classList.add("flex");
}

window.closeGroupInfo = function(){
    const modal = document.getElementById("groupInfoModal");
    if(!modal) return;

    modal.classList.remove("flex");
    modal.classList.add("hidden");
}

window.changeRole = function(userId, newRole){

    APP.groupSocket.send(JSON.stringify({
        action: "change_role",
        user_id: userId,
        role: newRole
    }));
}

window.removeMember = function(userId){
    openCxConfirm({
        title: "Remove member?",
        message: "They will be removed from this group.",
        confirmText: "Remove",
        onConfirm: () => {
            APP.groupSocket.send(JSON.stringify({
                action: "remove_member",
                user_id: userId
            }));
        }
    });
}

window.showAddMember = function(){
    document.getElementById("addMemberSection")
        .classList.toggle("hidden");
}

window.addMember = function(userId){

    APP.groupSocket.send(JSON.stringify({
        action: "add_member",
        user_id: userId
    }));
}

document.addEventListener("click", function (e) {
  const replyBtn = e.target.closest(".reply-btn");
  if (!replyBtn) return;

  const id = replyBtn.dataset.id;
  const text = replyBtn.dataset.text;
  const user = replyBtn.dataset.user;

  APP.replyingTo = id;

  document.getElementById("reply-user").innerText =
    user === APP.username ? "You" : user;

  document.getElementById("reply-text").innerText = text;

  document.getElementById("reply-preview").classList.remove("hidden");
});



 
