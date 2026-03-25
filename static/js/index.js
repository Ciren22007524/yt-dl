const urlInput = document.getElementById('url-input');
const formatSelect = document.getElementById('format-select');
const qualitySelect = document.getElementById('quality-select');
const videoPreview = document.getElementById('video-preview');
const downloadForm = document.getElementById('download-form');
const footer = document.getElementById('status-footer');

// 1. 動態切換品質選項 (p vs kbps)
formatSelect.addEventListener('change', () => {
    qualitySelect.innerHTML = ''; // 清空選項

    if (formatSelect.value === 'mp3') {
        const options = [
            { text: '最佳音質 (Best)', value: '0' },
            { text: '極限音質 (320kbps)', value: '320' }, // 這是 MP3 的標準極限
            { text: '高品質 (256kbps)', value: '256' },
            { text: '標準音質 (192kbps)', value: '192' },
            { text: '低音質 (128kbps)', value: '128' }
        ];
        options.forEach(opt => {
            const el = document.createElement('option');
            el.value = opt.value;
            el.textContent = opt.text;
            if(opt.value === '0') el.selected = true;
            qualitySelect.appendChild(el);
        });
    } else {
        const options = [
            { text: '最佳品質', value: 'best' },
            { text: '1080p', value: '1080' },
            { text: '720p', value: '720' },
            { text: '480p', value: '480' }
        ];
        options.forEach(opt => {
            const el = document.createElement('option');
            el.value = opt.value;
            el.textContent = opt.text;
            if(opt.value === 'best') el.selected = true;
            qualitySelect.appendChild(el);
        });
    }
});

// 2. 預覽影片封面
urlInput.addEventListener('input', async () => {
    const url = urlInput.value;
    if (url.includes('youtube.com/') || url.includes('youtu.be/')) {
        try {
            const response = await fetch(`/preview?url=${encodeURIComponent(url)}`);
            const data = await response.json();
            if (data.thumbnail) {
                videoPreview.src = data.thumbnail;
                videoPreview.classList.remove('d-none');
            }
        } catch (e) {
            console.error("預覽失敗", e);
        }
    }
});

// 3. 處理下載
downloadForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    // 顯示轉圈圈
    footer.classList.remove('d-none');
    const submitBtn = e.target.querySelector('button[type="submit"]');
    submitBtn.disabled = true;

    const formData = new FormData(e.target);
    try {
        const response = await fetch('/download', { method: 'POST', body: formData });
        const result = await response.json();

        // 這裡要配合後端回傳的 "started"
        if (result.status === 'started') {
            console.log("下載已在背景啟動，請觀察進度條");
            // 這裡可以不用 alert，因為進度條會自己跳出來
        } else {
            alert('發生錯誤：' + (result.message || '未知錯誤'));
            footer.classList.add('d-none');
            submitBtn.disabled = false;
        }
    } catch (error) {
        alert('連線失敗');
        footer.classList.add('d-none');
        submitBtn.disabled = false;
    }

    // 注意：這裡不要在 finally 裡立刻把按鈕改回可用，
    // 應該等 WebSocket 收到「✅ 下載已完成！」才把按鈕恢復。
});