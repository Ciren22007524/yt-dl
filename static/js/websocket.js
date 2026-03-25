// const socket = new WebSocket(`ws://${window.location.host}/ws`);
const socket = new WebSocket("ws://127.0.0.1:8000/ws");

socket.onmessage = function(event) {
    const msg = JSON.parse(event.data);
    const bar = document.getElementById('progress-bar');
    const status = document.getElementById('status-text');
    const container = document.getElementById('progress-container');

    container.style.display = 'block';

    if (msg.type === 'progress') {
        // 處理進度條更新
        bar.style.width = msg.data + '%';
        status.innerText = `下載中: ${msg.data}%`;
    } else if (msg.type === 'status') {
        // 1. 先更新狀態文字（無論是否完成都要顯示）
        status.innerText = msg.data;

        // 2. 接著判斷這條 status 訊息是否代表「結束」
        if (msg.data.includes('✅')) {
            const submitBtn = document.querySelector('#download-form button[type="submit"]');
            const footer = document.getElementById('status-footer');

            if (submitBtn) submitBtn.disabled = false;
            if (footer) footer.classList.add('d-none');

            alert(msg.data); // 顯示彈窗：✅ 下載已完成！
        }
    }
};