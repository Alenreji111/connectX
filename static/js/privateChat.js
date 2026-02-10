//   var roomName = "{{ room_name }}";
//   var username = "{{ request.user.username }}";
window.APP = window.APP || {
  chatSocket: null,
  messageQueue: [],
  activeRoom: null,
  username: null,
  otherUser: null
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

    APP.chatSocket.onmessage = function (e) {
      const data = JSON.parse(e.data);
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
      // MESSAGE
      const messages = document.getElementById("messages");
      const isMe = data.username ===APP.username;

      const wrapper = document.createElement("div");
      wrapper.className = `flex ${isMe ? "justify-end" : "justify-start"}`;

      wrapper.innerHTML = `
            <div class="px-4 py-2 rounded-xl max-w-xs
                ${isMe ? "bg-green-300" : "bg-white"}">
                ${data.message}
                <div class="text-xs text-gray-600">
                    ${new Date().toLocaleTimeString([], {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  ${isMe ? `<span id="tick-${data.message_id}">✔</span>` : ""}
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

  const payload = JSON.stringify({ message });

  if (APP.chatSocket && APP.chatSocket.readyState === WebSocket.OPEN) {
    APP.chatSocket.send(payload);
    APP.chatSocket.send(JSON.stringify({ typing: false }));
  } else {
    APP.messageQueue.push(payload);
  }

  input.value = "";

  if(input){

    input.onkeydown = function(e){
        if(e.key === "Enter"){
            sendPrivateMessage();
        }
    };

    input.addEventListener("input", function () {

        if (APP.chatSocket && APP.chatSocket.readyState === WebSocket.OPEN) {
            APP.chatSocket.send(JSON.stringify({ typing: true }));
        }

        clearTimeout(typingTimeout);

        typingTimeout = setTimeout(() => {

            if (APP.chatSocket && APP.chatSocket.readyState === WebSocket.OPEN) {
                APP.chatSocket.send(JSON.stringify({ typing: false }));
            }

        }, 1000);
    });
  }
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

const messagesDiv = document.getElementById("messages");
if (messagesDiv) {
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}
