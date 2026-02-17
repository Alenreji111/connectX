window.APP = window.APP || {
    chatSocket: null,
    replyingTo: null
};

function connectGroupSocket(){

    const data = document.getElementById("group-chat-data");
    if(!data) return;

    const roomId = data.dataset.roomId;
    const currentUserId = data.dataset.userId;

    const protocol = window.location.protocol === "https:" ? "wss://" : "ws://";

    APP.chatSocket = new WebSocket(
        protocol + window.location.host + "/ws/group/" + roomId + "/"
    );

    APP.chatSocket.onopen = function(){

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

    APP.chatSocket.onmessage = function(e){

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

        // ONLY HANDLE GROUP MESSAGE
        if(data.type !== "group_message") return;

        const box = document.getElementById("messages");
        if(!box) return;

        const isMe = data.sender_id == currentUserId;

        const messageHTML = `
            <div class="flex ${isMe ? "justify-end" : "justify-start"}">
                <div id="msg-${data.message_id}" 
                     class="relative px-4 py-2 rounded-xl max-w-xs ${
                        isMe ? "bg-green-300" : "bg-white"
                     }">

                    ${!isMe ? `
                        <div class="text-xs font-semibold text-green-700">
                            ${data.username}
                        </div>
                    ` : ""}

                    ${data.reply_to ? `
                        <div class="reply-preview bg-gray-200 text-xs p-2 rounded mb-1 border-l-4 border-green-500 cursor-pointer"
                             data-reply-id="${data.reply_to.id}">
                            <strong>
                                ${data.reply_to.username === APP.username ? "You" : data.reply_to.username}
                            </strong>
                            <div class="truncate">
                                ${data.reply_to.content}
                            </div>
                        </div>
                    ` : ""}

                    <div class="msg-text">
                        ${data.message}
                    </div>

                    <div class="text-xs text-gray-600 mt-1">now</div>

                    <button class="reply-btn text-gray-500 text-xs mt-1"
                        data-id="${data.message_id}"
                        data-text="${data.message}"
                        data-user="${data.username}">
                        Reply
                    </button>

                </div>
            </div>
        `;

        box.insertAdjacentHTML("beforeend", messageHTML);
        box.scrollTop = box.scrollHeight;
    };
}


window.sendGroupMessage = function(){

    const input = document.getElementById("messageInput");
    if(!input) return;

    const message = input.value.trim();
    if(!message) return;

    if(APP.chatSocket && APP.chatSocket.readyState === WebSocket.OPEN){
        APP.chatSocket.send(JSON.stringify({
            message: message,
            reply_to: APP.replyingTo
        }));
    }

    input.value = "";
    clearReply();
};
 window.deleteMessage = function(messageId){
    if(!APP.chatSocket) return;

    if(!confirm("Delete this message?")) return;

    if(APP.chatSocket && APP.chatSocket.readyState === WebSocket.OPEN){

        APP.chatSocket.send(JSON.stringify({
            type: "delete",
            message_id: messageId
        }));

    }else{
        console.log("Socket not connected");
    }
};

 window.editMessage =function(id, oldText){
    const newText = prompt("Edit message", oldText);
    if(!newText) return;

    APP.chatSocket.send(JSON.stringify({
        action: "edit",
        message_id: id,
        message: newText
    }));

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
}


 