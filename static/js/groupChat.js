window.APP = window.APP || {
    chatSocket: null,
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
        
         if(data.type === "deleted"){
            const bubble = document.getElementById("msg-" + data.message_id);
            if(bubble){
              bubble.innerHTML = "<i class='text-gray-400 text-sm'>Message deleted</i>";
            }
            return;
        }

        const box = document.getElementById("messages");

        if(!box) return;

        const isMe = data.sender_id == currentUserId;

        const messageHTML = `
            <div class="flex ${isMe ? "justify-end" : "justify-start"}">
                <div class="px-4 py-2 rounded-xl max-w-xs ${
                    isMe ? "bg-green-300" : "bg-white"
                }">

                    ${!isMe ? `<div class="text-xs font-semibold text-green-700">
                        ${data.username}
                    </div>` : ""}

                    ${data.message}

                    <div class="text-xs text-gray-600">now</div>

                </div>
            </div>
        `;

        if(data.type === "edited"){
          const bubble = document.getElementById("msg-" + data.message_id);
          if(bubble){
            bubble.querySelector(".content").innerText = data.message;
           }
           return;
        }



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
        APP.chatSocket.send(JSON.stringify({message}));
    }

    input.value = "";
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
}


 